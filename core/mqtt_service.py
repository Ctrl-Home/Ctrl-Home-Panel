import paho.mqtt.client as mqtt
import logging

logger = logging.getLogger(__name__)

class MQTTService:
    def __init__(self):
        self.client = mqtt.Client()
        self.is_connected = False
        self.config = {} # 会在 init_app 中设置

    def init_app(self, app):
        self.config = {
            'broker_host': app.config['MQTT_BROKER_HOST'],
            'broker_port': app.config['MQTT_BROKER_PORT'],
            'username': app.config.get('MQTT_USERNAME'),
            'password': app.config.get('MQTT_PASSWORD'),
            'topic_base': app.config.get('MQTT_TOPIC_BASE', 'smart_home/api')
        }

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        # 可以添加 on_message 回调来处理订阅的消息

        if self.config['username'] and self.config['password']:
            self.client.username_pw_set(self.config['username'], self.config['password'])

        try:
            self.client.connect(self.config['broker_host'], self.config['broker_port'], 60)
            self.client.loop_start() # 使用后台线程处理网络循环
            logger.info(f"MQTT Service: Connecting to {self.config['broker_host']}:{self.config['broker_port']}")
        except Exception as e:
            logger.error(f"MQTT Service: Failed to connect initially: {e}")

        # 注册应用销毁时的清理函数
        app.teardown_appcontext(self.teardown)


    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            logger.info("MQTT Service: Connected to MQTT Broker!")
            # 在这里可以订阅需要的 Topic
            # client.subscribe("some/topic")
        else:
            self.is_connected = False
            logger.error(f"MQTT Service: Failed to connect, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        logger.warning(f"MQTT Service: Disconnected from MQTT Broker (rc={rc}). Will attempt to reconnect.")
        # paho-mqtt 的 loop_start 会自动处理重连

    def publish(self, topic, payload=None, qos=0, retain=False):
        if not self.is_connected:
            logger.error("MQTT Service: Cannot publish, not connected.")
            return False
        try:
            result = self.client.publish(topic, payload, qos, retain)
            result.wait_for_publish(timeout=5) # 等待发布完成 (可选，增加可靠性)
            if result.is_published():
                logger.info(f"MQTT Service: Published to topic '{topic}', payload: {payload}")
                return True
            else:
                 logger.error(f"MQTT Service: Failed to publish to topic '{topic}' (mid={result.mid})")
                 return False
        except ValueError as e: # payload 格式问题
             logger.error(f"MQTT Service: Error publishing to topic '{topic}': {e}")
             return False
        except Exception as e:
             logger.error(f"MQTT Service: Unexpected error publishing to topic '{topic}': {e}")
             return False

    def teardown(self, exception):
        """在应用上下文结束时关闭 MQTT 连接"""
        if self.client and self.is_connected:
            logger.info("MQTT Service: Disconnecting from MQTT broker.")
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False

# 在 extensions.py 中实例化
# from .mqtt_service import MQTTService
# mqtt_service = MQTTService()
# 然后在 create_app 中调用 mqtt_service.init_app(app)