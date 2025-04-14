import paho.mqtt.client as mqtt
import json
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# MQTT 配置
MQTT_BROKER = "mumble.2k2.cc"
MQTT_PORT = 11883
CLIENT_ID = f"mqtt-test-client-{int(time.time())}"

# 需要测试的主题
TRIGGER_TOPIC = "home/sensors/livingroom/temp"  # 触发主题
ACTION_TOPIC = "home/devices/livingroom/ac/set"  # 动作主题

# 当连接上服务器时的回调函数
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"已连接到 MQTT Broker: {MQTT_BROKER}")
        
        # 订阅动作主题，监听规则引擎是否发送了控制命令
        client.subscribe(ACTION_TOPIC)
        logging.info(f"已订阅主题: {ACTION_TOPIC}")
    else:
        logging.error(f"连接失败，返回码 {rc}")

# 当收到消息时的回调函数
def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        logging.info(f"收到消息，主题: {msg.topic}, 内容: {payload_str}")
        
        # 如果消息来自动作主题，说明规则被触发了
        if msg.topic == ACTION_TOPIC:
            logging.info("🎉 规则触发成功！空调控制指令已发送。")
            
    except Exception as e:
        logging.error(f"处理消息出错: {e}")

def main():
    # 创建客户端实例，指定API版本
    client = mqtt.Client(client_id=CLIENT_ID, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        # 连接到 MQTT Broker
        logging.info(f"正在连接到 MQTT Broker {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # 启动网络循环
        client.loop_start()
        
        # 等待连接成功
        time.sleep(2)
        
        # 发送温度数据，模拟温度过高
        temp_data = {
            "temperature": 30,  # 高于规则中设定的 28 度
            "humidity": 60
        }
        
        logging.info(f"发送温度数据: {temp_data}")
        client.publish(TRIGGER_TOPIC, json.dumps(temp_data))
        
        # 等待一段时间，观察规则触发
        logging.info("等待规则触发...")
        time.sleep(5)
        
        # 发送正常温度数据
        normal_temp_data = {
            "temperature": 26,  # 低于规则中设定的 28 度
            "humidity": 60
        }
        
        logging.info(f"发送正常温度数据: {normal_temp_data}")
        client.publish(TRIGGER_TOPIC, json.dumps(normal_temp_data))
        
        # 再等待一段时间
        time.sleep(5)
        
        logging.info("测试完成，按 Ctrl+C 退出...")
        
        # 保持程序运行，直到用户按下 Ctrl+C
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("用户终止程序")
            
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        # 停止网络循环并断开连接
        client.loop_stop()
        client.disconnect()
        logging.info("已断开连接")

if __name__ == "__main__":
    main() 