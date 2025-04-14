from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User

def register_user_routes(app):
    @app.route('/api/v1/users/register', methods=['POST'])
    def register():
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                "code": 400,
                "message": "需要用户名和密码",
                "data": None
            }), 400
            
        if data['password'] != data.get('confirm_password', ''):
            return jsonify({
                "code": 400,
                "message": "两次密码输入不一致",
                "data": None
            }), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                "code": 409,
                "message": "用户名已存在",
                "data": None
            }), 409

        new_user = User(username=data['username'], password=data['password'])
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            "code": 201,
            "message": "注册成功",
            "data": {
                "user_id": new_user.id
            }
        }), 201

    @app.route('/api/v1/users/<int:user_id>', methods=['GET'])
    @jwt_required()
    def get_user(user_id):
        current_user_id = get_jwt_identity()
        if current_user_id != user_id:
            return jsonify({
                "code": 403,
                "message": "无权访问该用户信息",
                "data": None
            }), 403

        user = User.query.get(user_id)
        if not user:
            return jsonify({
                "code": 404,
                "message": "用户不存在",
                "data": None
            }), 404

        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "user_id": user.id,
                "username": user.username,
                "role": user.role
            }
        })

    @app.route('/api/v1/users/<int:user_id>', methods=['PUT'])
    @jwt_required()
    def update_user(user_id):
        current_user_id = get_jwt_identity()
        if current_user_id != user_id:
            return jsonify({
                "code": 403,
                "message": "无权修改该用户信息",
                "data": None
            }), 403

        user = User.query.get(user_id)
        if not user:
            return jsonify({
                "code": 404,
                "message": "用户不存在",
                "data": None
            }), 404

        data = request.get_json()
        if 'password' in data:
            user.password = data['password']
            
        db.session.commit()

        return jsonify({
            "code": 200,
            "message": "用户信息已更新",
            "data": None
        })
