# routes/utils/agent.py
import requests
import json
from flask import jsonify
from models import Node  # 导入 Node
# 假设你的agent 蓝图已经被注册，例如： app.register_blueprint(agent_bp)
# from your_app import app  # 导入你的 Flask app
# 简化agent command 函数
def handle_command(command_data, node_secret_key):
    """处理来自agent的命令.

    Args:
        command_data (dict): 包含命令和相关参数的字典。
        node_secret_key (str):  节点的 secret_key，用于身份验证和关联。

        Returns:
            dict:  处理结果。
        """
    command = command_data.get('command')
    if command == 'start_relay':
        software_name = command_data.get('software_name')
        config = command_data.get('config')
        node_api_address = command_data.get('node_api_address')  # 从 command_data 中获取
        api_username = command_data.get('api_username')
        api_password = command_data.get('api_password')

        if not all([software_name, config, node_api_address, api_username, api_password]):
            return {"success": False, "message": "Missing parameters for start_relay"}
        #  根据 software_name 选择不同的处理方式
        if software_name == "gost":
            #  处理 gost 配置
            api_config_json = json.dumps(config)
            api_config_url = f"{node_api_address}/config"  # gost 的配置接口
            api_auth = (api_username, api_password)
            headers = {'Content-Type': 'application/json', 'X-Secret-Key': node_secret_key} # 加上secret key
            try:
                response = requests.post(api_config_url, headers=headers, data=api_config_json, auth=api_auth, timeout=10)
                response.raise_for_status()
                api_response_data = response.json()
                if api_response_data.get('status') == 'ok':
                    return {"success": True, "message": f"gost 配置成功: {api_response_data.get('message')}", "api_response": api_response_data}
                else:
                    return {"success": False, "message": f"gost 配置失败: {api_response_data.get('message')}", "api_response": api_response_data}

            except requests.exceptions.RequestException as e:
                return {"success": False, "message": f"Failed to communicate with gost API: {str(e)}"}
        elif software_name == "v2ray":
            # 处理v2ray配置
            #  这里的实现取决于你的 v2ray 控制接口.  可能需要使用 v2ctl，或者直接修改 v2ray 的配置文件
            #  这个例子只是一个占位符
            api_config_url = f"{node_api_address}/v2ctl/config"  #  v2ray 的配置接口 (示例)
            api_auth = (api_username, api_password)
            headers = {'Content-Type': 'application/json', 'X-Secret-Key': node_secret_key} #  加上 secret key
            try:
                response = requests.post(api_config_url, headers=headers, data=json.dumps(config), auth=api_auth, timeout=10)
                response.raise_for_status()
                api_response_data = response.json()
                if api_response_data.get('status') == 'ok':
                    return {"success": True, "message": f"v2ray 配置成功: {api_response_data.get('message')}", "api_response": api_response_data}
                else:
                    return {"success": False, "message": f"v2ray 配置失败: {api_response_data.get('message')}", "api_response": api_response_data}
            except requests.exceptions.RequestException as e:
                return {"success": False, "message": f"Failed to communicate with v2ray API: {str(e)}"}
        else:
            return {"success": False, "message": f"不支持的软件: {software_name}"}
    #  处理其他命令
    return {"success": False, "message": "Unknown command"}