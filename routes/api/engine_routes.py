# routes/api/engine_routes.py
import logging
from flask import Blueprint, jsonify, request, abort, current_app # 使用 current_app 访问服务实例
import time

# 创建 Blueprint
# 注意：这里使用 'engine_api' 作为蓝图名称，避免与类名冲突
engine_api_bp = Blueprint('engine_api', __name__, url_prefix='/api/engine') # 建议加个前缀区分

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 辅助函数：检查服务是否可用 ---
def check_service(service_name):
    """
    检查服务是否可用，如果不可用则返回JSON格式错误而不是HTML错误页面
    适合前后端分离的应用程序
    """
    service = getattr(current_app, service_name, None)
    if not service:
        logging.error(f"核心服务 '{service_name}' 未初始化或未附加到 app 对象。")
        # 不使用abort(503)，而是返回JSON格式的错误
        error_response = {
            "code": 503,
            "message": f"服务 '{service_name}' 当前不可用。",
            "data": None
        }
        return None, error_response
    return service, None

# --- 状态查询 API ---
@engine_api_bp.route('/status/sensors', methods=['GET'])
def get_sensor_status():
    """获取所有类型为 'sensor' 的设备的最新状态。"""
    state_manager, error = check_service('state_manager')
    if error:
        return jsonify(error), error["code"]
    
    sensor_states = state_manager.get_states_by_type('sensor')
    
    # 打印详细日志以便调试
    logging.info(f"==调试== 获取传感器状态: {sensor_states}")
    
    return jsonify({
        "code": 200,
        "message": "成功获取传感器状态",
        "data": sensor_states
    })

@engine_api_bp.route('/status/actuators', methods=['GET'])
def get_actuator_status():
    """获取所有类型为 'actuator' 的设备的最新状态。"""
    state_manager, error = check_service('state_manager')
    if error:
        return jsonify(error), error["code"]
    
    actuator_states = state_manager.get_states_by_type('actuator')
    
    # 打印详细日志以便调试
    logging.info(f"==调试== 获取执行器状态: {actuator_states}")
    
    return jsonify({
        "code": 200,
        "message": "成功获取执行器状态",
        "data": actuator_states
    })

@engine_api_bp.route('/status/device/<string:device_id>', methods=['GET'])
def get_device_status(device_id):
    """获取指定 device_id 的设备的最新状态。"""
    state_manager, error = check_service('state_manager')
    if error:
        return jsonify(error), error["code"]
        
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    state = state_manager.get_state(device_id)
    
    # 打印详细日志以便调试
    logging.info(f"==调试== 获取设备 {device_id} 状态: {state}")
    
    if state:
        return jsonify({
            "code": 200,
            "message": "成功获取设备状态",
            "data": state
        })
    else:
        if device_manager.get_device(device_id):
            return jsonify({
                "code": 404,
                "message": "设备存在，但尚无状态记录",
                "data": None
            }), 404
        else:
            return jsonify({
                "code": 404,
                "message": f"设备 ID '{device_id}' 未找到",
                "data": None
            }), 404

@engine_api_bp.route('/status/all', methods=['GET'])
def get_all_status():
    """获取所有已知设备的最新状态。"""
    state_manager, error = check_service('state_manager')
    if error:
        return jsonify(error), error["code"]
        
    all_states = state_manager.get_all_states()
    return jsonify({
        "code": 200,
        "message": "成功获取所有设备状态",
        "data": all_states
    })

# --- 命令监控 API ---
@engine_api_bp.route('/commands/history', methods=['GET'])
def get_command_history():
    """获取最近由规则引擎发送的命令历史记录。"""
    mqtt_controller, error = check_service('mqtt_controller')
    if error:
        return jsonify(error), error["code"]
        
    history = mqtt_controller.get_command_history()
    return jsonify({
        "code": 200,
        "message": "成功获取命令历史",
        "data": history
    })

# --- 规则管理 API (CRUD) ---
@engine_api_bp.route('/rules', methods=['GET'])
def get_rules():
    """获取所有规则的列表（包括启用和禁用的）。"""
    rule_manager, error = check_service('rule_manager')
    if error:
        return jsonify(error), error["code"]
        
    rules = rule_manager.get_all_rules()
    if rules is None:
        return jsonify({
            "code": 500,
            "message": "读取规则文件时发生错误",
            "data": None
        }), 500
    
    return jsonify({
        "code": 200,
        "message": "成功获取规则列表",
        "data": rules
    })

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['GET'])
def get_rule(rule_identifier):
    """获取单个规则的详细信息 (默认按 ID, 可用 ?by=name)。"""
    rule_manager, error = check_service('rule_manager')
    if error:
        return jsonify(error), error["code"]
        
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({
            "code": 400,
            "message": "无效的查找方式 'by' 参数，请使用 'id' 或 'name'",
            "data": None
        }), 400
        
    rule = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key)
    if rule:
        return jsonify({
            "code": 200,
            "message": "成功获取规则信息",
            "data": rule
        })
    else:
        return jsonify({
            "code": 404,
            "message": f"未找到 {lookup_key} 为 '{rule_identifier}' 的规则",
            "data": None
        }), 404

@engine_api_bp.route('/rules', methods=['POST'])
def add_rule_api(): # 重命名避免与内置 add_rule 冲突
    """添加一条新规则 (请求体为 JSON)。"""
    rule_manager, error = check_service('rule_manager')
    if error:
        return jsonify(error), error["code"]
        
    if not request.is_json:
        return jsonify({
            "code": 400,
            "message": "请求必须是 JSON 格式",
            "data": None
        }), 400
        
    new_rule_data = request.get_json()
    if not isinstance(new_rule_data, dict):
        return jsonify({
            "code": 400,
            "message": "JSON 数据必须是一个对象",
            "data": None
        }), 400

    # add_rule 会处理 ID 生成和验证
    success = rule_manager.add_rule(new_rule_data)
    if success:
        # new_rule_data 现在包含 ID
        return jsonify({
            "code": 201,
            "message": "成功创建规则",
            "data": new_rule_data
        }), 201 # Created
    else:
        # RuleManager 内部应记录详细错误
        return jsonify({
            "code": 400,
            "message": "添加规则失败，请检查服务日志",
            "data": None
        }), 400 # Bad request or 500 Internal Server Error?

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['PUT'])
def update_rule_api(rule_identifier): # 重命名
    """修改现有规则 (请求体为完整 JSON, 默认按 ID, 可用 ?by=name)。"""
    rule_manager, error = check_service('rule_manager')
    if error:
        return jsonify(error), error["code"]
        
    if not request.is_json:
        return jsonify({
            "code": 400,
            "message": "请求必须是 JSON 格式",
            "data": None
        }), 400
        
    updated_rule_data = request.get_json()
    if not isinstance(updated_rule_data, dict):
        return jsonify({
            "code": 400,
            "message": "JSON 数据必须是一个对象",
            "data": None
        }), 400

    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({
            "code": 400,
            "message": "无效的查找方式 'by' 参数",
            "data": None
        }), 400

    # 可选：验证请求体中的标识符与 URL 一致
    # if lookup_key not in updated_rule_data or updated_rule_data[lookup_key] != rule_identifier:
    #     return jsonify({"error": f"请求体中的 '{lookup_key}' 必须与 URL 标识符匹配"}), 400

    success = rule_manager.modify_rule(rule_identifier, updated_rule_data, identifier_key=lookup_key)
    if success:
        return jsonify({
            "code": 200,
            "message": "规则更新成功",
            "data": updated_rule_data
        }), 200 # OK
    else:
        # 检查规则是否存在以返回 404
        rule_exists = rule_manager.get_rule(rule_identifier, identifier_key=lookup_key)
        if not rule_exists:
            return jsonify({
                "code": 404,
                "message": f"未找到 {lookup_key} 为 '{rule_identifier}' 的规则",
                "data": None
            }), 404
        else:
            return jsonify({
                "code": 500,
                "message": "修改规则失败，请检查服务日志",
                "data": None
            }), 500 # Internal Server Error

@engine_api_bp.route('/rules/<string:rule_identifier>', methods=['DELETE'])
def delete_rule_api(rule_identifier): # 重命名
    """删除规则 (默认按 ID, 可用 ?by=name)。"""
    rule_manager, error = check_service('rule_manager')
    if error:
        return jsonify(error), error["code"]
        
    lookup_key = request.args.get('by', 'id').lower()
    if lookup_key not in ['id', 'name']:
        return jsonify({
            "code": 400,
            "message": "无效的查找方式 'by' 参数",
            "data": None
        }), 400

    success = rule_manager.delete_rule(rule_identifier, identifier_key=lookup_key)
    if success:
        return jsonify({
            "code": 204,
            "message": "规则已成功删除",
            "data": None
        }), 204 # No Content
    else:
        # delete_rule 返回 False 可能是 "未找到" (404) 或其他错误 (500)
        return jsonify({
            "code": 404, 
            "message": f"删除规则失败，未找到 {lookup_key} 为 '{rule_identifier}' 的规则或发生错误",
            "data": None
        }), 404 # 或 500

# --- 设备信息 API ---
@engine_api_bp.route('/devices', methods=['GET'])
def get_devices():
    """获取所有已定义的设备列表及其信息。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    devices = device_manager.get_all_devices()
    return jsonify({
        "code": 200,
        "message": "成功获取设备列表",
        "data": devices
    })

@engine_api_bp.route('/devices/<string:device_id>', methods=['GET'])
def get_device_info(device_id):
    """获取单个设备的定义信息。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    device_info = device_manager.get_device(device_id)
    if device_info:
        return jsonify({
            "code": 200,
            "message": "成功获取设备信息",
            "data": device_info
        })
    else:
        return jsonify({
            "code": 404,
            "message": f"设备 ID '{device_id}' 未找到",
            "data": None
        }), 404

@engine_api_bp.route('/devices', methods=['POST'])
def add_device():
    """添加新设备（请求体为 JSON）。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    if not request.is_json:
        return jsonify({
            "code": 400,
            "message": "请求必须是 JSON 格式",
            "data": None
        }), 400
        
    device_data = request.get_json()
    if not isinstance(device_data, dict):
        return jsonify({
            "code": 400,
            "message": "JSON 数据必须是一个对象",
            "data": None
        }), 400
    
    # 调用设备管理器添加设备
    result = device_manager.add_device(device_data)
    
    # 检查结果是否包含错误
    if "error" in result:
        return jsonify({
            "code": 400,
            "message": result["error"],
            "data": None
        }), 400
    
    # 成功，返回创建的设备
    return jsonify({
        "code": 201,
        "message": "设备创建成功",
        "data": result
    }), 201

@engine_api_bp.route('/devices/<string:device_id>', methods=['PUT'])
def update_device(device_id):
    """更新现有设备（请求体为 JSON）。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    if not request.is_json:
        return jsonify({
            "code": 400,
            "message": "请求必须是 JSON 格式",
            "data": None
        }), 400
        
    updated_data = request.get_json()
    if not isinstance(updated_data, dict):
        return jsonify({
            "code": 400,
            "message": "JSON 数据必须是一个对象",
            "data": None
        }), 400
    
    # 调用设备管理器更新设备
    result = device_manager.update_device(device_id, updated_data)
    
    # 检查结果是否包含错误
    if "error" in result:
        return jsonify({
            "code": 400,
            "message": result["error"],
            "data": None
        }), 400
    
    # 成功，返回更新后的设备
    return jsonify({
        "code": 200,
        "message": "设备更新成功",
        "data": result
    })

@engine_api_bp.route('/devices/<string:device_id>', methods=['DELETE'])
def delete_device(device_id):
    """删除指定设备。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
    
    # 调用设备管理器删除设备
    result = device_manager.delete_device(device_id)
    
    # 检查结果是否包含错误
    if "error" in result:
        return jsonify({
            "code": 400,
            "message": result["error"],
            "data": None
        }), 400
    
    # 成功，返回204 No Content
    return "", 204

# --- 状态查询和定时刷新 API ---
@engine_api_bp.route('/dashboard/status', methods=['GET'])
def get_dashboard_status():
    """
    获取仪表盘所需的所有数据，包括设备定义和当前状态。
    这个API针对前端定时刷新优化，一次返回所有需要的数据。
    """
    # 获取所需服务
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    state_manager, error = check_service('state_manager')
    if error:
        return jsonify(error), error["code"]
    
    # 获取所有设备定义
    all_devices = device_manager.get_all_devices()
    logging.info(f"==调试== 仪表盘API: 获取到 {len(all_devices)} 个设备定义")
    
    # 获取所有设备状态
    all_states = state_manager.get_all_states()
    logging.info(f"==调试== 仪表盘API: 获取到 {len(all_states)} 个设备状态")
    logging.info(f"==调试== 仪表盘API: 设备状态详情: {all_states}")
    
    # 合并数据，为每个设备添加其状态
    dashboard_data = {}
    for device_id, device_info in all_devices.items():
        device_data = device_info.copy()  # 复制设备定义
        
        # 添加当前状态（如果有）
        state_info = all_states.get(device_id)
        if state_info:
            device_data["current_state"] = state_info.get("state", {})
            device_data["last_updated"] = state_info.get("timestamp")
            logging.info(f"==调试== 仪表盘API: 设备 {device_id} 有状态数据: {state_info.get('state', {})}")
        else:
            device_data["current_state"] = {}
            device_data["last_updated"] = None
            logging.info(f"==调试== 仪表盘API: 设备 {device_id} 无状态数据")
        
        dashboard_data[device_id] = device_data
    
    response_data = {
        "code": 200,
        "message": "成功获取仪表盘数据",
        "data": dashboard_data,
        "timestamp": time.time()  # 添加服务器时间戳便于前端处理
    }
    
    logging.info(f"==调试== 仪表盘API: 返回数据概要: {len(dashboard_data)}个设备")
    
    return jsonify(response_data)

# --- 设备命令 API ---
@engine_api_bp.route('/devices/command', methods=['POST'])
def execute_device_command():
    """执行设备命令，向设备发送MQTT消息。"""
    device_manager, error = check_service('device_manager')
    if error:
        return jsonify(error), error["code"]
        
    mqtt_controller, error = check_service('mqtt_controller')
    if error:
        return jsonify(error), error["code"]
    
    if not request.is_json:
        return jsonify({
            "code": 400,
            "message": "请求必须是JSON格式",
            "data": None
        }), 400
    
    command_data = request.get_json()
    if not isinstance(command_data, dict):
        return jsonify({
            "code": 400,
            "message": "JSON数据必须是对象格式",
            "data": None
        }), 400
    
    # 验证必要参数
    device_id = command_data.get('device_id')
    command = command_data.get('command')
    params = command_data.get('params', {})
    
    if not device_id or not command:
        return jsonify({
            "code": 400,
            "message": "缺少必要参数: device_id和command",
            "data": None
        }), 400
    
    # 获取设备信息
    device = device_manager.get_device(device_id)
    if not device:
        return jsonify({
            "code": 404,
            "message": f"设备未找到: {device_id}",
            "data": None
        }), 404
    
    # 检查命令是否存在
    commands = device.get('commands', {})
    command_info = commands.get(command)
    if not command_info:
        return jsonify({
            "code": 400,
            "message": f"设备 {device_id} 不支持命令: {command}",
            "data": None
        }), 400
    
    # 获取命令主题和payload模板
    command_topic, payload_template = device_manager.get_command_details(device_id, command)
    if not command_topic or payload_template is None:
        return jsonify({
            "code": 500,
            "message": f"无法获取命令 {command} 的详细信息",
            "data": None
        }), 500
    
    # 构建最终的payload
    final_payload = device_manager.build_payload(payload_template, params)
    if final_payload is None:
        return jsonify({
            "code": 400,
            "message": "构建命令payload失败，请检查参数",
            "data": None
        }), 400
    
    # 发布MQTT消息
    try:
        # 准备MQTT发布动作
        resolved_action = {
            "type": "mqtt_publish",
            "topic": command_topic,
            "payload": final_payload
        }
        
        # 发布消息
        mqtt_controller.publish(resolved_action["topic"], resolved_action["payload"])
        
        return jsonify({
            "code": 200,
            "message": f"命令 '{command}' 已发送到设备 '{device_id}'",
            "data": {
                "topic": command_topic,
                "payload": final_payload
            }
        })
    except Exception as e:
        logging.error(f"发送设备命令失败: {e}")
        return jsonify({
            "code": 500,
            "message": f"发送命令失败: {e}",
            "data": None
        }), 500

# --- 注册函数 (供 register_all_api_routes.py 调用) ---
def register_engine_routes(app):
    """将此蓝图注册到 Flask app。"""
    app.register_blueprint(engine_api_bp)
    logging.info("引擎 API 蓝图 (engine_api_bp) 已注册。")