from flask import Blueprint, jsonify, request
from models import db, Rule, User, Server

rule_bp = Blueprint('rule', __name__)

@rule_bp.route('/', methods=['GET'])
def list_rules():
    rules = Rule.query.all()
    rule_list = []
    for rule in rules:
        rule_data = {
            'id': rule.id,
            'name': rule.name,
            'source': rule.source,
            'destination': rule.destination,
            'protocol': rule.protocol,
            'user_id': rule.user_id,
            'server_id': rule.server_id,
            'username': rule.user.username if rule.user else None, # 获取关联用户名
            'server_name': rule.server.name if rule.server else None # 获取关联服务器名
        }
        rule_list.append(rule_data)
    return jsonify(rules=rule_list)


@rule_bp.route('/<int:rule_id>', methods=['GET'])
def get_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    return jsonify({
        'id': rule.id,
        'name': rule.name,
        'source': rule.source,
        'destination': rule.destination,
        'protocol': rule.protocol,
        'user_id': rule.user_id,
        'server_id': rule.server_id,
        'username': rule.user.username if rule.user else None,
        'server_name': rule.server.name if rule.server else None
    })

@rule_bp.route('/', methods=['POST'])
def create_rule():
    data = request.get_json()
    if not data or 'name' not in data or 'user_id' not in data or 'server_id' not in data:
        return jsonify(message='规则名称、用户ID和服务器ID是必需的'), 400

    user = User.query.get(data['user_id'])
    server = Server.query.get(data['server_id'])
    if not user or not server:
        return jsonify(message='无效的用户ID或服务器ID'), 400

    new_rule = Rule(
        name=data['name'],
        source=data.get('source'),
        destination=data.get('destination'),
        protocol=data.get('protocol'),
        user_id=data['user_id'],
        server_id=data['server_id']
    )
    db.session.add(new_rule)
    db.session.commit()
    return jsonify(message='规则创建成功', rule_id=new_rule.id), 201

@rule_bp.route('/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    data = request.get_json()
    if not data:
        return jsonify(message='请求体不能为空'), 400

    if 'name' in data:
        rule.name = data['name']
    if 'source' in data:
        rule.source = data['source']
    if 'destination' in data:
        rule.destination = data['destination']
    if 'protocol' in data:
        rule.protocol = data['protocol']
    if 'user_id' in data:
        user = User.query.get(data['user_id'])
        if not user:
            return jsonify(message='无效的用户ID'), 400
        rule.user_id = data['user_id']
    if 'server_id' in data:
        server = Server.query.get(data['server_id'])
        if not server:
            return jsonify(message='无效的服务器ID'), 400
        rule.server_id = data['server_id']

    db.session.commit()
    return jsonify(message='规则信息更新成功')

@rule_bp.route('/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify(message='规则删除成功')