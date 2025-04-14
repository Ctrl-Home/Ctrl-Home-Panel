from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies
)
from models import User

def register_auth_routes(app):
    @app.route('/api/v1/auth/login', methods=['POST'])
    def login():
        data = request.get_json()
        user = User.query.filter_by(username=data.get('username')).first()
        
        if not user or not user.verify_password(data.get('password')):
            return jsonify({
                "code": 401,
                "message": "无效的用户名或密码",
                "data": None
            }), 401

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        response = jsonify({
            "code": 200,
            "message": "登录成功",
            "data": {
                "user_id": user.id,
                "role": user.role
            }
        })
        
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        return response

    @app.route('/api/v1/auth/refresh', methods=['POST'])
    @jwt_required(refresh=True)
    def refresh():
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=str(current_user))
        response = jsonify({"code": 200, "message": "令牌已刷新"})
        set_access_cookies(response, new_token)
        return response

    @app.route('/api/v1/auth/logout', methods=['POST'])
    def logout():
        response = jsonify({"code": 200, "message": "登出成功"})
        unset_jwt_cookies(response)
        return response
