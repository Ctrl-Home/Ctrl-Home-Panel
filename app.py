import bcrypt
import yaml
from flask import Flask, current_app
from flask_login import LoginManager

from models import db, User
from routes.register_all_api_routes import register_routes  # 导入总的路由注册函数


def create_app():
    app = Flask(__name__)

    # 加载配置
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:  # 指定 encoding='utf-8'
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("错误: config.yaml 文件未找到。请确保文件存在且路径正确。")
        return None # 或者 raise  异常来终止程序

    # 配置 Flask 应用
    app.config['SECRET_KEY'] = config['secret_key']  # 从配置文件加载
    app.config['SQLALCHEMY_DATABASE_URI'] = config['database']['uri']  # 从配置文件加载
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 使用 with 语句手动激活应用上下文
    with app.app_context():
        current_app.config['SECRET_KEY'] = config['secret_key']  # 现在可以在应用上下文中访问配置
        print(f"Secret key: {current_app.config['SECRET_KEY']}")  # 验证

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
        admin_config = config.get('admin_user')  # 从配置文件读取管理员信息，使用get防止KeyError
        if admin_config:
            if User.query.filter_by(username=admin_config['username']).first() is None:
                admin_user = User()
                admin_user.username = admin_config['username']
                admin_user.password = admin_config['password']
                print(admin_user.password)
                admin_user.role = admin_config.get('role', 'admin')  # 默认管理员角色
                db.session.add(admin_user)
                db.session.commit()
                print(f"创建了初始管理员用户: {admin_config['username']}")
            else:
                print(f"管理员用户 {admin_config['username']} 已经存在。")
        else:
            print("警告：config.yaml 中未找到 'admin_user' 配置，跳过创建初始管理员用户。")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=15000, debug=True)
