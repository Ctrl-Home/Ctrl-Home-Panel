import paho.mqtt.client as mqtt
import time
import json
import random


class SmartLight:
    """
    MQTT 智能灯类，模拟灯的开关、色温调节。
    使用 Paho MQTT v2 API。
    """

    def __init__(self, device_id, broker_address, broker_port=1883, topic_prefix="smart_light"):
        """
        初始化 SmartLight 对象。

        Args:
            device_id (str): 设备的唯一 ID。
            broker_address (str): MQTT Broker 的地址。
            broker_port (int, optional): MQTT Broker 的端口。默认为 1883。
            topic_prefix (str, optional): MQTT 主题的前缀。 默认为 "smart_light"。
        """
        self.device_id = device_id
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        # 使用 CallbackAPIVersion.VERSION2 指定使用 V2 API
        self.client = mqtt.Client(client_id=f"light_simulator_{device_id}_{random.randint(0, 1000)}",
                                   protocol=mqtt.MQTTv5,  # 明确指定 MQTT 版本为 v5，如果 Broker 支持
                                   callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish  # 添加 on_publish 回调
        self.state = {
            "power": "OFF",
            "color_temp": 2700,
        }
        self.control_topic = f"{self.topic_prefix}/{self.device_id}/control"
        self.state_topic = f"{self.topic_prefix}/{self.device_id}/state"
        self.color_temp_topic = f"{self.topic_prefix}/{self.device_id}/setColorTemp"

    def connect(self):
        """连接到 MQTT Broker。"""
        self.client.connect(self.broker_address, self.broker_port, 60)
        self.client.loop_start()

    def disconnect(self):
        """断开与 MQTT Broker 的连接。"""
        self.publish_state()
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """MQTT 连接成功回调函数 (V2 API)。"""
        if reason_code == 0:
            print(f"Connected to MQTT Broker as {self.device_id}!")
            self.client.subscribe(self.control_topic)
            self.client.subscribe(self.color_temp_topic)
            self.publish_state()
        else:
            print(f"Connection failed with code: {reason_code}")  # reason_code 现在是一个对象

    def _on_message(self, client, userdata, msg):
        """MQTT 消息接收回调函数 (V2 API)。"""
        print(f"Received message on topic: {msg.topic} with payload: {msg.payload.decode()}")
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            print("Invalid JSON format.")
            return

        if msg.topic == self.control_topic:
            if "power" in payload:
                self.set_power(payload["power"])

        elif msg.topic == self.color_temp_topic:
            if "color_temp" in payload:
                self.set_color_temperature(payload["color_temp"])

    def _on_publish(self, client, userdata, mid, reason_codes=None, properties=None):
        """MQTT 消息发布回调函数 (V2 API)。"""
        # reason_codes 是一个列表，即使只有一个原因码。 对于 MQTT v3.x，列表为空。
        if reason_codes:  # 检查列表是否非空
           for reason_code in reason_codes:
               if reason_code >= 128:  # 128 及以上通常表示发布失败
                    print(f"Publish failed with reason code: {reason_code}")
        else: # v3
            print(f"Message published (mid: {mid})")


    def publish_state(self):
        """发布灯具当前状态。"""
        self.client.publish(self.state_topic, json.dumps(self.state), retain=True)
        print(f"Published state: {self.state}")

    def set_power(self, power_state):
        """设置灯的开关状态。"""
        power_state = power_state.upper()
        if power_state in ("ON", "OFF"):
            self.state["power"] = power_state
            self.publish_state()
        else:
            print("Invalid power command. Use 'ON' or 'OFF'.")

    def set_color_temperature(self, color_temp):
        """设置灯的色温。"""
        try:
            color_temp = int(color_temp)
            if 2700 <= color_temp <= 6500:
                self.state["color_temp"] = color_temp
                self.publish_state()
            else:
                print("Color temperature out of range (2700-6500).")
        except ValueError:
            print("Invalid color temperature value. Must be an integer.")


if __name__ == '__main__':
    MQTT_BROKER = "192.168.7.190"
    MQTT_PORT = 1883

    light1 = SmartLight("living_room_light", MQTT_BROKER, MQTT_PORT)
    light1.connect()

    light2 = SmartLight("bedroom_light", MQTT_BROKER, MQTT_PORT)
    light2.connect()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        light1.disconnect()
        light2.disconnect()