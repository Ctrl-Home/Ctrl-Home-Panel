from flask import Blueprint, jsonify

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/user_count', methods=['GET'])
def get_user_count():
    """获取用户总数 (示例统计)"""
    from models import User # 避免循环导入，这里局部导入
    user_count = User.query.count()
    return jsonify(user_count=user_count)

# 您可以在这里添加更多统计相关的视图函数