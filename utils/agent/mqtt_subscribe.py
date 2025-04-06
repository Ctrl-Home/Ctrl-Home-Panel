import time

import paho.mqtt.client as paho
import json  # Import the json module


# 全局变量来存储最新的温湿度数据和接收状态
latest_temperature = None
latest_humidity = None
data_received = False
last_update_time = None  # 用于跟踪上次更新时间

class MqttSubscriber:
    """
    MQTT 订阅者类，用于订阅指定主题并接收消息。
    """

    def __init__(self, broker_host, broker_port, topic, callback=None):
        """
        初始化 MQTT 订阅者。

        Args:
            broker_host (str): MQTT Broker 的主机名或 IP 地址。
            broker_port (int): MQTT Broker 的端口号。
            topic (str): 要订阅的主题。
            callback (callable, optional): 接收到消息时的回调函数。默认为 None。
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.callback = callback
        self.client = paho.Client()
        self.client.on_message = self._on_message  # 设置内部消息处理函数
        self.client.on_connect = self._on_connect  #设置连接成功的处理函数

    def _on_connect(self, client, userdata, flags, rc):
        """
        (内部) 连接到 MQTT Broker 时的回调函数。
        """
        if rc == 0:
            print(f"成功连接到 MQTT Broker: {self.broker_host}:{self.broker_port}")
            self.client.subscribe(self.topic)  # 订阅主题
            print(f"已订阅主题: {self.topic}")
        else:
            print(f"连接到 MQTT Broker 失败，返回码: {rc}")

    def _on_message(self, client, userdata, msg):
        """
        (内部) 收到 MQTT 消息时的回调函数。
        """
        try:
            message_content = msg.payload.decode()  # 解码消息内容
            # Parse the JSON payload
            data = json.loads(message_content)
            print(f"收到消息，主题: {msg.topic}, 内容: {data}")

            if self.callback:
                self.callback(data)  # Pass the parsed data to the callback

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from topic {msg.topic}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred processing message from {msg.topic}: {e}")

    def start(self):
        """
        启动 MQTT 订阅者，开始监听消息。
        """
        self.client.connect(self.broker_host, self.broker_port, 60)  #连接
        self.client.loop_start()  # 开启一个独立的循环线程

    def stop(self):
        """
        停止 MQTT 订阅者。
        """
        self.client.loop_stop()
        self.client.disconnect()
        print("MQTT 订阅者已停止。")

    def wait_for_messages(self, duration=None):
        """
        等待消息，可选地指定等待的时间。
        这个方式，适合于测试或者只需要接收有限数量消息的场景

        Args:
            duration (float, optional): 等待消息的最长时间（秒）。如果为 None，则无限期等待。
        """
        if duration is None:
            while True:
                time.sleep(1)  # 持续监听，通过 Ctrl+C 或其他方式停止
        else:
            time.sleep(duration)  # 等待指定的时间



def process_sensor_data(data):
    """
    处理从 MQTT Broker 接收的传感器数据。

    Args:
        data (dict): 从 MQTT 消息解析的 JSON 数据。
                     预期格式：{"params": {"temp": <temperature>, "humi": <humidity>}}

    Returns:
        tuple: 包含温度、湿度和数据接收状态的元组 (temperature, humidity, data_received)。
               如果数据无效或缺失，返回 (None, None, False)。
    """
    if "params" in data:
        params = data["params"]
        if "temp" in params and "humi" in params:
            temperature = params["temp"]
            humidity = params["humi"]
            print(f"Temperature: {temperature}°C, Humidity: {humidity}%")
            return temperature, humidity, True  # 返回数据和接收状态
        else:
            print("Received data is missing 'temp' or 'humi' keys within 'params'.")
            return None, None, False
    else:
        print("Received data is missing 'params' key.")
        return None, None, False

# --- Example Usage ---
if __name__ == "__main__":
    # Callback function to process the received data
    def process_sensor_data(data):
        """
        Processes the sensor data received from the MQTT broker.

        Args:
            data (dict): The parsed JSON data from the MQTT message.
                         Expected format: {"temp": <temperature>, "humi": <humidity>}
        """
        if "params" in data:
            params = data["params"]
            if "temp" in params and "humi" in params:
                temperature = params["temp"]
                humidity = params["humi"]
                print(f"Temperature: {temperature}°C, Humidity: {humidity}%")
            else:
                print("Received data is missing 'temp' or 'humi' keys within 'params'.")
        else:
            print("Received data is missing 'params' key.")


    # Create a subscriber instance for the sensor data topic
    subscriber = MqttSubscriber(
        broker_host="10.1.0.177",  # Replace with your broker's host
        broker_port=11883,  # Replace with your broker's port if different
        topic="/test/sensor1",
        callback=process_sensor_data
    )

    subscriber.start()
    subscriber.wait_for_messages(30)  # Wait for messages for 30 seconds
    subscriber.stop()

    print("Program finished.")
