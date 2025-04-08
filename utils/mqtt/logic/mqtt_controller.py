# mqtt_controller.py
import paho.mqtt.client as mqtt
import json
import logging
import time
import os
from collections import deque # 用于命令历史记录
from typing import TYPE_CHECKING, Deque, Dict, Any, Optional
from threading import Thread, Event

# 假设这些类在以下路径，根据你的项目调整
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
        self.connected = False
        self.stop_event = Event()
        self.reconnect_delay = 5  # 重连延迟时间（秒）
        self.max_reconnect_attempts = 5  # 最大重连尝试次数

        # --- 添加命令历史记录 ---
        self.command_history: Deque[Dict[str, Any]] = deque(maxlen=COMMAND_HISTORY_SIZE)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message # 修改 on_message 以更新状态
        self.client.on_disconnect = self._on_disconnect
        self.client.on_log = self._on_log

        self.rules_engine.set_action_handler(self._execute_action) # 修改 _execute_action 以记录历史

    # _on_connect, _on_disconnect, _on_log, update_subscriptions 保持不变...

    def _on_message(self, client, userdata, msg):
        """Callback 当收到消息时 - 更新状态管理器"""
        payload_str = ""
        try:
            payload_str = msg.payload.decode('utf-8')
            logging.debug(f"收到主题 '{msg.topic}' 上的消息: {payload_str}")
            payload_dict = json.loads(payload_str)

            # --- 更新状态管理器 ---
            self.state_manager.update_state_from_mqtt(msg.topic, payload_dict)

            # 将消息传递给规则引擎处理 (规则引擎可能也需要原始 dict)
            self.rules_engine.process_message(msg.topic, payload_str) # 规则引擎仍然使用字符串 payload

        except json.JSONDecodeError:
             logging.warning(f"无法解码主题 '{msg.topic}' 上的 JSON payload: {payload_str}")
             # 即使解码失败，也可以考虑是否更新状态为 "error" 或记录原始字符串
             # self.state_manager.update_state_from_mqtt(msg.topic, {"error": "invalid_json", "raw": payload_str})
        except UnicodeDecodeError:
            logging.warning(f"无法将主题 '{msg.topic}' 上的 payload 解码为 UTF-8: {msg.payload}")
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
                    result, mid = self.client.publish(target_topic, payload_str, qos=1)

                    if result == mqtt.MQTT_ERR_SUCCESS:
                         # --- 记录命令历史 ---
                         timestamp = time.time()
                         command_record = {
                             "timestamp": timestamp,
                             "topic": target_topic,
                             "payload": payload_obj, # 存储原始对象，便于API返回JSON
                             "success": True,
                             "mid": mid # 消息 ID
                         }
                         self.command_history.append(command_record)
                         logging.debug(f"命令已记录到历史: {command_record}")
                    else:
                         logging.error(f"发布 MQTT 消息到主题 '{target_topic}' 失败，错误码: {result}")
                         # 可以考虑也记录失败的尝试
                         # self.command_history.append({... "success": False, "error_code": result ...})

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
            self.connected = True
            logging.info(f"成功连接到 MQTT Broker: {self.broker_host}:{self.broker_port}")
            # --- 修改订阅逻辑 ---
            # 1. 从 DeviceManager 获取所有传感器的状态主题
            sensor_topics = self.device_manager.get_status_topics()
            # 2. (可选) 从 RuleEngine 获取规则中直接指定的触发主题
            rule_topics = self.rules_engine.get_trigger_topics()
            # 3. 合并并去重
            topics_to_subscribe = set(sensor_topics) | set(rule_topics)

            if topics_to_subscribe:
                subscriptions = [(topic, 0) for topic in topics_to_subscribe]
                client.subscribe(subscriptions)
                logging.info(f"已订阅主题: {list(topics_to_subscribe)}")
            else:
                logging.warning("没有找到需要订阅的主题 (来自设备或规则)。")
            # --- 结束修改订阅逻辑 ---
        else:
            self.connected = False
            logging.error(f"连接失败，返回码 {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logging.info(f"与 MQTT Broker 断开连接，结果代码 {rc}。尝试重连...")
        self._attempt_reconnect()

    def _on_log(self, client, userdata, level, buf):
         # logging.debug(f"MQTT Log: {buf}")
         pass

    def _execute_action(self, action):
        """执行由规则引擎解析后的动作 (预期是 mqtt_publish 类型)。"""
        action_type = action.get("type")

        # 现在只处理由 RuleEngine 解析好的 mqtt_publish 动作
        if action_type == "mqtt_publish":
            target_topic = action.get("topic")
            payload_obj = action.get("payload") # payload 应该是 Python 对象 (dict, list, etc.)

            if target_topic and payload_obj is not None:
                try:
                    # 将 Python 对象转换为 JSON 字符串
                    payload_str = json.dumps(payload_obj)
                    logging.info(f"执行动作: 发布到 '{target_topic}', Payload: {payload_str}")
                    self.client.publish(target_topic, payload_str, qos=1) # 使用 QoS 1 保证送达
                except TypeError as e:
                    logging.error(f"无法将动作 payload 序列化为 JSON: {payload_obj}。错误: {e}")
                except Exception as e:
                     logging.error(f"发布 MQTT 消息失败: {e}", exc_info=True)
            else:
                logging.warning(f"无法执行 mqtt_publish 动作: 缺少 target_topic 或 payload。 Action: {action}")
        else:
            #理论上不应该执行到这里，因为 RuleEngine 应该已经处理了
            logging.warning(f"接收到未处理的动作类型: {action_type}。 Action: {action}")

    def _attempt_reconnect(self):
        """尝试重新连接到MQTT代理"""
        attempts = 0
        while not self.connected and attempts < self.max_reconnect_attempts and not self.stop_event.is_set():
            try:
                attempts += 1
                logging.info(f"尝试重新连接 (尝试 {attempts}/{self.max_reconnect_attempts})")
                self.client.reconnect()
                time.sleep(self.reconnect_delay)
            except Exception as e:
                logging.error(f"重连尝试失败: {e}")
                time.sleep(self.reconnect_delay)
        
        if not self.connected and not self.stop_event.is_set():
            logging.error("达到最大重连尝试次数，停止重连")

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
            self._attempt_reconnect()

    def stop(self):
        """停止 MQTT 循环并断开连接。"""
        logging.info("停止 MQTT 客户端循环...")
        self.stop_event.set()
        self.client.loop_stop()
        logging.info("与 MQTT broker 断开连接...")
        self.client.disconnect()
        logging.info("MQTT 客户端已停止。")