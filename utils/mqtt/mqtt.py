# 在 main.py 文件或其他你的主执行文件中

import logging
import time
import os
import signal
import sys
import json

# 假设你的类都在这些路径下，请根据你的项目结构调整
from utils.mqtt.device_manager import DeviceManager
from utils.mqtt.logic.rule_engine import RuleEngine
from utils.mqtt.logic.mqtt_controller import MqttController
from utils.mqtt.logic.rule_manager import RuleManager
from utils.mqtt.state_manager import StateManager
from typing import Optional

from utils.mqtt.test.mqtt_rule_test import test_rule_management

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 配置 (与 main.py 中保持一致) ---
script_dir = os.path.dirname(os.path.abspath(__file__))
DEVICES_FILE_PATH = os.path.join(script_dir, "devices.json")
RULES_FILE_PATH = os.path.join(script_dir, "rules.json")
MQTT_BROKER_HOST = "mumble.2k2.cc"
MQTT_BROKER_PORT = 11883
# --- 结束配置 ---

# --- 全局实例，用于关闭处理 ---
mqtt_controller_instance: Optional[MqttController] = None

def validate_config():
    """验证配置文件的有效性"""
    try:
        # 验证设备文件
        with open(DEVICES_FILE_PATH, 'r') as f:
            devices = json.load(f)
            if not isinstance(devices, dict):
                raise ValueError("设备文件格式错误：应为JSON对象")
            
        # 验证规则文件
        with open(RULES_FILE_PATH, 'r') as f:
            rules = json.load(f)
            if not isinstance(rules, list):
                raise ValueError("规则文件格式错误：应为JSON数组")
            
    except FileNotFoundError as e:
        logging.error(f"配置文件不存在: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"配置文件格式错误: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"配置文件验证失败: {e}")
        sys.exit(1)

def shutdown_handler(signum, frame):
    global mqtt_controller_instance
    logging.info("收到关闭信号，正在停止应用...")
    if mqtt_controller_instance:
        try:
            mqtt_controller_instance.stop()
        except Exception as e:
            logging.error(f"停止MQTT控制器时发生错误: {e}")
    sys.exit(0)

if __name__ == '__main__':
    # --- 设置信号处理 ---
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # --- 验证配置文件 ---
    validate_config()

    try:
        # --- 初始化核心组件 ---
        # 1. 设备管理器
        device_manager = DeviceManager(devices_file=DEVICES_FILE_PATH)
        
        # 2. 状态管理器
        state_manager = StateManager(device_manager=device_manager)
        
        # 3. 规则引擎
        rule_engine = RuleEngine(device_manager=device_manager, rules_file=RULES_FILE_PATH)
        
        # 4. MQTT 控制器
        mqtt_controller_instance = MqttController(
            broker_host=MQTT_BROKER_HOST,
            broker_port=MQTT_BROKER_PORT,
            rules_engine=rule_engine,
            device_manager=device_manager,
            state_manager=state_manager
        )
        
        # 5. 规则管理器
        rule_manager = RuleManager(
            rules_file_path=RULES_FILE_PATH,
            rule_engine=rule_engine,
            mqtt_controller=mqtt_controller_instance
        )

        # --- 启动 MQTT ---
        mqtt_controller_instance.start()
        logging.info("MQTT 控制器已启动，等待连接...")
        
        # 给 MQTT 一点时间连接和完成初始订阅
        time.sleep(3)

        # --- 调用测试函数 ---
        test_rule_management(rule_manager)

        # --- 保持主程序运行 ---
        logging.info("规则引擎正在运行。按 Ctrl+C 退出。")
        while True:
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                shutdown_handler(signal.SIGINT, None)
            except Exception as e:
                logging.error(f"主循环发生错误: {e}")
                time.sleep(5)  # 发生错误时等待5秒后继续

    except Exception as e:
        logging.exception("程序初始化失败")
        shutdown_handler(signal.SIGTERM, None)