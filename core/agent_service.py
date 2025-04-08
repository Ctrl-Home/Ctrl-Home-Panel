import requests # 示例：如果 Agent 提供 HTTP API
import logging

logger = logging.getLogger(__name__)

# --- !!! 这是占位符，你需要替换成实际的 Agent 通信逻辑 !!! ---
def send_command_to_agent(node_ip, node_port, node_secret, command):
    """
    向 Agent 节点发送命令。

    Args:
        node_ip (str): 节点 IP 地址。
        node_port (int): 节点端口。
        node_secret (str): 节点的 Secret Key 用于认证。
        command (str): 要发送的命令。

    Returns:
        dict: 包含 'success': bool 和 'message': str 或 'error': str 的字典。
              例如: {'success': True, 'message': 'Command executed'}
                    {'success': False, 'error': 'Connection failed'}
    """
    logger.info(f"Attempting to send command '{command}' to node {node_ip}:{node_port}")

    # 示例：如果 Agent 监听 HTTP POST 请求
    agent_url = f"http://{node_ip}:{node_port}/command" # 假设 Agent 的命令端点
    headers = {'X-Agent-Secret': node_secret, 'Content-Type': 'application/json'}
    payload = {'command': command}

    try:
        # 注意设置超时！
        response = requests.post(agent_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status() # 如果状态码是 4xx 或 5xx，则抛出异常

        # 假设 Agent 返回 JSON
        response_data = response.json()
        logger.info(f"Received response from agent {node_ip}:{node_port}: {response_data}")

        # 根据 Agent 的响应格式调整返回值
        if response_data.get('status') == 'success':
             return {'success': True, 'message': response_data.get('message', '命令已发送')}
        else:
             return {'success': False, 'error': response_data.get('error', 'Agent 执行失败')}

    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error when sending command to {node_ip}:{node_port}")
        return {'success': False, 'error': '无法连接到 Agent 节点'}
    except requests.exceptions.Timeout:
        logger.error(f"Timeout when sending command to {node_ip}:{node_port}")
        return {'success': False, 'error': '连接 Agent 节点超时'}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending command to {node_ip}:{node_port}: {e}")
        # 尝试获取响应内容以获取更多信息
        error_detail = str(e)
        if e.response is not None:
             try:
                 error_detail += f" - Response: {e.response.text}"
             except Exception:
                 pass # 忽略获取响应文本的错误
        return {'success': False, 'error': f'与 Agent 通信时出错: {error_detail}'}
    except Exception as e:
         logger.exception(f"Unexpected error sending command to {node_ip}:{node_port}")
         return {'success': False, 'error': f'发送命令时发生意外错误: {e}'}

# --- 占位符结束 ---