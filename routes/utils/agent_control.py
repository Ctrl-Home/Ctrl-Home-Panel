import requests
import yaml
from flask import jsonify
from models import db, User, Rule, Node, NodeSoftware  # 使用 Node 替换 Server
import json

#  假设你有一个 handle_command 函数，在 agent.py 或其他地方
from routes.utils.agent import handle_command  #  导入 handle_command  请根据你的 agent 代码实际情况调整路径
from routes.utils.software_install import start_gost


def load_protocols(file_path="tools/gost/protocols.yaml"):  #  修正文件路径
    """从 YAML 文件加载协议配置."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:  #  指定编码为 utf-8
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"错误：未找到协议配置文件 {file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"错误：解析 YAML 文件时出错: {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"错误：使用utf-8编码读取文件时出错: {e}")  # 增加错误提示
        return None

def get_protocol_config(protocol_name):
    """
    获取单个协议的配置.

    Args:
        protocol_name (str): 协议名称.

    Returns:
        dict: 协议配置字典, 如果未找到则返回 None.
    """
    protocols = load_protocols()
    if not protocols or 'protocols' not in protocols:
        return None

    return protocols['protocols'].get(protocol_name)


def agent_control(protocol_name, source_addr, destination_addr, entry_node, exit_node, current_user):
    """
    控制 Agent 启动/配置转发。

    Args:
        protocol_name (str): 协议名称。
        source_addr (str): 源地址。
        destination_addr (str): 目标地址。
        entry_node (Node): 入口节点对象。
        exit_node (Node): 出口节点对象。
        current_user (User):  当前用户。

    Returns:
        tuple: (success, message)。 success 为布尔值，表示是否成功；message 为提示信息。
    """

    protocol_config = get_protocol_config(protocol_name)
    if not protocol_config:
        return False, f"未找到协议 '{protocol_name}' 的配置"

    #  查找出口节点上运行的软件实例
    software_instance = NodeSoftware.query.filter_by(node_id=exit_node.id, software_name="gost").first()  #  例如，固定为 gost,  或者从前端选择

    if not software_instance:
        #  如果数据库中没有 Gost 实例，则尝试安装并启动它
        if not start_gost(exit_node.id):
            return False, "没有找到 gost 软件实例，且自动安装失败"

        # 重新获取软件实例 (因为可能刚刚安装)
        software_instance = NodeSoftware.query.filter_by(node_id=exit_node.id, software_name="gost").first()
        if not software_instance:
            return False, "自动安装成功后，仍然没有找到 gost 软件实例"
    # 准备配置数据
    config_data = {}

    #  获取配置文件路径，或者根据 software_name 来判断配置处理方式
    if software_instance.config_path:
        #  如果软件使用配置文件
        try:
            with open(software_instance.config_path, 'r') as f:
                #  尝试加载配置，这取决于配置文件格式
                config_from_file = yaml.safe_load(f) # 或者json.load(f)
                #  使用配置文件中的数据，或者覆盖
                #  例如: config_data = config_from_file
                config_data['services'] = config_from_file['services'] #这里需要根据你的配置来修改，修改配置内容
        except FileNotFoundError:
            return False, f"配置文件未找到: {software_instance.config_path}"
        except yaml.YAMLError as e: # 或者 json.JSONDecodeError
            return False, f"无法解析配置文件: {e}"
    else:
        #  如果配置信息存储在数据库中，或者根据 software_name 动态生成
        #  例如，如果使用 v2ray，可能需要动态生成配置
        if software_instance.software_name == "v2ray":
            #  在这里动态构建 v2ray 配置
            config_data = {
                "inbounds": [
                    {
                        "port": int(source_addr.split(':')[-1]),  #  从 source_addr 中提取端口
                        "protocol": "vmess",
                        "settings": {
                            "clients": [
                                # ...
                            ]
                        }
                    }
                ],
                "outbounds": [
                    {
                        "protocol": "freedom",
                        "settings": {}
                    }
                ]
            }

    # 替换占位符，使用 f-string
    try:
        entry_config = protocol_config['entry']
        exit_config = protocol_config['exit']
        config_data['entry'] = json.loads(json.dumps(entry_config).replace("{{source_addr}}", source_addr))  # 替换源地址
        config_data['exit'] = json.loads(json.dumps(exit_config).replace("{{destination_addr}}", destination_addr))  # 替换目标地址
    except KeyError as e:
        return False, f"协议配置格式错误: 缺少必需的字段: {e}"
    except Exception as e:
        return False, f"配置处理出错: {e}"

    #  构造 agent 命令
    #  构造 agent 命令
    command_data = {
        "command": "start_relay",
        "software_name": software_instance.software_name,
        "config": config_data,
        "node_api_address": exit_node.ip_address,
        "api_username": software_instance.api_username,
        "api_password": software_instance.api_password,
        "secret_key": exit_node.secret_key,
    }

    print("command_data:", command_data)  #  打印 command_data
    #  调用 handle_command 函数
    response = handle_command(command_data, exit_node.secret_key)

    #  调用 handle_command 函数
    response = handle_command(command_data, exit_node.secret_key)  #  使用出口节点的 secret_key
    #  处理 agent 的响应
    if response.get("success"):
        return True, response.get("message")
    else:
        return False, response.get("message")