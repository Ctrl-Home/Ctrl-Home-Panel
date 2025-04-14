#rlue_list.py
from flask import Flask, render_template, jsonify, Blueprint
from flask_login import login_required, current_user
from models import db, Rule  # 确保导入 Rule 模型

# 创建一个蓝图用于API
rule_list_api_bp = Blueprint('rule_list_api', __name__, url_prefix='/api/v1')

def register_other_routes(app):
    # 注册蓝图
    app.register_blueprint(rule_list_api_bp)
    
    # 保留原有的HTML路由
    @app.route('/')
    @login_required
    def index():
        if current_user.role == 'admin':
            relay_rules = Rule.query.all() # 管理员查看所有规则
        else:
            relay_rules = Rule.query.filter_by(user_id=current_user.id).all() # 普通用户只查看自己的规则
        return render_template('rule_list.html', relay_rules=relay_rules, current_user=current_user)

# 添加API端点，用于获取规则列表
@rule_list_api_bp.route('/rules', methods=['GET'])
@login_required
def api_get_rules():
    """
    获取规则列表的API端点
    支持前后端分离应用
    """
    try:
        if current_user.role == 'admin':
            relay_rules = Rule.query.all()  # 管理员查看所有规则
        else:
            relay_rules = Rule.query.filter_by(user_id=current_user.id).all()  # 普通用户只查看自己的规则
        
        # 将规则对象转换为字典列表
        rules_data = []
        for rule in relay_rules:
            rule_dict = {
                'id': rule.id,
                'name': rule.name,
                'device_id': rule.device_id,
                'action': rule.action,
                'parameters': rule.parameters,
                'user_id': rule.user_id,
                'node_id': rule.node_id,
                'created_at': str(rule.created_at) if hasattr(rule, 'created_at') else None,
                'updated_at': str(rule.updated_at) if hasattr(rule, 'updated_at') else None,
                # 添加其他需要的字段
            }
            rules_data.append(rule_dict)
        
        return jsonify({
            'code': 200,
            'message': '成功获取规则列表',
            'data': rules_data
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取规则列表失败: {str(e)}',
            'data': None
        }), 500