import time

from flask import Blueprint, request, jsonify, render_template, url_for, flash, redirect, session, current_app, \
    get_flashed_messages
from models import db, Node, Rule
import datetime
import secrets
import uuid  # 导入 uuid 模块

from utils.agent.mqtt_subscribe import MqttSubscriber, process_sensor_data
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
    data = request.form  # 使用 request.form 而不是 request.get_json()
    if not data:
        flash('Bad Request: 没有提供输入数据', 'danger')
        return redirect(url_for('node.dashboard'))

    # 1. 数据验证 (检查必要的字段是否存在且有效)
    required_fields = ['ip_address', 'port', 'role', 'protocols']  # name 不再是必需的
    for field in required_fields:
        if field not in data or not data.get(field):  # 使用 .get() 避免 KeyError
            flash(f'Bad Request: 缺少或空值必需字段: {field}', 'danger')
            return redirect(url_for('node.dashboard'))

    try:
        port = int(data['port'])
        if port < 1 or port > 65535:  # 检查端口范围
            flash('Bad Request: 端口必须是1-65535之间的整数', 'danger')
            return redirect(url_for('node.dashboard'))
    except ValueError:
        flash('Bad Request: 端口必须是整数', 'danger')
        return redirect(url_for('node.dashboard'))

    valid_roles = ['ingress', 'egress', 'both']
    if data['role'] not in valid_roles:
        flash(f'Bad Request: 无效的角色。必须是以下之一: {", ".join(valid_roles)}', 'danger')
        return redirect(url_for('node.dashboard'))


    # 2. 检查是否已注册 (根据 IP 地址和端口)
    existing_node = Node.query.filter_by(ip_address=data['ip_address'], port=port).first()
    if existing_node:
        # 更新信息
        existing_node.name = data.get('name', str(uuid.uuid4())) #更新name，如果没有就生成uuid
        existing_node.role = data['role']
        existing_node.protocols = data['protocols']
        #  安全地处理 secret_key 更新! (考虑一个单独的、更安全的端点)
        existing_node.secret_key = data.get('secret_key', existing_node.secret_key) #如果没有输入就使用旧的
        existing_node.status = "online"
        existing_node.last_heartbeat = datetime.datetime.utcnow()
        existing_node.last_modified = datetime.datetime.utcnow()  # 记录修改时间
        db.session.commit()
        flash('节点已更新', 'success')
        return redirect(url_for('node.dashboard'))

    # 3. 创建新节点
    new_node = Node(
        name=data.get('name', str(uuid.uuid4())),  # 使用 UUID 生成节点名称
        ip_address=data['ip_address'],
        port=port,
        role=data['role'],
        protocols=data['protocols'],
        secret_key=data.get('secret_key', secrets.token_urlsafe(16)),  # 如果未提供，则安全生成
        last_heartbeat=datetime.datetime.utcnow(),
        status="online"  # 或 'pending'，取决于初始设置
    )
    db.session.add(new_node)

    try:
        db.session.commit()
        flash('节点已注册', 'success')
        return redirect(url_for('node.dashboard'))
    except Exception as e:
        db.session.rollback()
        flash(f'数据库错误: {str(e)}', 'danger')
        return redirect(url_for('node.dashboard'))

@node_bp.route('/node/config/<int:node_id>', methods=['GET'])
def config(node_id):
    """获取节点配置"""
    try:
        node = Node.query.get_or_404(node_id)
    except Exception as e:  # 捕获可能的数据库查询错误
        flash(f'服务器内部错误: {str(e)}', 'danger')
        return redirect(url_for('node.dashboard'))

    # 验证 secret_key
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        flash('未授权', 'danger')
        return redirect(url_for('node.dashboard'))

    # 获取适用于该节点的规则
    if node.role == "ingress" or node.role == "both":
        rules = Rule.query.filter(Rule.entry_node_id == None).all()  # 更正后的筛选
    elif node.role == "egress" or node.role == "both":
        rules = Rule.query.filter(Rule.entry_node_id != None).all()  # 更正后的筛选
    else:
        flash("Bad Request: 节点角色错误", 'danger')
        return redirect(url_for('node.dashboard'))

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
def send_command_route(node_id):
    """
    向节点发送命令。

    该 API 接受 POST 请求，其中请求体应该包含 JSON 格式的数据，
    包含一个名为 'command' 的字段。
    """
    # 1. 检查节点是否存在
    node = Node.query.get_or_404(node_id)

    # 2. 验证授权
    secret_key = session.get('secret_key')
    if not secret_key or secret_key != current_app.config['SECRET_KEY']:
        print(f"Unauthorized access attempt for node {node_id} from {request.remote_addr}")  # 记录未授权尝试
        return jsonify({'status': 'error', 'message': '未授权'}), 401  # 401 Unauthorized

    # 3. 获取并解析 JSON 数据
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({'status': 'error', 'message': "无效的 JSON 数据：需要包含 'command' 字段"}), 400  # 400 Bad Request
        command = data['command']
        #print(f"节点 {node.name} 收到命令: {command}")

    except (TypeError, ValueError) as e:  # 捕获 JSON 解析错误
        print(f"JSON parsing error: {e}")
        return jsonify({'status': 'error', 'message': '无效的请求数据或 JSON 格式错误'}), 400  # 400 Bad Request

    # 4. 发送命令并处理响应
    try:
        agent_response_data = send_command(node, command)  # 假设 send_command 在其他地方定义

        if not agent_response_data:
            agent_response_data = {}  # 避免 NoneType 错误

        if agent_response_data.get('success'):
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
                # db.session.delete(node)  # 如果是删除，可能需要在另一处处理节点的删除
            db.session.commit()
            return jsonify({'status': 'success', 'message': message, 'category': 'success'}), 200  # 200 OK
        else:
            message = agent_response_data.get('message', "命令执行失败") + ". " + agent_response_data.get('error', "")
            return jsonify({'status': 'error', 'message': message, 'category': 'danger'}), 200 #  或其他适当的状态码，通常是 200
    except Exception as e:  # 捕获 send_command 过程中可能发生的异常
        db.session.rollback() # 回滚数据库操作，防止数据不一致
        print(f"Error sending command to agent: {e}")
        return jsonify({'status': 'error', 'message': f"发送命令时发生错误: {e}", 'category': 'danger'}), 500  # 500 Internal Server Error

@node_bp.route('/node/command/test/<int:node_id>', methods=['POST'])
def send_command_route_test(node_id):
    """
    向节点发送命令。

    该 API 接受 POST 请求，其中请求体应该包含 JSON 格式的数据，
    包含一个名为 'command' 的字段。

    错误处理：
    *   如果请求方法不是 POST，返回 405 Method Not Allowed。
    *   如果未授权（session 中没有 secret_key 或者 secret_key 不匹配），
        重定向到控制面板。
    *   如果 JSON 解析失败，返回 400 Bad Request。
    *   如果 JSON 中缺少 'command' 字段，返回 400 Bad Request。
    *   如果在发送命令过程中发生错误，或者 agent 返回错误信息，
        显示警告消息，并重定向到控制面板。
    *   成功时，显示成功消息，并重定向到控制面板。
    """
    # 1. 检查节点是否存在
    node = Node.query.get_or_404(node_id)

    # 2. 验证授权
    secret_key = session.get('secret_key')
    if not secret_key or secret_key != current_app.config['SECRET_KEY']:
        print(f"Unauthorized access attempt for node {node_id} from {request.remote_addr}")  # 记录未授权尝试
        flash('未授权', 'danger')
        return redirect(url_for('node.control_panel', node_id=node_id))

    # 3. 获取并解析 JSON 数据
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            flash("无效的 JSON 数据：需要包含 'command' 字段", 'danger')
            return redirect(url_for('node.control_panel', node_id=node.id))
        command = data['command']
        print(f"节点 {node.name} 收到命令: {command}")

    except (TypeError, ValueError) as e: # 捕获 JSON 解析错误
        print(f"JSON parsing error: {e}")
        flash('无效的请求数据或 JSON 格式错误', 'danger')
        return redirect(url_for('node.control_panel', node_id=node.id))


    # 4. 发送命令并处理响应
    try:
        agent_response_data = send_command(node, command)  # 假设 send_command 在其他地方定义
        if not agent_response_data:
            agent_response_data = {}  # 避免 NoneType 错误

        if agent_response_data.get('success'):
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
            flash(message, 'success')
        else:
            message = agent_response_data.get('message', "命令执行失败") + ". " + agent_response_data.get('error', "")
            flash(message, 'danger')

    except Exception as e: # 捕获 send_command 过程中可能发生的异常
        print(f"Error sending command to agent: {e}")
        flash(f"发送命令时发生错误: {e}", 'danger') # 更友好的错误信息
        agent_response_data = {} # 避免后续代码出错

    # 5. 将 agent 响应存储在 session 中（可选）
    session['agent_response'] = agent_response_data  # 存储 agent 响应以便在模板中显示
    messages = get_flashed_messages(with_categories=True)  # 获取 flash 消息
    # 6. 重定向到控制面板
    return redirect(url_for('node.control_panel', node_id=node.id, messages=messages))

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
        flash('未授权', 'danger')
        return redirect(url_for('node.dashboard'))

    # 2. 获取请求数据
    data = request.form  # 使用 request.form 而不是 request.get_json()
    if not data:
        flash('Bad Request: 没有提供数据', 'danger')
        return redirect(url_for('node.dashboard'))

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
                    flash(f'Bad Request: 无效状态。必须是以下之一: {", ".join(valid_statuses)}', 'danger')
                    return redirect(url_for('node.dashboard'))
                node.status = value
            elif key == 'name':
                node.name = value #更新name
            else:
                setattr(node, key, value)  # 使用 setattr 动态设置属性

    # 4. 记录修改时间
    node.last_modified = datetime.datetime.utcnow()

    # 5. 提交数据库更改
    try:
        db.session.commit()
        flash('节点更新成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败: {str(e)}', 'danger')
    return redirect(url_for('node.dashboard'))

@node_bp.route('/node/add_node_form', methods=['GET'])
def add_node_form():
    """呈现添加节点的表单"""
    return render_template('add_node_form.html')

@node_bp.route('/node/list_node_form', methods=['GET'])
def list_node_form():
    return render_template('device_list_info.html')

@node_bp.route('/node/test/get_sensor1', methods=['GET'])
def get_sensor():
    """呈现添加节点的表单，并获取 MQTT 数据"""

    # 使用一个内部类来封装 MQTT 客户端和数据处理
    class DataFetcher:
        def __init__(self):
            self.temperature = None
            self.humidity = None
            self.data_received = False
            self.last_update_time = None

        def fetch_data(self):
            def callback_with_return(data):
                """内部回调函数，用于处理数据并设置 DataFetcher 的属性"""
                result = process_sensor_data(data)
                if result:
                    self.temperature, self.humidity, self.data_received = result
                    self.last_update_time = time.time()

            subscriber = MqttSubscriber(
                broker_host="10.1.0.177",
                broker_port=11883,
                topic="/test/sensor1",
                callback=callback_with_return  # 使用内部回调
            )
            subscriber.start()
            subscriber.wait_for_messages(10)
            subscriber.stop()

            if self.last_update_time is not None and time.time() - self.last_update_time > 15:
                self.data_received = False
                self.temperature = None
                self.humidity = None

    # 创建 DataFetcher 实例并获取数据
    fetcher = DataFetcher()
    fetcher.fetch_data()

    # 构建并返回 JSON 响应
    return jsonify({
        'temperature': fetcher.temperature,
        'humidity': fetcher.humidity,
        'data_received': fetcher.data_received
    })

def register_node_blueprint(app):
    """注册节点蓝图"""
    app.register_blueprint(node_bp)