from flask import Blueprint, request, jsonify, current_app
# werkzeug.security 不再直接用于这里，因为模型内部使用了 bcrypt
# from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User # 确保 User 模型在这里被导入
from extensions import jwt # 导入 JWT 实例
import bcrypt # 确保 bcrypt 在 User 模型文件或这里被导入，模型文件更佳

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

    # --- 修改开始 ---
    # 创建用户实例
    new_user = User(username=username)
    # 通过 password setter 自动哈希密码并存入 password_hash
    new_user.password = password
    # --- 修改结束 ---

    # 可以根据需要设置默认角色等，模型中已有默认值 'user'
    # new_user.role = 'user'
    # 也可以在这里设置 traffic_limit 或 permission_group_id (如果需要)
    # new_user.traffic_limit = 2048 # 示例

    try:
        db.session.add(new_user)
        db.session.commit()
        # 提交后 new_user.id 才会被赋值 (如果是自增主键)

        # print(new_user) # 可以在这里打印，但注意不要打印敏感信息到生产日志
        # print(f"User created: ID={new_user.id}, Username={new_user.username}, Role={new_user.role}")

        # 创建 JWT Token
        access_token = create_access_token(identity=new_user.id)
        # 准备返回的用户信息
        user_info = {
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "traffic_limit": new_user.traffic_limit,
            # 如果需要，也可以返回权限组信息，但要小心循环引用或暴露过多信息
            # "permission_group_id": new_user.permission_group_id
        }
        return jsonify(message="注册成功", access_token=access_token, user=user_info), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"注册失败: {e}")
        return jsonify({"error": "注册过程中发生错误"}), 500

# --- login, me, logout 函数保持不变 ---
# (login 函数中的 user.verify_password(password) 与 User 模型中的方法匹配，无需修改)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "缺少用户名或密码"}), 400

    username = data['username']
    password = data['password']

    user = User.query.filter_by(username=username).first()

    # 这里 user.verify_password(password) 会调用 User 模型中的方法
    if user and user.verify_password(password):
        # 密码正确，创建 JWT
        access_token = create_access_token(identity=user.id)
        user_info = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "traffic_limit": user.traffic_limit,
            # "permission_group_id": user.permission_group_id
        }
        return jsonify(access_token=access_token, user=user_info), 200
    else:
        return jsonify({"error": "用户名或密码无效"}), 401 # 401 Unauthorized

# ... (get_current_user 和 logout 函数不变) ...
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
         return jsonify({"error": "用户未找到"}), 404
    user_info = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "traffic_limit": user.traffic_limit,
        # "permission_group_id": user.permission_group_id
    }
    return jsonify(user=user_info), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # ... (登出逻辑，如需要黑名单)
    return jsonify({"message": "成功登出"}), 200