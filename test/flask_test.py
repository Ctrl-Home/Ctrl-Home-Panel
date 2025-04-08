# tests/test_api_integration.py
import pytest
import requests
import json
import time

BASE_URL = 'http://localhost:15000/api/engine'


def test_device_api():
    # 测试获取所有设备
    response = requests.get(f'{BASE_URL}/devices')
    assert response.status_code == 200
    devices = response.json()
    assert isinstance(devices, dict)

    # 测试获取单个设备
    device_id = list(devices.keys())[0]
    response = requests.get(f'{BASE_URL}/devices/{device_id}')
    assert response.status_code == 200
    device = response.json()
    assert device['device_id'] == device_id


def test_status_api():
    # 测试获取所有状态
    response = requests.get(f'{BASE_URL}/status/all')
    assert response.status_code == 200

    # 测试获取传感器状态
    response = requests.get(f'{BASE_URL}/status/sensors')
    assert response.status_code == 200

    # 测试获取执行器状态
    response = requests.get(f'{BASE_URL}/status/actuators')
    assert response.status_code == 200


def test_rule_api():
    # 测试添加规则
    new_rule = {
        "name": "测试规则",
        "enabled": True,
        "trigger": {
            "topic": "/device/test/sensor123/status",
            "condition": {
                "data_key": "temperature",
                "operator": ">",
                "value": 25
            }
        },
        "action": {
            "type": "device_command",
            "device_id": "ac_livingroom",
            "command": "turn_on"
        }
    }

    response = requests.post(f'{BASE_URL}/rules', json=new_rule)
    assert response.status_code == 201
    rule_id = response.json()['id']

    # 测试获取规则
    response = requests.get(f'{BASE_URL}/rules/{rule_id}')
    assert response.status_code == 200
    assert response.json()['name'] == "测试规则"

    # 测试修改规则
    new_rule['enabled'] = False
    response = requests.put(f'{BASE_URL}/rules/{rule_id}', json=new_rule)
    assert response.status_code == 200

    # 测试删除规则
    response = requests.delete(f'{BASE_URL}/rules/{rule_id}')
    assert response.status_code == 204


def test_command_history():
    # 测试获取命令历史
    response = requests.get(f'{BASE_URL}/commands/history')
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == '__main__':
    pytest.main(['-v', __file__])