import paho.mqtt.client as mqtt
import json
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# MQTT 配置
MQTT_BROKER = "mumble.2k2.cc"
MQTT_PORT = 11883

# 触发主题
TRIGGER_TOPIC = "home/sensors/livingroom/temp"

def main():
    # 创建一个MQTT客户端
    client = mqtt.Client(client_id="simple-test-client", callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    
    try:
        # 连接到MQTT代理
        logging.info(f"正在连接到MQTT代理 {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # 发送高温数据以触发规则
        high_temp_data = {
            "temperature": 30,  # 高于规则阈值28度
            "humidity": 60
        }
        
        logging.info(f"发送高温数据: {high_temp_data}")
        result = client.publish(TRIGGER_TOPIC, json.dumps(high_temp_data))
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logging.info("消息发送成功")
        else:
            logging.error(f"消息发送失败，错误码: {result.rc}")
        
        # 等待一会儿，确保消息被发送
        time.sleep(2)
        
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        # 断开连接
        client.disconnect()
        logging.info("已断开MQTT连接")

if __name__ == "__main__":
    main() 