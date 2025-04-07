# routes/api/engine_routes.py
import logging
from flask import Blueprint, jsonify, request, abort, current_app # 使用 current_app 访问服务实例

# 创建 Blueprint
# 注意：这里使用 'engine_api' 作为蓝图名称，避免与类名冲突
engine_api_bp = Blueprint('engine_api', __name__, url_prefix='/api/engine') # 建议加个前缀区分

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 辅助函数：检查服务是否可用 ---
def check_service(service_name):
    service = getattr(current_app, service_name, None)
    if not service:
        logging.error(f"核心服务 '{service_name}' 未初始化或未附加到 app 对象。")
        abort(503, description=f"服务 '{service_name}' 当前不可用。")
    return service

# --- 状态查询 API ---
@engine_api_bp.route('/status/sensors', methods=['GET'])
def get_sensor_status():
    """获取所有类型为 'sensor' 的设备的最新状态。"""
    state_manager = check_service('state_manager')
    sensor_states = state_manager.get_states_by_type('sensor')
    return jsonify(sensor_states)

@engine_api_bp.route('/status/actuators', methods=['GET'])
def get_actuator_status():
    """获取所有类型为 'actuator' 的设备的最新状态。"""
    state_manager = check_service('state_manager')
    actuator_states = state_manager.get_states_by_type('actuator')
    return jsonify(actuator_states)

@engine_api_bp.route('/status/device/<string:device_id>', methods=['GET'])
def get_device_status(device_id):
    """获取指定 device_id 的设备的最新状态。"""
    state_manager = check_service('state_manager')
    device_manager = check_service('device_manager') # 也需要设备管理器来检查设备是否存在
    state = state_manager.get_state(device_id)
    if state:
        return jsonify(state)
    else:
        if device_manager.get_device(device_id):
             return jsonify({"message": "设备存在，但尚无状态记录"}), 404 # 返回 message 而不是 error
        else:
            return jsonify({"error": f"设备 ID '{device_id}' 未找到"}), 404

@engine_api_bp.route('/status/all', methods=['GET'])
def get_all_status():
    """获取所有已知设备的最新状态。"""
    state_manager = check_service('state_manager')
    all_states = state_manager.get_all_states()
    return jsonify(all_states)

# --- 命令监控 API ---
@engine_api_bp.route('/commands/history', methods=['GET'])
def get_command_history():
    """获取最近由规则引擎发送的命令历史记录。"""
    mqtt_controller = check_service('mqtt_controller')
    history = mqtt_controller.get_command_history()
    return jsonify(history)

# --- 规则管理 API (CRUD) ---
@engine_api_bp.route('/rules', methods=['GET'])
def get_rules():
    """获取所有规则的列表（包括启用和禁用的）。"""
    rule_manager = check_service('rule_manager')
    rules = rule_manager.get_all_rules()
    if rules is None:
        abort(500, description="读取规则文件时发生错误")
    return jsonify(rules)

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['GET'])
def get_rule(rule_identifier):
    """获取单个规则的详细信息 (默认按 ID, 可用 ?by=name)。"""
    rule_manager = check_service('rule_manager')
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的查找方式 'by' 参数，请使用 'id' 或 'name'"}), 400
    rule = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key)
    if rule:
        return jsonify(rule)
    else:
        return jsonify({"error": f"未找到 {lookup_key} 为 '{rule_identifier}' 的规则"}), 404

@engine_api_bp.route('/rules', methods=['POST'])
def add_rule_api(): # 重命名避免与内置 add_rule 冲突
    """添加一条新规则 (请求体为 JSON)。"""
    rule_manager = check_service('rule_manager')
    if not request.is_json:
        return jsonify({"error": "请求必须是 JSON 格式"}), 400
    new_rule_data = request.get_json()
    if not isinstance(new_rule_data, dict):
         return jsonify({"error": "JSON 数据必须是一个对象"}), 400

    # add_rule 会处理 ID 生成和验证
    success = rule_manager.add_rule(new_rule_data)
    if success:
        # new_rule_data 现在包含 ID
        return jsonify(new_rule_data), 201 # Created
    else:
        # RuleManager 内部应记录详细错误
        return jsonify({"error": "添加规则失败，请检查服务日志"}), 400 # Bad request or 500 Internal Server Error?

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['PUT'])
def update_rule_api(rule_identifier): # 重命名
    """修改现有规则 (请求体为完整 JSON, 默认按 ID, 可用 ?by=name)。"""
    rule_manager = check_service('rule_manager')
    if not request.is_json:
        return jsonify({"error": "请求必须是 JSON 格式"}), 400
    updated_rule_data = request.get_json()
    if not isinstance(updated_rule_data, dict):
         return jsonify({"error": "JSON 数据必须是一个对象"}), 400

    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的查找方式 'by' 参数"}), 400

    # 可选：验证请求体中的标识符与 URL 一致
    # if lookup_key not in updated_rule_data or updated_rule_data[lookup_key] != rule_identifier:
    #     return jsonify({"error": f"请求体中的 '{lookup_key}' 必须与 URL 标识符匹配"}), 400

    success = rule_manager.modify_rule(rule_identifier, updated_rule_data, identifier_key=lookup_key)
    if success:
        return jsonify(updated_rule_data), 200 # OK
    else:
        # 检查规则是否存在以返回 404
        rule_exists = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key)
        if not rule_exists:
             return jsonify({"error": f"未找到 {lookup_key} 为 '{rule_identifier}' 的规则"}), 404
        else:
             return jsonify({"error": "修改规则失败，请检查服务日志"}), 500 # Internal Server Error

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['DELETE'])
def delete_rule_api(rule_identifier): # 重命名
    """删除规则 (默认按 ID, 可用 ?by=name)。"""
    rule_manager = check_service('rule_manager')
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的查找方式 'by' 参数"}), 400

    success = rule_manager.delete_rule(rule_identifier, identifier_key=lookup_key)
    if success:
        return '', 204 # No Content
    else:
        # delete_rule 返回 False 可能是 "未找到" (404) 或其他错误 (500)
         return jsonify({"error": f"删除规则失败，未找到 {lookup_key} 为 '{rule_identifier}' 的规则或发生错误"}), 404 # 或 500

# --- 设备信息 API ---
@engine_api_bp.route('/devices', methods=['GET'])
def get_devices():
    """获取所有已定义的设备列表及其信息。"""
    device_manager = check_service('device_manager')
    devices = device_manager.get_all_devices()
    return jsonify(devices)

@engine_api_bp.route('/devices/<string:device_id>', methods=['GET'])
def get_device_info(device_id):
    """获取单个设备的定义信息。"""
    device_manager = check_service('device_manager')
    device_info = device_manager.get_device(device_id)
    if device_info:
        return jsonify(device_info)
    else:
        return jsonify({"error": f"设备 ID '{device_id}' 未找到"}), 404

# --- 注册函数 (供 register_all_api_routes.py 调用) ---
def register_engine_routes(app):
    """将此蓝图注册到 Flask app。"""
    app.register_blueprint(engine_api_bp)
    logging.info("引擎 API 蓝图 (engine_api_bp) 已注册。")