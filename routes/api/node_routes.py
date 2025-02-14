from flask import Blueprint, request, jsonify, render_template, url_for
from models import db, Node, Rule
import datetime
import secrets
import uuid  # 导入 uuid 模块
from utils.agent.send_command import send_command

node_bp = Blueprint('node', __name__)

@node_bp.route('/node/dashboard')
def dashboard():
    """节点仪表盘视图"""
    nodes = Node.query.all()
    return render_template('combined_node.html', nodes=nodes, page_type='dashboard')  # 传递 page_type

@node_bp.route('/node/create', methods=['POST'])
def register_node():
    """注册或更新节点"""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Bad Request: 没有提供输入数据'}), 400

    # 1. 数据验证 (检查必要的字段是否存在且有效)
    required_fields = ['ip_address', 'port', 'role', 'protocols', 'secret_key']  # name 不再是必需的
    for field in required_fields:
        if field not in data or not data.get(field):  # 使用 .get() 避免 KeyError
            return jsonify({'message': f'Bad Request: 缺少或空值必需字段: {field}'}), 400

    if not isinstance(data['port'], int):
        return jsonify({'message': 'Bad Request: 端口必须是整数'}), 400

    valid_roles = ['ingress', 'egress', 'both']
    if data['role'] not in valid_roles:
        return jsonify({'message': f'Bad Request: 无效的角色。必须是以下之一: {", ".join(valid_roles)}'}), 400


    # 2. 检查是否已注册 (根据 IP 地址和端口)
    existing_node = Node.query.filter_by(ip_address=data['ip_address'], port=data['port']).first()
    if existing_node:
        # 更新信息
        existing_node.name = data.get('name', str(uuid.uuid4())) #更新name，如果没有就生成uuid
        existing_node.role = data['role']
        existing_node.protocols = data['protocols']
        #  安全地处理 secret_key 更新! (考虑一个单独的、更安全的端点)
        existing_node.secret_key = data['secret_key']
        existing_node.status = "online"
        existing_node.last_heartbeat = datetime.datetime.utcnow()
        existing_node.last_modified = datetime.datetime.utcnow()  # 记录修改时间
        db.session.commit()
        return jsonify({'message': '节点已更新', 'node_id': existing_node.id}), 200

    # 3. 创建新节点
    new_node = Node(
        name=str(uuid.uuid4()),  # 使用 UUID 生成节点名称
        ip_address=data['ip_address'],
        port=data['port'],
        role=data['role'],
        protocols=data['protocols'],
        secret_key=data.get('secret_key', secrets.token_urlsafe(16)),  # 如果未提供，则安全生成
        last_heartbeat=datetime.datetime.utcnow(),
        status="online"  # 或 'pending'，取决于初始设置
    )
    db.session.add(new_node)

    try:
        db.session.commit()
        return jsonify({'message': '节点已注册', 'node_id': new_node.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'数据库错误: {str(e)}'}), 500

@node_bp.route('/node/config/<int:node_id>', methods=['GET'])
def config(node_id):
    """获取节点配置"""
    try:
        node = Node.query.get_or_404(node_id)
    except Exception as e:  # 捕获可能的数据库查询错误
        return jsonify({'message': f'服务器内部错误: {str(e)}'}), 500

    # 验证 secret_key
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': '未授权'}), 401

    # 获取适用于该节点的规则
    if node.role == "ingress" or node.role == "both":
        rules = Rule.query.filter(Rule.entry_node_id == None).all()  # 更正后的筛选
    elif node.role == "egress" or node.role == "both":
        rules = Rule.query.filter(Rule.entry_node_id != None).all()  # 更正后的筛选
    else:
        return jsonify({'message': "Bad Request: 节点角色错误"}), 400

    # 构建 JSON 响应
    config_data = {
        'page_type': 'config',
        'node': {
            'id': node.id,
            'ip_address': node.ip_address,
            'port': node.port,
            'role': node.role,
            'protocols': node.protocols,
            # 'secret_key': node.secret_key,  # 不要返回 SECRET KEY!
            'status': node.status,
            'last_heartbeat': None,  # 将在下面格式化
        },
        'rules': [
            {
                'id': rule.id,
                'name': rule.name,
                'source': rule.source,
                'destination': rule.destination,
                'protocol': rule.protocol,
                'node_id': rule.node_id,  # 使用 node_id
            }
            for rule in rules
        ]
    }

    # 格式化时间戳 (UTC)
    if node.last_heartbeat:
        config_data['node']['last_heartbeat'] = node.last_heartbeat.isoformat() + 'Z'

    return jsonify(config_data), 200

@node_bp.route('/node/control/<int:node_id>')
def control_panel(node_id):
    """节点控制面板视图"""
    node = Node.query.get_or_404(node_id)
    return render_template('combined_node.html', node=node, page_type='control')  # 传递 page_type

@node_bp.route('/node/heartbeat/<int:node_id>', methods=['POST'])
def heartbeat(node_id):
    """节点心跳"""
    node = Node.query.get_or_404(node_id)
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
         return jsonify({'message': '未授权'}), 401

    data = request.get_json()  # 可以上传一些节点信息

    # 更新心跳
    node.last_heartbeat = datetime.datetime.utcnow()
    node.status = 'online'
    # 可以根据 'data' 更新其他信息，如负载等。
    db.session.commit()
    return jsonify({'message': '已收到心跳'})

@node_bp.route('/node/command/<int:node_id>', methods=['POST'])
def send_command_route(node_id):  # 重命名以避免名称冲突
    """向节点发送命令"""
    node = Node.query.get_or_404(node_id)
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': '未授权'}), 401

    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({'message': 'Bad Request: 缺少命令'}), 400

    command = data['command']
    agent_response_data = send_command(node, command)  # 假设 send_command 在其他地方定义

    if agent_response_data and agent_response_data.get('success'):
        message = agent_response_data.get('message', "命令执行成功")
        # 根据命令结果更新节点状态
        if command in ('start', 'restart'):
            node.status = 'online'
        elif command == 'stop':
            node.status = 'offline'
        elif command == 'suspend':
            node.status = 'suspended'
        elif command == 'delete':  # 如果有删除节点的命令
            node.status = 'deleted'
        db.session.commit()
    else:
        message = agent_response_data.get('message', "命令执行失败") + ". " + agent_response_data.get('error', "")

    return jsonify({'message': message, 'status': node.status, 'agent_response': agent_response_data}), 200

@node_bp.route('/node/update_form/<int:node_id>', methods=['GET'])
def update_form(node_id):
    """呈现更新节点表单"""
    node = Node.query.get_or_404(node_id)
    return render_template('update_node_form.html', node=node)

@node_bp.route('/node/update/<int:node_id>', methods=['POST'])
def update_node(node_id):
    """更新节点信息"""
    node = Node.query.get_or_404(node_id)

    # 1. 身份验证
    secret_key = request.form.get('secret_key')  # 从表单数据中获取 X-Secret-Key
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': '未授权'}), 401

    # 2. 获取请求数据
    data = request.form  # 使用 request.form 而不是 request.get_json()
    if not data:
        return jsonify({'message': 'Bad Request: 没有提供数据'}), 400

    # 3. 数据验证和更新
    # 允许更新的字段
    allowed_fields = ['name', 'role', 'protocols', 'secret_key', 'status']  # 允许状态更新
    for key, value in data.items():
        if key in allowed_fields:
            if key == 'secret_key':
                # 安全地处理密钥更新 (考虑一个单独的、更安全的端点)
                node.secret_key = value
            elif key == 'status':
                # 验证状态更新
                valid_statuses = ['online', 'offline', 'suspended', 'deleted']
                if value not in valid_statuses:
                    return jsonify({'message': f'Bad Request: 无效状态。必须是以下之一: {", ".join(valid_statuses)}'}), 400
                node.status = value
            elif key == 'name':
                node.name = value #更新name
            else:
                setattr(node, key, value)  # 使用 setattr 动态设置属性

    # 4. 记录修改时间
    node.last_modified = datetime.datetime.utcnow()

    # 5. 提交数据库更改
    db.session.commit()

    return jsonify({
        'message': '节点更新成功',
        'node_id': node.id,
        'redirect_url': url_for('node.dashboard')  # 为前端添加 redirect_url
    }), 200

def register_node_blueprint(app):
    """注册节点蓝图"""
    app.register_blueprint(node_bp)