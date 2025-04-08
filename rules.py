import logging
from flask import Blueprint, request, jsonify, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Rule, User, Node
# 假设 MQTTService 实例附加到了 app
# from core.mqtt_service import MQTTService # 不需要直接导入，用 current_app

rules_bp = Blueprint('rules', __name__, url_prefix='/api/rules')
logger = logging.getLogger(__name__)

# 示例设备操作列表 (可以移到配置)
DEVICE_ACTIONS = ["on", "off", "toggle", "brightness", "color", "status_query"]

# --- 辅助函数 ---
def get_user_from_jwt():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        abort(401, description="无效的用户 Token") # 或者 404 Not Found? 401 更合适
    return user

def check_permission(rule, user):
     if user.role != 'admin' and rule.user_id != user.id:
         abort(403, description="无权操作此规则") # 403 Forbidden

# --- API 路由 ---

@rules_bp.route('', methods=['GET'])
@jwt_required()
def list_rules():
    """获取规则列表 (用户或管理员)"""
    user = get_user_from_jwt()
    if user.role == 'admin':
        rules_query = Rule.query.all()
    else:
        rules_query = Rule.query.filter_by(user_id=user.id).all()

    return jsonify([rule.to_dict() for rule in rules_query]), 200

@rules_bp.route('/<int:rule_id>', methods=['GET'])
@jwt_required()
def get_rule(rule_id):
    """获取单个规则详情"""
    user = get_user_from_jwt()
    rule = Rule.query.get_or_404(rule_id)
    check_permission(rule, user)
    return jsonify(rule.to_dict()), 200

@rules_bp.route('', methods=['POST'])
@jwt_required()
def create_rule():
    """创建新规则并尝试发送 MQTT 命令"""
    user = get_user_from_jwt()
    data = request.get_json()

    required_fields = ['name', 'device_id', 'action']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "缺少必填字段: name, device_id, action"}), 400

    name = data['name']
    device_id = data.get('device_id')
    action = data.get('action')
    parameters = data.get('parameters', '') # 参数可以是字符串或 JSON 字符串

    if action not in DEVICE_ACTIONS:
        return jsonify({"error": f"无效的操作: {action}"}), 400

    # 验证设备是否存在
    device_node = Node.query.get(device_id)
    if not device_node:
         return jsonify({"error": f"设备 ID {device_id} 不存在"}), 404
    # 可选: 检查节点角色是否为设备
    if 'device' not in device_node.role.lower() and 'actuator' not in device_node.role.lower():
         logger.warning(f"Rule created for node {device_id} which might not be a device/actuator (role: {device_node.role})")


    # 构建 MQTT Topic 和 Payload (根据你的结构调整)
    # 示例: smart_home/api/device_name/action -> payload
    mqtt_topic = f"{current_app.config['MQTT_TOPIC_BASE']}/{device_node.name}/{action}"
    mqtt_payload = parameters if parameters else "" # 根据需要调整 payload 格式

    # --- 尝试发布 MQTT 消息 ---
    mqtt_service = current_app.mqtt_service # 获取 MQTT 服务实例
    publish_success = False
    publish_error = None
    if mqtt_service and mqtt_service.is_connected:
        publish_success = mqtt_service.publish(mqtt_topic, mqtt_payload)
        if not publish_success:
            publish_error = "发布 MQTT 消息失败 (可能连接已断开或 broker 拒绝)"
            logger.error(f"Failed to publish MQTT for new rule '{name}' to topic '{mqtt_topic}'")
    else:
        publish_error = "MQTT 服务未连接"
        logger.error("MQTT service not connected, cannot publish for new rule.")

    # --- 创建数据库记录 ---
    try:
        new_rule = Rule(
            name=name,
            device_id=device_id,
            action=action,
            parameters=parameters,
            user_id=user.id
        )
        db.session.add(new_rule)
        db.session.commit()

        response_data = new_rule.to_dict()
        response_data['mqtt_publish_status'] = 'success' if publish_success else 'failed'
        if publish_error:
             response_data['mqtt_publish_error'] = publish_error

        return jsonify(response_data), 201 # 201 Created

    except Exception as e:
        db.session.rollback()
        logger.exception(f"创建规则时数据库出错: {e}")
        return jsonify({"error": "创建规则时发生数据库错误"}), 500


@rules_bp.route('/<int:rule_id>', methods=['PUT'])
@jwt_required()
def update_rule(rule_id):
    """更新规则并尝试发送 MQTT 命令"""
    user = get_user_from_jwt()
    rule = Rule.query.get_or_404(rule_id)
    check_permission(rule, user)

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    # 更新字段
    rule.name = data.get('name', rule.name)
    new_device_id = data.get('device_id', rule.device_id)
    new_action = data.get('action', rule.action)
    new_parameters = data.get('parameters', rule.parameters)

    if new_action not in DEVICE_ACTIONS:
        return jsonify({"error": f"无效的操作: {new_action}"}), 400

    # 检查新设备 ID 是否存在
    device_node = Node.query.get(new_device_id)
    if not device_node:
         return jsonify({"error": f"设备 ID {new_device_id} 不存在"}), 404
    rule.device_id = new_device_id # 必须在查询后更新

    rule.action = new_action
    rule.parameters = new_parameters

    # 如果是管理员，且提供了 user_id，则更新所有者 (谨慎使用)
    if user.role == 'admin' and 'user_id' in data:
         new_owner_id = data['user_id']
         new_owner = User.query.get(new_owner_id)
         if not new_owner:
             return jsonify({"error": f"用户 ID {new_owner_id} 不存在"}), 404
         rule.user_id = new_owner_id


    # 构建 MQTT Topic 和 Payload
    mqtt_topic = f"{current_app.config['MQTT_TOPIC_BASE']}/{device_node.name}/{rule.action}"
    mqtt_payload = rule.parameters if rule.parameters else ""

    # --- 尝试发布 MQTT 消息 ---
    mqtt_service = current_app.mqtt_service
    publish_success = False
    publish_error = None
    if mqtt_service and mqtt_service.is_connected:
        # 决定是否在更新时也发送 MQTT 命令，这取决于业务需求
        # 如果更新规则只是修改定义，而不是立即触发，则注释掉 publish
        publish_success = mqtt_service.publish(mqtt_topic, mqtt_payload)
        if not publish_success:
            publish_error = "发布 MQTT 消息失败"
            logger.error(f"Failed to publish MQTT for updated rule '{rule.name}' to topic '{mqtt_topic}'")
    else:
        publish_error = "MQTT 服务未连接"
        logger.error("MQTT service not connected, cannot publish for updated rule.")


    # --- 更新数据库记录 ---
    try:
        db.session.commit()
        response_data = rule.to_dict()
        # 可以选择性地在响应中包含 MQTT 发布状态
        # response_data['mqtt_publish_status'] = 'success' if publish_success else 'failed'
        # if publish_error:
        #     response_data['mqtt_publish_error'] = publish_error
        return jsonify(response_data), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"更新规则时数据库出错: {e}")
        return jsonify({"error": "更新规则时发生数据库错误"}), 500

@rules_bp.route('/<int:rule_id>', methods=['DELETE'])
@jwt_required()
def delete_rule(rule_id):
    """删除规则"""
    user = get_user_from_jwt()
    rule = Rule.query.get_or_404(rule_id)
    check_permission(rule, user)

    try:
        db.session.delete(rule)
        db.session.commit()
        return '', 204 # 204 No Content
    except Exception as e:
        db.session.rollback()
        logger.exception(f"删除规则时数据库出错: {e}")
        return jsonify({"error": "删除规则时发生数据库错误"}), 500

# 可选：触发规则执行 (如果规则不只是设备控制，而是复杂逻辑)
# @rules_bp.route('/<int:rule_id>/trigger', methods=['POST'])
# @jwt_required()
# def trigger_rule(rule_id):
#     # ... 获取规则，检查权限 ...
#     # ... 执行规则逻辑 (可能涉及 MQTT 或其他服务) ...
#     return jsonify({"message": "规则已触发"}), 200