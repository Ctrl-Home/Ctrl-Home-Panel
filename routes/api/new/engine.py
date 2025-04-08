import logging
from flask import Blueprint, jsonify, request, abort, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
# 假设你的核心服务 (StateManager, RuleManager 等) 实例
# 会在 app 工厂中创建并附加到 current_app
# 例如: current_app.state_manager, current_app.rule_manager

engine_api_bp = Blueprint('engine_api', __name__, url_prefix='/api/engine')
logger = logging.getLogger(__name__)

# --- 辅助函数：检查服务是否可用 ---
def check_service(service_name):
    service = getattr(current_app, service_name, None)
    if not service:
        logger.error(f"核心服务 '{service_name}' 未初始化或未附加到 app 对象。")
        abort(503, description=f"服务 '{service_name}' 当前不可用。") # 503 Service Unavailable
    return service

# --- API 路由 ---
# 注意：这里假设你需要用户登录才能访问这些 API

@engine_api_bp.route('/status/sensors', methods=['GET'])
@jwt_required()
def get_sensor_status():
    """获取所有 'sensor' 类型设备的最新状态"""
    state_manager = check_service('state_manager')
    sensor_states = state_manager.get_states_by_type('sensor') # 假设有此方法
    return jsonify(sensor_states), 200

@engine_api_bp.route('/status/actuators', methods=['GET'])
@jwt_required()
def get_actuator_status():
    """获取所有 'actuator' 类型设备的最新状态"""
    state_manager = check_service('state_manager')
    actuator_states = state_manager.get_states_by_type('actuator') # 假设有此方法
    return jsonify(actuator_states), 200

@engine_api_bp.route('/status/device/<string:device_id>', methods=['GET'])
@jwt_required()
def get_device_status(device_id):
    """获取指定设备 ID 的最新状态"""
    state_manager = check_service('state_manager')
    device_manager = check_service('device_manager') # 假设有 device_manager
    state = state_manager.get_state(device_id) # 假设有此方法
    if state:
        return jsonify(state), 200
    else:
        # 检查设备是否存在于定义中
        if device_manager.get_device(device_id): # 假设有此方法
             return jsonify({"message": "设备存在，但尚无状态记录"}), 404
        else:
            return jsonify({"error": f"设备 ID '{device_id}' 未找到"}), 404

@engine_api_bp.route('/status/all', methods=['GET'])
@jwt_required()
def get_all_status():
    """获取所有已知设备的最新状态"""
    state_manager = check_service('state_manager')
    all_states = state_manager.get_all_states() # 假设有此方法
    return jsonify(all_states), 200

@engine_api_bp.route('/commands/history', methods=['GET'])
@jwt_required()
def get_command_history():
    """获取最近发送的命令历史"""
    mqtt_controller = check_service('mqtt_controller') # 假设有 mqtt_controller
    history = mqtt_controller.get_command_history() # 假设有此方法
    return jsonify(history), 200

# --- 规则管理 API (如果 RuleManager 是独立于 SQLAlchemy 模型的) ---
# 注意：如果规则管理直接通过 SQLAlchemy 模型 (如 api/rules.py)，则这些可能重复
# 如果你的 RuleManager 是不同的实现 (例如，基于文件或内存)，则保留这些

@engine_api_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_rules_from_manager():
    """获取 RuleManager 中的所有规则"""
    rule_manager = check_service('rule_manager')
    rules = rule_manager.get_all_rules() # 假设有此方法
    if rules is None:
        return jsonify({"error": "读取规则时出错"}), 500
    return jsonify(rules), 200

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['GET'])
@jwt_required()
def get_rule_from_manager(rule_identifier):
    """从 RuleManager 获取单个规则"""
    rule_manager = check_service('rule_manager')
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的 'by' 参数"}), 400
    rule = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key) # 假设有此方法
    if rule:
        return jsonify(rule), 200
    else:
        return jsonify({"error": f"未找到规则 ({lookup_key}='{rule_identifier}')"}), 404

@engine_api_bp.route('/rules', methods=['POST'])
@jwt_required()
def add_rule_to_manager():
    """向 RuleManager 添加新规则"""
    rule_manager = check_service('rule_manager')
    if not request.is_json:
        return jsonify({"error": "请求必须是 JSON"}), 400
    new_rule_data = request.get_json()
    if not isinstance(new_rule_data, dict):
        return jsonify({"error": "JSON 数据必须是对象"}), 400

    success, result_data = rule_manager.add_rule(new_rule_data) # 假设 add_rule 返回 (bool, data)
    if success:
        return jsonify(result_data), 201
    else:
        error_msg = result_data if isinstance(result_data, str) else "添加规则失败"
        return jsonify({"error": error_msg}), 400 # Or 500?

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['PUT'])
@jwt_required()
def update_rule_in_manager(rule_identifier):
    """在 RuleManager 中修改规则"""
    rule_manager = check_service('rule_manager')
    if not request.is_json:
        return jsonify({"error": "请求必须是 JSON"}), 400
    updated_rule_data = request.get_json()
    if not isinstance(updated_rule_data, dict):
         return jsonify({"error": "JSON 数据必须是一个对象"}), 400

    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的 'by' 参数"}), 400

    success, result_data = rule_manager.modify_rule(rule_identifier, updated_rule_data, identifier_key=lookup_key) # 假设 modify_rule 返回 (bool, data)
    if success:
        return jsonify(result_data), 200
    else:
        # 检查规则是否存在以返回 404
        rule_exists = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key)
        if not rule_exists:
             return jsonify({"error": f"未找到规则 ({lookup_key}='{rule_identifier}')"}), 404
        else:
             error_msg = result_data if isinstance(result_data, str) else "修改规则失败"
             return jsonify({"error": error_msg}), 500

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['DELETE'])
@jwt_required()
def delete_rule_from_manager(rule_identifier):
    """从 RuleManager 删除规则"""
    rule_manager = check_service('rule_manager')
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({"error": "无效的 'by' 参数"}), 400

    success = rule_manager.delete_rule(rule_identifier, identifier_key=lookup_key) # 假设 delete_rule 返回 bool
    if success:
        return '', 204
    else:
         # 需要区分是未找到还是删除失败
         return jsonify({"error": f"删除规则失败或未找到 ({lookup_key}='{rule_identifier}')"}), 404 # 或 500


# --- 设备信息 API (如果 DeviceManager 是独立于 SQLAlchemy Node 模型的) ---
@engine_api_bp.route('/devices', methods=['GET'])
@jwt_required()
def get_devices_from_manager():
    """获取 DeviceManager 中定义的所有设备"""
    device_manager = check_service('device_manager')
    devices = device_manager.get_all_devices() # 假设有此方法
    return jsonify(devices), 200

@engine_api_bp.route('/devices/<string:device_id>', methods=['GET'])
@jwt_required()
def get_device_info_from_manager(device_id):
    """从 DeviceManager 获取单个设备信息"""
    device_manager = check_service('device_manager')
    device_info = device_manager.get_device(device_id) # 假设有此方法
    if device_info:
        return jsonify(device_info), 200
    else:
        return jsonify({"error": f"设备 ID '{device_id}' 未在 DeviceManager 中定义"}), 404