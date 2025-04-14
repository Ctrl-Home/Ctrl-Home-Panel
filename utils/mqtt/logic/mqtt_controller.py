# mqtt_controller.py
import paho.mqtt.client as mqtt
import json
import logging
import time
import os
from collections import deque # 用于命令历史记录
from typing import TYPE_CHECKING, Deque, Dict, Any

# 修正导入路径
from utils.mqtt.logic.rule_engine import RuleEngine
from utils.mqtt.device_manager import DeviceManager

if TYPE_CHECKING:
    from utils.mqtt.state_manager import StateManager # 引入 StateManager (用于类型提示)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局命令历史记录大小配置 ---
COMMAND_HISTORY_SIZE = 50

class MqttController:
    # 添加 state_manager 参数
    def __init__(self, broker_host, broker_port, rules_engine: RuleEngine,
                 device_manager: DeviceManager, state_manager: 'StateManager', # 添加 StateManager
                 client_id=""):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id if client_id else f"rule-engine-client-{int(time.time())}"
        self.rules_engine = rules_engine
        self.device_manager = device_manager
        self.state_manager = state_manager # 存储 StateManager 实例
        self.client = mqtt.Client(client_id=self.client_id)
        self.subscribed_topics = set()

        # --- 添加命令历史记录 ---
        self.command_history: Deque[Dict[str, Any]] = deque(maxlen=COMMAND_HISTORY_SIZE)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message # 修改 on_message 以更新状态
        self.client.on_disconnect = self._on_disconnect
        self.client.on_log = self._on_log

        self.rules_engine.set_action_handler(self._execute_action) # 修改 _execute_action 以记录历史

    # _on_connect, _on_disconnect, _on_log, update_subscriptions 保持不变...

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode('utf-8')
            logging.info(f"===调试信息=== 收到主题 '{msg.topic}' 上的消息: {payload_str}")
            
            # 解析消息内容以便调试
            try:
                payload_dict = json.loads(payload_str)
                logging.info(f"===调试信息=== 解析后的消息内容: {payload_dict}")
                
                # 调用状态管理器更新设备状态
                self.state_manager.update_state_from_mqtt(msg.topic, payload_dict)
                logging.info(f"===调试信息=== 已更新状态管理器中的设备状态")
            except json.JSONDecodeError as e:
                logging.warning(f"===调试信息=== 消息内容不是有效JSON: {payload_str}，错误：{e}")
            
            # 将消息传递给规则引擎处理
            self.rules_engine.process_message(msg.topic, payload_str)
        except Exception as e:
            logging.error(f"处理主题 {msg.topic} 上的消息时出错: {e}", exc_info=True)

    def _execute_action(self, action):
        """执行动作并记录命令历史"""
        action_type = action.get("type")

        if action_type == "mqtt_publish":
            target_topic = action.get("topic")
            payload_obj = action.get("payload") # payload 是 Python 对象

            if target_topic and payload_obj is not None:
                payload_str = ""
                try:
                    payload_str = json.dumps(payload_obj)
                    logging.info(f"执行动作: 发布到 '{target_topic}', Payload: {payload_str}")
                    
                    # 添加命令到历史记录
                    command_record = {
                        "timestamp": time.time(),
                        "topic": target_topic,
                        "payload": payload_obj,
                        "source": "rule_engine"
                    }
                    self.command_history.append(command_record)
                    logging.info(f"===调试信息=== 已添加命令到历史记录，当前历史记录长度: {len(self.command_history)}")
                    
                    result = self.client.publish(target_topic, payload_str, qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logging.info(f"===调试信息=== 成功发布消息到主题 '{target_topic}'")
                    else:
                        logging.error(f"===调试信息=== 发布消息失败，错误码: {result.rc}")

                except TypeError as e:
                    logging.error(f"无法将动作 payload 序列化为 JSON: {payload_obj}。错误: {e}")
                except Exception as e:
                     logging.error(f"发布 MQTT 消息失败: {e}", exc_info=True)
            else:
                logging.warning(f"无法执行 mqtt_publish 动作: 缺少 target_topic 或 payload。 Action: {action}")
        else:
            logging.warning(f"接收到未处理的动作类型: {action_type}。 Action: {action}")

    def get_command_history(self) -> list:
        """获取最近发送的命令历史记录"""
        # deque 本身是线程安全的（对于原子操作如 append），转换为列表也是安全的
        return list(self.command_history)

    def update_subscriptions(self):
        """根据 RuleEngine 和 DeviceManager 更新 MQTT 订阅"""
        if not self.client.is_connected():
            logging.warning("MQTT 未连接，无法更新订阅。")
            return

        logging.info("正在检查并更新 MQTT 订阅...")
        # 1. 从 DeviceManager 获取所有传感器的状态主题
        sensor_topics = set(self.device_manager.get_status_topics())
        # 2. 从 RuleEngine 获取当前启用规则所需的主题
        rule_trigger_topics = set(
            self.rules_engine.get_trigger_topics())  # Ensure get_trigger_topics reflects current rules
        # 3. 合并所需主题
        required_topics = sensor_topics | rule_trigger_topics

        # 找出需要新增订阅的主题
        topics_to_subscribe = required_topics - self.subscribed_topics

        if topics_to_subscribe:
            subscriptions = [(topic, 0) for topic in topics_to_subscribe]
            result, mid = self.client.subscribe(subscriptions)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"成功订阅新增主题: {list(topics_to_subscribe)}")
                self.subscribed_topics.update(topics_to_subscribe)  # 更新已订阅集合
            else:
                logging.error(f"订阅新增主题失败，错误码: {result}, 主题: {list(topics_to_subscribe)}")
        else:
            logging.info("无需新增订阅。")
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"成功连接到 MQTT Broker: {self.broker_host}:{self.broker_port}")
            # --- 修改订阅逻辑 ---
            # 1. 从 DeviceManager 获取所有传感器的状态主题
            sensor_topics = self.device_manager.get_status_topics()
            # 2. (可选) 从 RuleEngine 获取规则中直接指定的触发主题
            rule_topics = self.rules_engine.get_trigger_topics()
            # 3. 合并并去重
            topics_to_subscribe = set(sensor_topics) | set(rule_topics)

            logging.info(f"===调试信息=== 传感器主题: {sensor_topics}")
            logging.info(f"===调试信息=== 规则主题: {rule_topics}")

            if topics_to_subscribe:
                subscriptions = [(topic, 0) for topic in topics_to_subscribe]
                client.subscribe(subscriptions)
                logging.info(f"已订阅主题: {list(topics_to_subscribe)}")
            else:
                logging.error("没有找到需要订阅的主题 (来自设备或规则)。MQTT服务将无法接收消息！")
            # --- 结束修改订阅逻辑 ---
        else:
            logging.error(f"连接失败，返回码 {rc}")

    def _on_disconnect(self, client, userdata, rc):
        logging.info(f"与 MQTT Broker 断开连接，结果代码 {rc}。尝试重连...")

    def _on_log(self, client, userdata, level, buf):
        if "SUBSCRIBE" in buf or "PUBLISH" in buf:
            logging.debug(f"MQTT客户端日志: {buf}")

    def start(self):
        """连接到 broker 并启动 MQTT 循环。"""
        try:
            logging.info(f"连接到 MQTT broker {self.broker_host}:{self.broker_port}...")
            # self.client.username_pw_set(username="your_username", password="your_password")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start() # 在后台线程中运行循环
            logging.info("MQTT 客户端循环已启动。")
        except Exception as e:
            logging.error(f"连接或启动 MQTT 循环失败: {e}", exc_info=True)

    def stop(self):
        """停止 MQTT 循环并断开连接。"""
        logging.info("停止 MQTT 客户端循环...")
        self.client.loop_stop()
        logging.info("与 MQTT broker 断开连接...")
        self.client.disconnect()
        logging.info("MQTT 客户端已停止。")
        
    def publish(self, topic, payload, qos=1, retain=False):
        """
        直接发布MQTT消息到指定主题
        
        Args:
            topic (str): 要发布到的主题
            payload (dict|str): 要发布的数据，若为dict则转为JSON字符串
            qos (int): 服务质量级别 (0, 1, 2)
            retain (bool): 是否作为保留消息
            
        Returns:
            bool: 发布是否成功
        """
        try:
            payload_str = payload
            if isinstance(payload, dict) or isinstance(payload, list):
                payload_str = json.dumps(payload)
                
            logging.info(f"发布消息到主题 '{topic}': {payload_str}")
            
            # 添加到命令历史
            command_record = {
                "timestamp": time.time(),
                "topic": topic,
                "payload": payload,
                "source": "api"
            }
            self.command_history.append(command_record)
            
            # 发布消息
            result = self.client.publish(topic, payload_str, qos=qos, retain=retain)
            success = result.rc == mqtt.MQTT_ERR_SUCCESS
            
            if success:
                logging.info(f"成功发布消息到主题 '{topic}'")
            else:
                logging.error(f"发布消息失败，错误码: {result.rc}")
                
            return success
            
        except Exception as e:
            logging.error(f"发布MQTT消息失败: {e}", exc_info=True)
            return False