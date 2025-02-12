import yaml
from flask import Flask
from flask_login import LoginManager

from models import db, User
from routes.api.register_all_api_routes import register_routes  # 导入总的路由注册函数


def create_app():
    app = Flask(__name__)

    # 加载配置
    with open('config.yaml', 'r', encoding='utf-8') as f:  # 指定 encoding='utf-8'
        config = yaml.safe_load(f)

    # 配置 Flask 应用
    app.config['SECRET_KEY'] = config['secret_key']  # 从配置文件加载
    app.config['SQLALCHEMY_DATABASE_URI'] = config['database']['uri']  # 从配置文件加载
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化数据库
    db.init_app(app)

    # 初始化 Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'  # 假设你的登录路由是 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 注册路由
    register_routes(app)  # 使用总的路由注册函数

    # 创建数据库表和初始管理员用户 (在应用上下文中)
    with app.app_context():
        db.create_all()

        # 创建初始管理员用户
        admin_config = config['admin_user']  # 从配置文件读取管理员信息
        if User.query.filter_by(username=admin_config['username']).first() is None:
            admin_user = User(username=admin_config['username'], password=admin_config['password'],
                            role=admin_config['role'])
            db.session.add(admin_user)
            db.session.commit()
            print("创建了初始管理员用户: {}".format(admin_config['username']))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)