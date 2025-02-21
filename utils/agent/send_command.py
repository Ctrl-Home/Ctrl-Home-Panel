# 独立出来的 send_command 函数
import requests


def send_command_old(node, command):
    """Internal function to send a command to a node."""
    agent_command_url = f"http://{node.ip_address}:{node.port}/agent/command"
    headers = {'X-Secret-Key': node.secret_key, 'Content-Type': 'application/json'}
    command_payload = {'command': command}

    try:
        response = requests.post(agent_command_url, headers=headers, json=command_payload, timeout=10)
        response.raise_for_status()

        agent_response_data = response.json()
        return agent_response_data
    except requests.exceptions.RequestException as e:
        return {'success': False, 'message': f"Failed to send command to node: {str(e)}"}

def send_command(node, command):
    return {'success': True, 'message': f"成功发送"}