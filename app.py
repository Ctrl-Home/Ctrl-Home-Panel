import os
import logging
from flask import Flask, jsonify, request
# Removed werkzeug.security import as it's handled in the model now
# from werkzeug.security import generate_password_hash

from config import get_config
from extensions import db, migrate, jwt, cors # 导入实例化的扩展
# 导入你的服务 (如果需要附加到 app)
from core.mqtt_service import MQTTService
# from core.state_manager import StateManager # 假设你有这些服务
# from core.rule_manager import RuleManager
# from core.device_manager import DeviceManager
# from core.mqtt_controller import MQTTController

# 实例化服务
mqtt_service = MQTTService()
# state_manager = StateManager()
# rule_manager = RuleManager()
# device_manager = DeviceManager()
# mqtt_controller = MQTTController()


def create_app(config_name=None):
    app = Flask(__name__)

    # 加载配置
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    app_config = get_config(config_name) # Pass config_name to get_config
    app.config.from_object(app_config)

    # Setup logging if not already configured by Flask
    if not app.debug:
        # Configure logging level, format, handlers etc. as needed
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

    app.logger.info(f"Starting app with config: {config_name}")


    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    # 配置 CORS - 生产环境应限制 origins
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True) # 允许所有来源访问 /api/*
    app.logger.info(f"CORS configured for /api/* with origins: *")

    # 初始化并附加服务到 app context
    mqtt_service.init_app(app)
    app.mqtt_service = mqtt_service
    # state_manager.init_app(app) # 假设服务有 init_app 方法
    # app.state_manager = state_manager
    # rule_manager.init_app(app)
    # app.rule_manager = rule_manager
    # device_manager.init_app(app)
    # app.device_manager = device_manager
    # mqtt_controller.init_app(app, mqtt_service) # 可能依赖其他服务
    # app.mqtt_controller = mqtt_controller
    app.logger.info("Core services initialized and attached to app.")


    # 注册 API 蓝图
    # Ensure these imports happen *after* app is created or use factory pattern within blueprints
    from routes.api.new.auth import auth_bp
    from routes.api.new.rules import rules_bp
    from routes.api.new.nodes import nodes_bp
    from routes.api.new.engine import engine_api_bp
    from routes.api.new.sensors import sensors_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth') # Example adding prefix
    app.register_blueprint(rules_bp, url_prefix='/api/rules')
    app.register_blueprint(nodes_bp, url_prefix='/api/nodes')
    app.register_blueprint(engine_api_bp, url_prefix='/api/engine')
    app.register_blueprint(sensors_bp, url_prefix='/api/sensors')
    app.logger.info("API blueprints registered.")

    # 注册全局错误处理器 (返回 JSON)
    @app.errorhandler(400)
    def bad_request(error):
        description = getattr(error, 'description', "无效请求")
        app.logger.warning(f"Bad Request (400): {description}")
        return jsonify(error=description), 400

    @app.errorhandler(401)
    def unauthorized(error):
        description = getattr(error, 'description', "未授权访问")
        app.logger.warning(f"Unauthorized (401): {description}")
        return jsonify(error=description), 401

    @app.errorhandler(403)
    def forbidden(error):
        description = getattr(error, 'description', "禁止访问")
        app.logger.warning(f"Forbidden (403): {description}")
        return jsonify(error=description), 403

    @app.errorhandler(404)
    def not_found(error):
        description = getattr(error, 'description', "资源未找到")
        app.logger.warning(f"Not Found (404): {description} - URL: {request.url if 'request' in globals() else 'N/A'}")
        return jsonify(error=description), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        # 记录真实错误
        app.logger.error(f"Server Error (500): {error}", exc_info=True)
        description = getattr(error, 'description', "服务器内部错误")
        # 不要在生产中暴露原始错误给客户端 unless debugging
        resp_error = "服务器内部错误" if not app.debug else str(error)
        return jsonify(error=resp_error), 500

    @app.errorhandler(503)
    def service_unavailable(error):
        description = getattr(error, 'description', "服务暂时不可用")
        app.logger.error(f"Service Unavailable (503): {description}")
        return jsonify(error=description), 503

    # 创建数据库表和初始用户 (在应用上下文中)
    with app.app_context():
        # Import models inside context or ensure they are loaded before this point
        from models import User  # Import all models

        try:
            # db.drop_all() # 开发时可能需要，谨慎使用
            db.create_all()
            app.logger.info("Database tables checked/created.")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}", exc_info=True)
            # Depending on severity, you might want to raise the error or exit
            # raise e # Re-raise if you want the app startup to fail

        # 创建初始管理员用户
        admin_config = app.config.get('INITIAL_ADMIN_USER', {})
        if admin_config and 'username' in admin_config and 'password' in admin_config:
            admin_username = admin_config['username']
            try:
                # Check if user exists within the same try block as commit
                if User.query.filter_by(username=admin_username).first() is None:
                    admin_user = User(
                        username=admin_username,
                        role=admin_config.get('role', 'admin')
                    )
                    # --- THIS IS THE CORRECTED LINE ---
                    # Use the property setter, not a direct method call
                    admin_user.password = admin_config['password']
                    # --- END CORRECTION ---

                    db.session.add(admin_user)
                    db.session.commit()
                    app.logger.info(f"Created initial admin user: {admin_username}")
                else:
                    app.logger.info(f"Admin user {admin_username} already exists.")
            except Exception as e:
                 db.session.rollback()
                 app.logger.error(f"Failed to create or check initial admin user {admin_username}: {e}", exc_info=True)

        else:
            app.logger.warning("INITIAL_ADMIN_USER not found in config or missing username/password. Skipping initial admin user creation.")

    return app

# Make sure run.py or your WSGI server calls create_app()
# Example for run.py:
# from app import create_app
# import os
#
# app = create_app(os.getenv('FLASK_ENV') or 'default')
#
# if __name__ == '__main__':
#    app.run() # Add host/port as needed, e.g., app.run(host='0.0.0.0', port=5000)