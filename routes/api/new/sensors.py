import time
import logging
from flask import Blueprint, jsonify, current_app
# 假设 MQTT 订阅逻辑封装在某个服务或 utils 中
# from utils.mqtt_subscribe import MqttSubscriber, process_sensor_data # 导入你的实现

sensors_bp = Blueprint('sensors', __name__, url_prefix='/api/sensors')
logger = logging.getLogger(__name__)

# 缓存或共享数据的方式需要根据实际情况设计
# 这个简单的例子每次请求都重新订阅，效率不高，仅作演示
# 更好的方式是有一个后台服务持续监听 MQTT 并更新状态

@sensors_bp.route('/sensor1', methods=['GET'])
# @jwt_required() # 根据是否需要登录访问来决定
def get_sensor1_data():
    """获取 Sensor1 的数据 (示例，效率低)"""
    # --- 这是一个非常基础的示例，实际应用需要更健壮的方式 ---
    # 例如，使用后台线程/任务队列来更新缓存或数据库中的传感器状态
    data = {'temperature': None, 'humidity': None, 'data_received': False, 'error': None}

    try:
        # --- 这里需要替换为你实际获取传感器数据的逻辑 ---
        # 可能是从数据库/缓存读取，或者触发一次 MQTT 请求/等待
        # 模拟获取数据:
        # logger.info("Fetching data for sensor1...")
        # data['temperature'] = round(random.uniform(20, 25), 1)
        # data['humidity'] = round(random.uniform(40, 60), 1)
        # data['data_received'] = True
        # time.sleep(0.1) # 模拟延迟

        # --- 如果使用原来的 MqttSubscriber 方式 (每次请求都连接，效率低) ---
        # class DataFetcher:
        #     # ... (复制你原来的 DataFetcher 逻辑) ...
        # fetcher = DataFetcher()
        # fetcher.fetch_data() # 这会阻塞一段时间
        # data['temperature'] = fetcher.temperature
        # data['humidity'] = fetcher.humidity
        # data['data_received'] = fetcher.data_received
        # --- 结束 MqttSubscriber 示例 ---

        # 假设你有一个 state_manager
        state_manager = getattr(current_app, 'state_manager', None)
        if state_manager:
             sensor1_state = state_manager.get_state('sensor1_id') # 假设 sensor1 有个 ID
             if sensor1_state:
                 data['temperature'] = sensor1_state.get('temperature')
                 data['humidity'] = sensor1_state.get('humidity')
                 # 判断数据是否过时
                 last_update = sensor1_state.get('timestamp')
                 if last_update and (time.time() - last_update < 60): # 1分钟内有效
                      data['data_received'] = True
                 else:
                      data['data_received'] = False
                      data['error'] = "数据过时"
             else:
                 data['error'] = "未找到 Sensor1 的状态"
        else:
             data['error'] = "状态管理器不可用"
             logger.warning("State Manager not found on current_app")


    except Exception as e:
        logger.exception("获取 Sensor1 数据时出错")
        data['error'] = f"获取数据时出错: {e}"
        return jsonify(data), 500

    if data['data_received']:
        return jsonify(data), 200
    else:
         # 如果没有收到数据或数据过时，返回 404 或 200 带错误信息？取决于你的 API 设计
         return jsonify(data), 404 # 404 Not Found