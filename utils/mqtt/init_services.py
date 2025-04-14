import logging
import os
import atexit
from flask import Flask

from utils.mqtt.device_manager import DeviceManager
from utils.mqtt.state_manager import StateManager
from utils.mqtt.logic.rule_engine import RuleEngine
from utils.mqtt.logic.mqtt_controller import MqttController
from utils.mqtt.logic.rule_manager import RuleManager

def init_mqtt_services(app: Flask, config: dict):
    """初始化并将MQTT相关服务附加到Flask应用对象"""
    logging.info("正在初始化MQTT服务组件...")
    
    # 配置路径
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    devices_file = os.path.join(script_dir, "mqtt", "devices.json")
    rules_file = os.path.join(script_dir, "mqtt", "rules.json")
    
    mqtt_config = config.get('mqtt', {
        'broker_host': 'mumble.2k2.cc',
        'broker_port': 11883
    })
    
    # 确保文件存在
    for file_path in [devices_file, rules_file]:
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write('{}')  # 写入空JSON对象
            logging.warning(f"创建了空文件: {file_path}")
    
    # 1. 初始化设备管理器
    device_manager = DeviceManager(devices_file=devices_file)
    app.device_manager = device_manager
    
    # 2. 初始化状态管理器
    state_manager = StateManager(device_manager=device_manager)
    app.state_manager = state_manager
    
    # 3. 初始化规则引擎
    rule_engine = RuleEngine(device_manager=device_manager, rules_file=rules_file)
    app.rule_engine = rule_engine
    
    # 4. 初始化MQTT控制器
    mqtt_controller = MqttController(
        broker_host=mqtt_config.get('broker_host'),
        broker_port=mqtt_config.get('broker_port'),
        rules_engine=rule_engine,
        device_manager=device_manager,
        state_manager=state_manager
    )
    app.mqtt_controller = mqtt_controller
    
    # 5. 初始化规则管理器
    rule_manager = RuleManager(
        rules_file_path=rules_file,
        rule_engine=rule_engine,
        mqtt_controller=mqtt_controller
    )
    app.rule_manager = rule_manager
    
    # 注册应用程序退出时的清理函数，而不是每个请求结束时
    def shutdown_mqtt():
        if hasattr(app, 'mqtt_controller') and getattr(app, 'mqtt_running', False):
            app.mqtt_controller.stop()
            app.mqtt_running = False
            logging.info("MQTT服务已停止")
    
    # 使用atexit模块注册清理函数
    atexit.register(shutdown_mqtt)
    
    logging.info("MQTT服务组件已初始化完成")
    return app

def start_mqtt_services(app: Flask):
    """启动MQTT服务，适合在应用正式运行时调用"""
    if hasattr(app, 'mqtt_controller') and not getattr(app, 'mqtt_running', False):
        app.mqtt_controller.start()
        app.mqtt_running = True
        logging.info("MQTT服务已启动")
    return app 