from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User
from extensions import jwt # 导入 JWT 实例

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "缺少用户名或密码"}), 400

    username = data['username']
    password = data['password']

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 409 # 409 Conflict

    # 创建用户并哈希密码
    new_user = User(username=username)
    new_user.set_password(password)
    # 可以根据需要设置默认角色等
    # new_user.role = 'user'

    try:
        db.session.add(new_user)
        db.session.commit()
        # 可以选择在注册后直接登录并返回 token
        access_token = create_access_token(identity=new_user.id)
        user_info = {"id": new_user.id, "username": new_user.username, "role": new_user.role}
        return jsonify(message="注册成功", access_token=access_token, user=user_info), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"注册失败: {e}")
        return jsonify({"error": "注册过程中发生错误"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "缺少用户名或密码"}), 400

    username = data['username']
    password = data['password']

    user = User.query.filter_by(username=username).first()

    if user and user.verify_password(password):
        # 密码正确，创建 JWT
        access_token = create_access_token(identity=user.id)
        user_info = {"id": user.id, "username": user.username, "role": user.role}
        return jsonify(access_token=access_token, user=user_info), 200
    else:
        return jsonify({"error": "用户名或密码无效"}), 401 # 401 Unauthorized

# 可选: 获取当前用户信息
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
         return jsonify({"error": "用户未找到"}), 404
    user_info = {"id": user.id, "username": user.username, "role": user.role}
    return jsonify(user=user_info), 200


# 可选: 登出 (JWT 登出通常在客户端删除 Token，但可以实现 Token 黑名单)
# 这里是一个简单的占位符，表明需要认证
@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # 如果实现了 Token 黑名单，在这里将 JTI 加入黑名单
    # from extensions import blocklist  # 假设你有一个 blocklist 集合
    # jti = get_jwt()['jti']
    # blocklist.add(jti)
    return jsonify({"message": "成功登出"}), 200

# --- JWT 配置回调 (可选，用于检查 Token 是否在黑名单中) ---
# @jwt.token_in_blocklist_loader
# def check_if_token_in_blocklist(jwt_header, jwt_payload):
#     from extensions import blocklist
#     jti = jwt_payload["jti"]
#     return jti in blocklist