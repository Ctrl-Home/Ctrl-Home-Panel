from flask import Blueprint, jsonify, request
from models import db, Server

server_bp = Blueprint('server', __name__)

@server_bp.route('/', methods=['GET'])
def list_servers():
    servers = Server.query.all()
    server_list = [{'id': s.id, 'name': s.name, 'address': s.address, 'status': s.status} for s in servers]
    return jsonify(servers=server_list)

@server_bp.route('/<int:server_id>', methods=['GET'])
def get_server(server_id):
    server = Server.query.get_or_404(server_id)
    return jsonify(id=server.id, name=server.name, address=server.address, status=server.status)

@server_bp.route('/', methods=['POST'])
def create_server():
    data = request.get_json()
    if not data or 'name' not in data or 'address' not in data:
        return jsonify(message='服务器名称和地址是必需的'), 400

    new_server = Server(name=data['name'], address=data['address'])
    db.session.add(new_server)
    db.session.commit()
    return jsonify(message='服务器创建成功', server_id=new_server.id), 201

@server_bp.route('/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    server = Server.query.get_or_404(server_id)
    data = request.get_json()
    if not data:
        return jsonify(message='请求体不能为空'), 400

    if 'name' in data:
        server.name = data['name']
    if 'address' in data:
        server.address = data['address']
    if 'status' in data:
        server.status = data['status']

    db.session.commit()
    return jsonify(message='服务器信息更新成功')

@server_bp.route('/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    server = Server.query.get_or_404(server_id)
    db.session.delete(server)
    db.session.commit()
    return jsonify(message='服务器删除成功')