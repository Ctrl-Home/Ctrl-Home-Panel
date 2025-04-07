# 在 main.py 文件或其他你的主执行文件中

import logging
import time
import os
import signal
import sys

# 假设你的类都在这些路径下，请根据你的项目结构调整
from utils.mqtt.device_manager import DeviceManager
from utils.mqtt.logic.rule_engine import RuleEngine
from utils.mqtt.logic.mqtt_controller import MqttController
from utils.mqtt.logic.rule_manager import RuleManager # 引入规则管理器
from typing import Optional # 用于类型提示

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

def shutdown_handler(signum, frame):
    global mqtt_controller_instance
    logging.info("收到关闭信号，正在停止应用...")
    if mqtt_controller_instance:
        mqtt_controller_instance.stop()
    sys.exit(0)




if __name__ == '__main__':
    # --- 设置信号处理 ---
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # --- 初始化核心组件 ---
    # 1. 设备管理器
    device_manager = DeviceManager(devices_file=DEVICES_FILE_PATH)
    # 2. 规则引擎
    rule_engine = RuleEngine(device_manager=device_manager, rules_file=RULES_FILE_PATH)
    # 3. MQTT 控制器
    mqtt_controller_instance = MqttController( # 赋值给全局变量以便关闭
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        rules_engine=rule_engine,
        device_manager=device_manager
    )
    # 4. 规则管理器
    rule_manager = RuleManager(
        rules_file_path=RULES_FILE_PATH,
        rule_engine=rule_engine,
        mqtt_controller=mqtt_controller_instance
    )

    # --- 启动 MQTT ---
    mqtt_controller_instance.start()
    logging.info("MQTT 控制器已启动，等待连接...")
    # 给 MQTT 一点时间连接和完成初始订阅，再进行规则操作
    time.sleep(3) # 等待 3 秒

    # --- 调用测试函数 ---
    test_rule_management(rule_manager) # 传入初始化好的 rule_manager

    # --- 保持主程序运行 ---
    logging.info("规则引擎正在运行。按 Ctrl+C 退出。")
    try:
        while True:
            time.sleep(60) # 主循环可以做其他事或长时间休眠
    except KeyboardInterrupt:
        shutdown_handler(signal.SIGINT, None)
    except Exception as e:
        logging.exception("主循环发生意外错误。")
        shutdown_handler(signal.SIGTERM, None)