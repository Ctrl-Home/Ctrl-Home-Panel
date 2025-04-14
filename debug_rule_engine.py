import requests
import json
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# API基础URL
BASE_URL = "http://localhost:15000/api/engine"

def get_rules():
    """获取所有规则"""
    url = f"{BASE_URL}/rules"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"获取规则失败，状态码: {response.status_code}")
        return None

def get_device_status():
    """获取所有设备状态"""
    url = f"{BASE_URL}/status/all"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"获取设备状态失败，状态码: {response.status_code}")
        return None

def get_command_history():
    """获取命令历史"""
    url = f"{BASE_URL}/commands/history"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"获取命令历史失败，状态码: {response.status_code}")
        return None

def add_rule(rule_data):
    """添加新规则"""
    url = f"{BASE_URL}/rules"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(rule_data))
    if response.status_code in [200, 201]:
        return response.json()
    else:
        logging.error(f"添加规则失败，状态码: {response.status_code}, 响应: {response.text}")
        return None

def main():
    # 获取现有规则
    logging.info("获取现有规则...")
    rules_response = get_rules()
    if rules_response:
        rules = rules_response.get("data", [])
        logging.info(f"找到 {len(rules)} 条规则")
        for rule in rules:
            logging.info(f"规则: {rule['name']}, ID: {rule['id']}, 启用: {rule['enabled']}")
    
    # 获取设备状态
    logging.info("\n获取设备状态...")
    status_response = get_device_status()
    if status_response:
        statuses = status_response.get("data", {})
        if statuses:
            logging.info(f"设备状态: {json.dumps(statuses, indent=2)}")
        else:
            logging.info("没有设备状态记录")
    
    # 获取命令历史
    logging.info("\n获取命令历史...")
    history_response = get_command_history()
    if history_response:
        history = history_response.get("data", [])
        if history:
            logging.info(f"命令历史: {json.dumps(history, indent=2)}")
        else:
            logging.info("没有命令历史记录")
    
    # 确保规则已启用
    if rules_response:
        for rule in rules_response.get("data", []):
            if rule["id"] == "rule-001" and not rule["enabled"]:
                logging.info("\n规则 rule-001 未启用，尝试启用它...")
                # 这里可以通过API启用规则，但目前我们只是输出信息
                logging.info("请通过API启用规则 rule-001")
    
    logging.info("\n调试完成")

if __name__ == "__main__":
    main() 