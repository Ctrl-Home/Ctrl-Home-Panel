from flask import Flask, render_template
from flask_login import login_required, current_user
from models import db, Rule  # 确保导入 Rule 模型

def register_other_routes(app):
    @app.route('/')
    @login_required
    def index():
        if current_user.role == 'admin':
            relay_rules = Rule.query.all() # 管理员查看所有规则
        else:
            relay_rules = Rule.query.filter_by(user_id=current_user.id).all() # 普通用户只查看自己的规则
        return render_template('relay_list.html', relay_rules=relay_rules, current_user=current_user)