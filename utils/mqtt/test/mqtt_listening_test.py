from utils.mqtt.mqtt_subscribe import MqttSubscriber

if __name__ == '__main__':
    listener = MqttSubscriber(
        broker_host="10.1.0.177",  # Replace with your broker's host
        broker_port=11883,  # Replace with your broker's port if different
        topic="/device/test/ac1/living_room/command"
    )
    listener.start()
    listener.wait_for_messages(2000)
    listener.stop()

    print("Program finished.")
