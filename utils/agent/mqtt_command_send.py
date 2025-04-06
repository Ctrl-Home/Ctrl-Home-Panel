import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import yaml

config_file = "command_config.yaml"  # 配置文件名
mqtt_broker_host="10.1.0.177"

def load_command_config(config_file):
    """
    加载 YAML 命令配置文件。

    Args:
        config_file (str, optional): YAML 配置文件路径。默认为 "command_config.yaml"。

    Returns:
        dict:  加载的 YAML 配置字典。如果文件不存在或加载失败，返回 None。
    """
    try:
        with open(config_file, 'r',encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except FileNotFoundError:
        print(f"配置文件 '{config_file}' 未找到.")
        return None
    except yaml.YAMLError as e:
        print(f"加载 YAML 配置文件 '{config_file}' 失败: {e}")
        return None


def connect_mqtt_broker(mqtt_broker_host, mqtt_broker_port=11883):
    """
    连接到 MQTT Broker。

    Args:
        mqtt_broker_host (str, optional): MQTT Broker 的主机地址。默认为 "10.1.0.177"。
        mqtt_broker_port (int, optional): MQTT Broker 的端口号。默认为 1883。

    Returns:
        mqtt.Client: MQTT 客户端实例。如果连接失败，返回 None。
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) # 创建 MQTT 客户端实例
    try:
        client.connect(mqtt_broker_host, mqtt_broker_port, 60) # 连接到 Broker，keepalive 设为 60 秒
        return client
    except Exception as e:
        print(f"连接 MQTT Broker '{mqtt_broker_host}:{mqtt_broker_port}' 失败: {e}")
        return None

def send_command(brand, product_type, operation, params=None,
                 mqtt_broker_host="10.1.0.177", mqtt_broker_port=11883, topic_prefix="node",
                 config_file="command_config.yaml"):
    """
    根据品牌、产品类型和操作，从配置文件中查找并发送 MQTT 命令。

    Args:
        brand (str): 产品品牌。
        product_type (str): 产品类型 (例如: light, fan, switch)。
        operation (str): 具体操作 (例如: on, off, brightness, speed_low, toggle)。
        params (dict, optional): 操作所需的参数，例如 {'brightness': 50}。 默认为 None。
        mqtt_broker_host (str, optional): MQTT Broker 的主机地址。默认为 "mqtt.eclipseprojects.io"。
        mqtt_broker_port (int, optional): MQTT Broker 的端口号。默认为 1883。
        topic_prefix (str, optional): MQTT 主题前缀，用于构建命令主题。默认为 "node"。
        config_file (str, optional): YAML 配置文件路径。默认为 "command_config.yaml"。

    Returns:
        dict: 包含操作结果的字典。
              - 'success' (bool): 指示命令是否成功发送。
              - 'message' (str): 包含操作结果的详细信息。
    """

    config = load_command_config(config_file)
    if not config:
        return {'success': False, 'message': "无法加载命令配置文件。"}

    try:
        mqtt_command_template = config['brands'][brand]['product_types'][product_type]['operations'][operation]
    except KeyError:
        error_message = f"未找到品牌 '{brand}'，产品类型 '{product_type}' 或操作 '{operation}' 的配置。"
        print(error_message)
        return {'success': False, 'message': error_message}

    mqtt_command = mqtt_command_template  # 默认使用模板
    if params:
        try:
            mqtt_command = mqtt_command_template.format(**params) # 尝试格式化命令字符串
        except KeyError as e:
            error_message = f"参数 '{e}' 在提供的 params 中未找到，但命令模板需要。"
            print(error_message)
            return {'success': False, 'message': error_message}
        except ValueError as e:  # 捕获更多格式化错误
            error_message = f"格式化命令字符串时出错: {e}。请检查命令模板和参数。"
            print(error_message)
            return {'success': False, 'message': error_message}


    node_name = f"{brand}_{product_type}" # 假设节点名称可以根据品牌和产品类型生成，你可以根据实际情况调整
    topic = f"{topic_prefix}/{node_name}/command"

    client = connect_mqtt_broker(mqtt_broker_host, mqtt_broker_port) # 连接 MQTT Broker
    if not client:
        return {'success': False, 'message': f"无法连接到 MQTT Broker '{mqtt_broker_host}:{mqtt_broker_port}'。"}

    try:
        publish.single(topic, payload=mqtt_command, hostname=mqtt_broker_host, port=mqtt_broker_port) # 使用 publish.single，它内部也会处理连接，这里连接函数其实可以移除，保留publish.single的连接方式更简洁。
        # 或者使用 client.publish 方法 (需要先启动 client 的 loop，这里为了简化示例，仍然使用 publish.single)
        # client.publish(topic, payload=mqtt_command)
        return {'success': True, 'message': f"成功发送命令 '{mqtt_command}' 到节点 '{node_name}'，主题: '{topic}'"}
    except Exception as e:
        error_message = f"发送命令到节点 '{node_name}' 失败: {e}"
        print(error_message)
        return {'success': False, 'message': error_message}
    finally:
        if client: # 确保 client 对象存在才断开连接
            client.disconnect() # 断开 MQTT 连接



if __name__ == '__main__':

    # 开灯 (BrandA, Light, On)
    result_on = send_command("brandA", "light", "turn-on", config_file=config_file)
    print(f"开灯命令结果: {result_on}")

    # 关灯 (BrandA, Light, Off)
    result_off = send_command("brandA", "light", "turn-off", config_file=config_file)
    print(f"关灯命令结果: {result_off}")

    # 调节亮度 (BrandA, Light, Brightness, 参数 brightness=75)
    result_brightness = send_command("brandA", "light", "brightness", params={'brightness': 75},
                                     config_file=config_file)
    print(f"调节亮度命令结果: {result_brightness}")


    # 风扇低速 (BrandA, Fan, Speed_low)
    result_fan_low = send_command("brandA", "fan", "speed_low", config_file=config_file)
    print(f"风扇低速命令结果: {result_fan_low}")

    # 开关切换 (BrandB, Switch, Toggle)
    result_switch_toggle = send_command("brandB", "switch", "toggle", config_file=config_file)
    print(f"开关切换命令结果: {result_switch_toggle}")
