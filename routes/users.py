from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from models import db, User

user_bp = Blueprint('user', __name__)

# 权限检查装饰器 (示例，可以根据需要扩展)
def admin_required(func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)  # 返回 403 Forbidden，表示无权限
        return func(*args, **kwargs)
    return decorated_view

@user_bp.route('/', methods=['GET'])
@login_required
@admin_required # 只有管理员可以列出所有用户
def list_users():
    """获取所有用户列表 (管理员权限)"""
    users = User.query.all()
    user_list = [{'id': user.id, 'username': user.username, 'role': user.role, 'traffic_limit': user.traffic_limit} for user in users]
    return jsonify(users=user_list)

@user_bp.route('/<int:user_id>', methods=['GET'])
@login_required
@admin_required # 只有管理员可以获取用户详情
def get_user(user_id):
    """获取单个用户信息 (管理员权限)"""
    user = User.query.get_or_404(user_id) # 找不到用户时返回 404
    return jsonify(id=user.id, username=user.username, role=user.role, traffic_limit=user.traffic_limit)

@user_bp.route('/', methods=['POST'])
@login_required
@admin_required # 只有管理员可以创建用户
def create_user():
    """创建新用户 (管理员权限)"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data or 'role' not in data: # 需要 role 参数
        return jsonify(message='用户名、密码和角色是必需的'), 400 # Bad Request

    username = data['username']
    password = data['password']
    role = data['role'] # 获取角色
    if role not in ['admin', 'user']: # 验证角色是否有效
        return jsonify(message='角色必须是 "admin" 或 "user"'), 400

    if User.query.filter_by(username=username).first():
        return jsonify(message='用户名已存在'), 409 # Conflict

    new_user = User(username=username, password=password, role=role) # 设置角色
    db.session.add(new_user)
    db.session.commit()
    return jsonify(message='用户创建成功', user_id=new_user.id), 201 # Created

@user_bp.route('/<int:user_id>', methods=['PUT'])
@login_required
@admin_required # 只有管理员可以更新用户信息
def update_user(user_id):
    """更新用户信息 (管理员权限)"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if not data:
        return jsonify(message='请求体不能为空'), 400

    if 'username' in data:
        user.username = data['username']
    if 'traffic_limit' in data:
        user.traffic_limit = data['traffic_limit']
    if 'password' in data: # 允许更新密码，实际应用中需要考虑密码更新流程
        user.password = data['password']
    if 'role' in data: # 允许更新角色
        role = data['role']
        if role not in ['admin', 'user']: # 验证角色是否有效
            return jsonify(message='角色必须是 "admin" 或 "user"'), 400
        user.role = role

    db.session.commit()
    return jsonify(message='用户信息更新成功')

@user_bp.route('/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required # 只有管理员可以删除用户
def delete_user(user_id):
    """删除用户 (管理员权限)"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify(message='用户删除成功')