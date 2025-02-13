import requests
from flask import Blueprint, request, jsonify, render_template, abort, redirect, url_for
from models import db, Node, Rule
import datetime, secrets

from routes.utils.send_command import send_command

node_bp = Blueprint('node', __name__)

@node_bp.route('/node/dashboard')
def dashboard():
    nodes = Node.query.all()
    return render_template('combined_node.html', nodes=nodes, page_type='dashboard') # 传递 page_type

@node_bp.route('/node/create', methods=['POST'])
def register_node():
    data = request.get_json()
    # 1. 数据验证 (检查必要的字段是否存在)
    if not all(key in data for key in ['ip_address', 'port', 'role', 'protocols', 'secret_key']):
        return jsonify({'message': 'Bad Request: Missing required fields'}), 400

    # 2. 检查是否已注册 (根据 IP 地址和端口)
    existing_node = Node.query.filter_by(ip_address=data['ip_address'], port=data['port']).first()
    if existing_node: #如果存在
        # 更新信息
        existing_node.role = data['role']
        existing_node.protocols = data['protocols']
        existing_node.secret_key = data['secret_key'] # 应该允许节点更新密钥
        existing_node.status = "online"
        existing_node.last_heartbeat = datetime.datetime.utcnow()
        existing_node.last_modified = datetime.datetime.utcnow()  # 记录修改时间
        db.session.commit()
        return jsonify({'message': 'Node updated', 'node_id': existing_node.id}), 200


    # 3. 创建新节点
    new_node = Node(
        ip_address=data['ip_address'],
        port=data['port'],
        role=data['role'],
        protocols=data['protocols'],
        secret_key=data['secret_key'],  # 应该使用更安全的方式生成密钥
        last_heartbeat=datetime.datetime.utcnow(),
        status = "online"
    )
    db.session.add(new_node)
    db.session.commit()
    return jsonify({'message': 'Node registered', 'node_id': new_node.id}), 201

@node_bp.route('/node/config/<int:node_id>', methods=['GET'])
def config(node_id):
    try:
        node = Node.query.get_or_404(node_id)
    except Exception as e:  # 捕获可能的数据库查询错误
        return jsonify({'message': f'Internal Server Error: {str(e)}'}), 500

    # 验证 secret_key
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': 'Unauthorized'}), 401

    # 获取适用于该节点的规则
    if node.role == "ingress" or node.role == "both":
        # rules = Rule.query.filter_by(server_id=None).all()  # 获取所有入口规则 # Old line with server_id
        rules = Rule.query.filter(Rule.node_id == None).all() # Get ingress rules, using node_id
    elif node.role == "egress" or node.role == "both":
        # rules = Rule.query.filter(Rule.server_id != None).all()  # 获取所有出口规则 # Old line with server_id
        rules = Rule.query.filter(Rule.node_id != None).all() # Get egress rules, using node_id
    else:
        return jsonify({'message': "Bad Request: node role error"}), 400

    # 构建 JSON 响应
    config_data = {
        'page_type': 'config',
        'node': {  # 将 Node 对象转换为字典
            'id': node.id,
            'ip_address': node.ip_address,
            'port': node.port,
            'role': node.role,
            'protocols': node.protocols,
            'secret_key': node.secret_key,  # 密钥不能泄露
            'status': node.status,  # 包含状态
            'last_heartbeat': None,
        },
        'rules': [
            {
                'id': rule.id,
                'name': rule.name,
                'source': rule.source,
                'destination': rule.destination,
                'protocol': rule.protocol,
                # 'server_id': rule.server_id, # Old line with server_id
                'node_id': rule.node_id, # Use node_id instead of server_id
            }
            for rule in rules
        ]
    }

    # 格式化时间戳 (UTC)
    if node.last_heartbeat:
        config_data['node']['last_heartbeat'] = node.last_heartbeat.isoformat() + 'Z'  #  例如： 2025-02-12T17:30:32Z

    return jsonify(config_data), 200  # 返回 JSON 响应

@node_bp.route('/node/control/<int:node_id>')
def control_panel(node_id):
    node = Node.query.get_or_404(node_id)
    return render_template('combined_node.html', node=node, page_type='control') # 传递 page_type


@node_bp.route('/node/heartbeat/<int:node_id>', methods=['POST'])
def heartbeat(node_id):
    node = Node.query.get_or_404(node_id)
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
         return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json() #可以上传一些节点信息

    # 更新心跳时间
    node.last_heartbeat = datetime.datetime.utcnow()
    node.status = 'online'
    # 可以根据data更新其他信息，如负载等
    db.session.commit()
    return jsonify({'message': 'Heartbeat received'})



@node_bp.route('/node/command/<int:node_id>', methods=['POST'])
def send_command(node_id):
    node = Node.query.get_or_404(node_id)
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({'message': 'Bad Request: Missing command'}), 400

    command = data['command']

    agent_response_data = send_command(node, command)

    if agent_response_data and agent_response_data.get('success'):
        message = agent_response_data.get('message', "Command executed successfully")
        # 根据被控端命令结果，更新节点状态
        if command == 'start' or command == 'restart':
            node.status = 'online'
        elif command == 'stop':
            node.status = 'offline'
        elif command == 'suspend':
            node.status = 'suspended'
        elif command == 'delete':
            node.status = 'deleted'
        db.session.commit()  # 提交状态更新
    else:
        message = agent_response_data.get('message', "Command execution failed") + ". " + agent_response_data.get('error', "")
        # 可以考虑根据命令类型和错误信息更新节点状态，例如命令是 stop 且执行失败，可能需要将节点状态标记为 error

    return jsonify({'message': message, 'status': node.status, 'agent_response': agent_response_data}), 200

@node_bp.route('/node/update_form/<int:node_id>', methods=['GET']) #  新增 GET 路由
def update_form(node_id):
    node = Node.query.get_or_404(node_id)
    return render_template('update_node_form.html', node=node)  # 渲染修改节点信息的表单

@node_bp.route('/node/update/<int:node_id>', methods=['POST'])
def update_node(node_id):
    node = Node.query.get_or_404(node_id)

    # 1. 身份验证
    secret_key = request.form.get('secret_key_header')  # 从表单数据中获取 X-Secret-Key
    if not secret_key or secret_key != node.secret_key:  # 使用节点的 secret_key
        return jsonify({'message': 'Unauthorized'}), 401

    # 2. 获取请求数据
    data = request.form  # 使用 request.form  代替  request.get_json()
    if not data:
        return jsonify({'message': 'Bad Request: No data provided'}), 400

    # 3. 数据验证和更新
    # 允许更新的字段
    allowed_fields = ['role', 'protocols', 'secret_key', 'status'] # 允许更新状态
    for key, value in data.items():
        if key in allowed_fields:
            if key == 'secret_key':
                # 密钥更新，应该有更安全的处理方式
                node.secret_key = value
            elif key == 'status': # 状态更新
                # 状态更新需要校验
                if value not in ['online', 'offline', 'suspended', 'deleted']:
                    return jsonify({'message': 'Bad Request: Invalid status'}), 400
                node.status = value
            else:
                setattr(node, key, value)  # 使用 setattr 动态设置属性

    # 4. 记录修改时间
    node.last_modified = datetime.datetime.utcnow()

    # 5. 提交数据库更改
    db.session.commit()

    return jsonify({
        'message': 'Node updated successfully',
        'node_id': node.id,
        'redirect_url': url_for('node.dashboard')  # 添加 redirect_url
    }), 200

def register_node_blueprint(app):
    app.register_blueprint(node_bp)