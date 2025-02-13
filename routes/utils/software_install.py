import os
import subprocess
import platform
import yaml
from flask import current_app  # 确保 Flask 应用程序上下文可用
from models import NodeSoftware, Node, db
import requests  # 导入 requests 用于发送命令

# --- 辅助函数 (可复用) ---

def execute_command(command, capture_output=True, check=True):
    """
    执行 shell 命令，并处理错误。
    """
    try:
        result = subprocess.run(command, capture_output=capture_output, check=check, text=True, shell=True)  # 使用 text=True 解码输出，shell=True
        if capture_output:
            return result.stdout, result.stderr, 0 # 返回stdout, stderr, exit_code
        else:
            return None, None, 0
    except subprocess.CalledProcessError as e:
        return None, e.stderr, e.returncode # 发生错误时返回stderr和exit_code
    except FileNotFoundError:
        return None, "命令未找到", 127 # 文件未找到错误码
    except Exception as e:
        return None, str(e), 1 # 其他错误

def get_os():
    """检测服务器的操作系统。"""
    os_name = platform.system().lower()
    os_info = {"name": "unknown"}

    if os_name == "linux":
        distro = platform.linux_distribution()[0].lower()
        os_info = {"name": "linux", "distro": distro}
    elif os_name == "windows":
        os_info = {"name": "windows"}
    elif os_name == "darwin":
        os_info = {"name": "macos"}

    return os_info

def start_gost(node_id, config_path=None):
    """
    启动 Gost (Windows 专用)。
    """
    os_info = get_os()
    if os_info["name"] != "windows":
        print("此函数仅适用于 Windows 系统。")
        return False

    try:
        # 1. 查找 Gost 可执行文件 (假设 gost.exe 在 PATH 中，或者需要指定完整路径)
        gost_executable = "gost.exe"  #  或者  "C:\\path\\to\\gost.exe"  -- 需要根据实际情况修改

        # 2. 构造 Gost 启动命令。  这里我们简化配置，直接通过命令行参数传递
        #    你可以根据需要扩展此部分，支持更复杂的配置

        # a. 获取 Node 信息 (API 相关)
        node = Node.query.get(node_id)
        if not node:
            print(f"未找到 ID 为 {node_id} 的节点信息.")
            return False

        # b. 构建 Gost 启动命令
        command = [
            gost_executable,
            "-L", "http://:8080",  # 监听端口 (可以修改)
            "-api", f"admin:password@{node.ip_address}:18080?pathPrefix=/api&accesslog=true", # 使用节点 IP 和端口
            #  "-C", config_path,  #  如果需要配置文件，启用此行并传递 config_path
            # 其他参数，例如 -F 转发设置
        ]
        print(f"启动 Gost 的命令: {' '.join(command)}")

        # 3. 使用 Popen 在后台启动 Gost  (Windows 需要 shell=True)
        process = subprocess.Popen(" ".join(command), shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        print(f"Gost 进程 ID: {process.pid}")

        # 4. 更新数据库中的 Gost 信息 (启动成功后)
        if update_gost_software_info(node_id, config_path): # 即使这里 config_path=None，也没关系
            print("Gost 启动成功，数据库信息已更新。")
        else:
            print("Gost 启动成功，但数据库信息更新失败。")
        return True

    except FileNotFoundError:
        print(f"未找到 Gost 可执行文件 '{gost_executable}'。请确保已安装 Gost，且可执行文件位于 PATH 中，或者指定了完整路径。")
        return False
    except Exception as e:
        print(f"启动 Gost 失败: {e}")
        return False

# --- 其他辅助函数 (保持不变) ---

def install_gost(node_id, config_path="/etc/gost/config.yml"):  #  Windows不需要安装
    """
    自动安装 Gost。

    Args:
        node_id (int): gost 所在节点的 ID (关联到 Node 表)。
        config_path (str, optional): gost 配置文件路径. 默认值是 "/etc/gost/config.yml"。

    Returns:
        bool: 安装是否成功。
    """
    print("Windows 系统不需要安装 Gost。 请手动安装。")
    return False
def update_gost_software_info(node_id, config_path):
    """更新 NodeSoftware 表中的 Gost 信息。"""
    try:
        existing_software = NodeSoftware.query.filter_by(node_id=node_id, software_name="gost").first()
        if existing_software:
            existing_software.config_path = config_path
            db.session.commit()
            print("Gost 软件实例已更新")
        else:
            new_software = NodeSoftware(
                node_id=node_id,
                software_name="gost",
                config_path=config_path,
            )
            db.session.add(new_software)
            db.session.commit()
            print("Gost 软件实例已创建")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"更新数据库时发生错误: {e}")
        return False

def check_gost_status(node_id):
    """检查 Gost 是否已安装。"""
    gost_instance = NodeSoftware.query.filter_by(node_id=node_id, software_name="gost").first()
    if not gost_instance:
        return False

    #  检查 Gost 进程 (更可靠的方法)
    try:
        node = Node.query.get(node_id)
        if not node:
            return False

        command = [
            "curl",
            "-s",  # 静默模式
            "-I",   # 仅获取头部信息
            f"http://{node.ip_address}:8080",  #  假设 gost 监听 8080
            "--connect-timeout", "2" # 设置超时时间，2秒
        ]

        stdout, stderr, exit_code = execute_command(command)
        if exit_code == 0 and "HTTP/1.1 200 OK" in stdout:
            print("gost 进程已启动")
            return True
        else:
            print("gost 进程未启动")
            return False

    except Exception as e:
        print(f"检查 gost 状态时出错: {e}")
        return False