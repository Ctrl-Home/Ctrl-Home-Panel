from flask import Blueprint, request, jsonify
from models import db, Node, Rule
import datetime, secrets

node_bp = Blueprint('node', __name__)

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

@node_bp.route('/config/<int:node_id>', methods=['GET'])
def get_config(node_id):
    node = Node.query.get_or_404(node_id)
    # 验证 secret_key (防止未经授权的访问)
    secret_key = request.headers.get('X-Secret-Key')
    if not secret_key or secret_key != node.secret_key:
        return jsonify({'message': 'Unauthorized'}), 401
    # 获取适用于该节点的规则
    if node.role == "ingress" or node.role == "both":
        rules = Rule.query.filter_by(server_id = None).all() #获取所有入口规则
    elif node.role == "egress" or node.role == "both":
        rules = Rule.query.filter(Rule.server_id != None).all() #获取所有出口规则
    else:
         return jsonify({'message':"bad request: node role error"}), 400

    # 将规则转换为适合节点端使用的格式 (这里只是一个示例)
    config = {
        'rules': [{'name': r.name, 'source': r.source, 'destination': r.destination, 'protocol': r.protocol} for r in rules]
    }
    return jsonify(config)

@node_bp.route('/heartbeat/<int:node_id>', methods=['POST'])
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

# ... 其他 API (例如: 上报统计信息)