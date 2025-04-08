import logging
import datetime
import secrets
import uuid
from flask import Blueprint, request, jsonify, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Node, Rule, User
from core.agent_service import send_command_to_agent # 导入你的 Agent 通信函数

nodes_bp = Blueprint('nodes', __name__, url_prefix='/api/nodes')
logger = logging.getLogger(__name__)

# --- 辅助函数 ---
def get_user_from_jwt():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        abort(401, description="无效的用户 Token")
    return user

def verify_node_secret(node_id):
    """验证请求头中的 X-Secret-Key 是否与节点匹配"""
    node = Node.query.get_or_404(node_id)
    secret_key_header = request.headers.get('X-Secret-Key')
    if not secret_key_header or secret_key_header != node.secret_key:
        logger.warning(f"Node {node_id}: Unauthorized access attempt with key '{secret_key_header}' from {request.remote_addr}")
        abort(401, description="无效的节点 Secret Key")
    return node

# --- API 路由 (供前端 UI 使用 - 通常需要 JWT 认证) ---

@nodes_bp.route('', methods=['GET'])
@jwt_required()
def list_nodes():
    """获取所有节点的列表 (供 UI 显示)"""
    user = get_user_from_jwt() # 确保用户已登录
    nodes = Node.query.all()
    # UI 通常不需要显示 Secret Key
    return jsonify([node.to_dict(include_secret=(user.role == 'admin')) for node in nodes]), 200 # 管理员可见密钥

@nodes_bp.route('/<int:node_id>', methods=['GET'])
@jwt_required()
def get_node(node_id):
    """获取单个节点详情 (供 UI 显示)"""
    user = get_user_from_jwt()
    node = Node.query.get_or_404(node_id)
    # UI 通常不需要显示 Secret Key
    return jsonify(node.to_dict(include_secret=(user.role == 'admin'))), 200

@nodes_bp.route('', methods=['POST'])
@jwt_required()
def create_node():
    """创建新节点 (通常由管理员通过 UI 操作)"""
    user = get_user_from_jwt()
    if user.role != 'admin':
        abort(403, description="只有管理员才能创建节点")

    data = request.get_json()
    required_fields = ['ip_address', 'port', 'role'] # name 和 protocols 可选
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "缺少必填字段: ip_address, port, role"}), 400

    ip_address = data['ip_address']
    port = data.get('port')
    role = data['role']
    name = data.get('name', f"Node-{str(uuid.uuid4())[:8]}") # 默认名称
    protocols = data.get('protocols', '')
    secret_key = data.get('secret_key', secrets.token_urlsafe(16)) # 允许指定或自动生成

    try:
        port = int(port)
        if not (1 <= port <= 65535):
             raise ValueError("端口超出范围")
    except (ValueError, TypeError):
        return jsonify({"error": "端口必须是 1-65535 之间的整数"}), 400

    # 检查 IP 和端口是否已存在
    existing_node = Node.query.filter_by(ip_address=ip_address, port=port).first()
    if existing_node:
        return jsonify({"error": f"节点 {ip_address}:{port} 已存在"}), 409 # Conflict

    try:
        new_node = Node(
            name=name,
            ip_address=ip_address,
            port=port,
            role=role,
            protocols=protocols,
            secret_key=secret_key,
            status='pending' # 新节点初始状态
        )
        db.session.add(new_node)
        db.session.commit()
        logger.info(f"Admin '{user.username}' created node '{new_node.name}' ({new_node.id})")
        # 返回包含密钥，因为是管理员操作
        return jsonify(new_node.to_dict(include_secret=True)), 201
    except Exception as e:
        db.session.rollback()
        logger.exception(f"创建节点时数据库出错: {e}")
        return jsonify({"error": "创建节点时发生数据库错误"}), 500

@nodes_bp.route('/<int:node_id>', methods=['PUT'])
@jwt_required()
def update_node(node_id):
    """更新节点信息 (通常由管理员通过 UI 操作)"""
    user = get_user_from_jwt()
    if user.role != 'admin':
        abort(403, description="只有管理员才能修改节点")

    node = Node.query.get_or_404(node_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    allowed_fields = ['name', 'role', 'protocols', 'secret_key', 'status']
    updated = False
    for key, value in data.items():
        if key in allowed_fields and hasattr(node, key):
            # 添加验证逻辑
            if key == 'status':
                 valid_statuses = ['online', 'offline', 'suspended', 'error', 'pending', 'deleted']
                 if value not in valid_statuses:
                     return jsonify({"error": f"无效的状态值: {value}"}), 400
            elif key == 'secret_key' and not value: # 不允许空密钥
                 return jsonify({"error": "Secret Key 不能为空"}), 400

            setattr(node, key, value)
            updated = True

    if updated:
        try:
            # node.last_modified 会自动更新 (如果模型配置了 onupdate)
            db.session.commit()
            logger.info(f"Admin '{user.username}' updated node '{node.name}' ({node.id})")
             # 返回包含密钥，因为是管理员操作
            return jsonify(node.to_dict(include_secret=True)), 200
        except Exception as e:
            db.session.rollback()
            logger.exception(f"更新节点时数据库出错: {e}")
            return jsonify({"error": "更新节点时发生数据库错误"}), 500
    else:
        return jsonify({"message": "未提供可更新的字段"}), 400 # Or 200 OK with message?

@nodes_bp.route('/<int:node_id>', methods=['DELETE'])
@jwt_required()
def delete_node(node_id):
    """删除节点 (通常由管理员通过 UI 操作)"""
    user = get_user_from_jwt()
    if user.role != 'admin':
        abort(403, description="只有管理员才能删除节点")

    node = Node.query.get_or_404(node_id)

    try:
        # 考虑：是否需要先停止 Agent 或执行其他清理操作？
        # 考虑：关联的规则如何处理？(级联删除或置空?) - 取决于模型关系设置
        db.session.delete(node)
        db.session.commit()
        logger.info(f"Admin '{user.username}' deleted node '{node.name}' ({node.id})")
        return '', 204
    except Exception as e:
        db.session.rollback()
        logger.exception(f"删除节点时数据库出错: {e}")
        # 可能有外键约束阻止删除
        return jsonify({"error": f"删除节点时发生错误: {e}"}), 500

@nodes_bp.route('/<int:node_id>/command', methods=['POST'])
@jwt_required()
def send_command_api(node_id):
    """向节点 Agent 发送命令 (由登录用户通过 UI 触发)"""
    user = get_user_from_jwt() # 验证用户身份
    node = Node.query.get_or_404(node_id)

    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({"error": "请求体需要包含 'command' 字段"}), 400
    command = data['command']

    # --- 调用 Agent 服务 ---
    agent_response = send_command_to_agent(
        node.ip_address,
        node.port,
        node.secret_key, # 需要节点的 Secret Key
        command
    )
    # --- 处理 Agent 响应 ---
    status_code = 200 # 默认成功响应码
    response_body = {"agent_response": agent_response}

    if agent_response.get('success'):
        # 根据命令更新节点状态 (可选)
        status_changed = False
        original_status = node.status
        if command in ('start', 'restart', 'resume'):
            node.status = 'online'
            status_changed = True
        elif command == 'stop':
            node.status = 'offline'
            status_changed = True
        elif command == 'suspend':
            node.status = 'suspended'
            status_changed = True
        # elif command == 'delete': # 删除命令可能更复杂
        #     node.status = 'deleted'
        #     status_changed = True

        if status_changed and node.status != original_status:
            try:
                db.session.commit()
                response_body["node_status_updated"] = node.status
                logger.info(f"User '{user.username}' sent command '{command}' to node {node.id}, status updated to '{node.status}'")
            except Exception as e:
                 db.session.rollback()
                 logger.exception(f"命令发送成功但更新节点状态失败: {e}")
                 response_body["node_status_update_error"] = str(e)
                 # 即使状态更新失败，命令本身可能成功了，仍返回 200
    else:
        # Agent 返回失败，或通信失败
        logger.error(f"User '{user.username}' failed to send command '{command}' to node {node.id}. Agent response: {agent_response}")
        # 可以考虑根据错误类型返回不同的状态码，例如 502 Bad Gateway (如果 Agent 不可用)
        # 但为了简化，这里仍用 200，在响应体中表明失败
        status_code = 200 # 或者 400 Bad Request / 500 Internal Server Error ?

    return jsonify(response_body), status_code


# --- API 路由 (供节点 Agent 使用 - 需要节点 Secret Key 认证) ---

@nodes_bp.route('/heartbeat/<int:node_id>', methods=['POST'])
def node_heartbeat(node_id):
    """接收节点 Agent 的心跳信号"""
    node = verify_node_secret(node_id) # 验证 X-Secret-Key

    # 更新心跳时间和状态
    node.last_heartbeat = datetime.datetime.utcnow()
    if node.status != 'online': # 只有在非 online 状态下才自动设为 online
        logger.info(f"Node {node_id} ('{node.name}') status changed to 'online' due to heartbeat.")
        node.status = 'online'

    # 可选：处理 Agent 发送的其他状态信息
    data = request.get_json()
    if data:
         # 例如，更新 agent 报告的协议或负载信息 (如果模型中有相应字段)
         # if 'reported_protocols' in data: node.reported_protocols = data['reported_protocols']
         pass

    try:
        db.session.commit()
        return jsonify({"message": "Heartbeat received"}), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"处理节点 {node_id} 心跳时数据库出错: {e}")
        return jsonify({"error": "处理心跳时发生内部错误"}), 500

@nodes_bp.route('/config/<int:node_id>', methods=['GET'])
def node_config(node_id):
    """向节点 Agent 提供其配置信息 (例如相关的规则)"""
    node = verify_node_secret(node_id) # 验证 X-Secret-Key

    # 根据节点角色查找相关规则 (这里的逻辑可能需要根据你的具体需求调整)
    # 示例：如果节点是设备 (actuator)，提供控制它的规则？
    # 示例：如果节点是网关 (ingress/egress)，提供需要它处理的规则？
    # 这个示例查找所有将此节点作为 device_id 的规则
    relevant_rules = Rule.query.filter_by(device_id=node.id).all()

    config_data = {
        'node': { # 发送给节点的基本信息 (不含密钥)
            'id': node.id,
            'name': node.name,
            'role': node.role,
        },
        'rules': [rule.to_dict() for rule in relevant_rules] # 发送规则详情
        # 可以添加其他需要的配置项
        # 'mqtt_config': { ... }
    }

    logger.info(f"Providing config for node {node_id} ('{node.name}')")
    return jsonify(config_data), 200