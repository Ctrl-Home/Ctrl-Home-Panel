import bcrypt
import yaml
from flask import Flask, current_app, jsonify, request
from flask_login import LoginManager
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import json
from models import db, User
from routes.register_all_api_routes import register_routes  # 导入总的路由注册函数
from utils.mqtt.init_services import init_mqtt_services, start_mqtt_services  # 导入MQTT服务初始化和启动函数


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

    # JWT配置
    from flask_jwt_extended import JWTManager
    app.config.update({
        'JWT_SECRET_KEY': config['jwt']['secret_key'],
        'JWT_ACCESS_TOKEN_EXPIRES': config['jwt'].get('access_token_expires', 3600),
        'JWT_REFRESH_TOKEN_EXPIRES': config['jwt'].get('refresh_token_expires', 604800),
        'JWT_TOKEN_LOCATION': ['cookies'],
        'JWT_COOKIE_SECURE': config['jwt'].get('cookie_secure', False),
        'JWT_COOKIE_SAMESITE': config['jwt'].get('cookie_samesite', 'Lax'),  # 更安全的SameSite设置
        'JWT_COOKIE_CSRF_PROTECT': True,  # 启用CSRF保护
        'JWT_CSRF_CHECK_FORM': True,
        'JWT_CSRF_IN_COOKIES': True,
        'JWT_COOKIE_DOMAIN': config['jwt'].get('cookie_domain', None)  # 生产环境需配置
    })
    
    # 初始化JWT管理器
    jwt = JWTManager(app)
    
    # 统一JWT错误响应格式
    @jwt.invalid_token_loader
    @jwt.expired_token_loader
    @jwt.unauthorized_loader
    def handle_jwt_error(reason):
        return jsonify({
            "code": 401,
            "message": f"认证失败: {reason}",
            "data": None
        }), 401
    
    # 处理OPTIONS预检请求
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            print(f"处理预检请求来自: {request.origin}")  
            print(f"请求头: {dict(request.headers)}")  
            
            resp = current_app.make_default_options_response()
            headers = resp.headers
            # 允许更多的请求头
            headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRF-Token, X-Requested-With, Accept, Origin'
            headers['Access-Control-Allow-Credentials'] = 'true'
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Max-Age'] = '3600'  # 预检请求缓存时间
            
            # 如果请求中包含Origin头，则设置允许的源
            if request.headers.get('Origin'):
                cors_origins = current_app.config.get('CORS_ORIGINS', ['*'])
                if '*' in cors_origins or request.headers.get('Origin') in cors_origins:
                    headers['Access-Control-Allow-Origin'] = request.headers.get('Origin')
            
            print("设置CORS响应头:", dict(headers))
            return resp
            
    # 响应包装中间件（排除API规范端点）
    @app.after_request
    def wrap_response(response):
        # 跳过非JSON响应和API规范端点
        if request.path == '/api-spec.json':
            return response
            
        # 检查是否是API请求
        if request.path.startswith('/api/'):
            try:
                if response.content_type and 'application/json' in response.content_type:
                    # 尝试解析JSON数据
                    data = response.get_json(silent=True)
                    
                    # 已经是统一格式的响应就不修改
                    if isinstance(data, dict) and all(k in data for k in ['code', 'message']):
                        return response
                    
                    # 否则包装成统一格式
                    status_code = response.status_code
                    message = ''
                    
                    if isinstance(data, dict) and 'message' in data:
                        message = data.pop('message')
                    elif isinstance(data, dict) and 'error' in data:
                        message = data.pop('error')
                    else:
                        # 根据状态码设置默认消息
                        if 200 <= status_code < 300:
                            message = 'success'
                        elif status_code == 400:
                            message = '请求参数错误'
                        elif status_code == 401:
                            message = '未认证'
                        elif status_code == 403:
                            message = '权限不足'
                        elif status_code == 404:
                            message = '资源不存在'
                        elif status_code == 500:
                            message = '服务器内部错误'
                        else:
                            message = f'HTTP状态码: {status_code}'
                    
                    wrapped_data = {
                        "code": status_code,
                        "message": message,
                        "data": data
                    }
                    
                    response.data = json.dumps(wrapped_data)
                    response.content_type = 'application/json'
                elif response.status_code >= 400 and not response.data:
                    # 对于没有内容的错误响应，创建标准错误格式
                    status_code = response.status_code
                    message = response.status
                    
                    wrapped_data = {
                        "code": status_code,
                        "message": message,
                        "data": None
                    }
                    
                    response.data = json.dumps(wrapped_data)
                    response.content_type = 'application/json'
            except Exception as e:
                print(f"响应包装出错: {str(e)}")
        
        return response
        
    # 添加通用的CORS头部 - 需要在响应包装之后执行
    @app.after_request
    def add_cors_headers(response):
        # 如果是API请求且不是预检请求
        if request.path.startswith('/api/') and request.method != 'OPTIONS':
            origin = request.headers.get('Origin')
            cors_origins = current_app.config.get('CORS_ORIGINS', ['*'])
            
            if origin and ('*' in cors_origins or origin in cors_origins):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization, X-CSRF-Token'
        
        return response

    # 配置跨域 (支持带凭证的请求)
    cors_origins = config['cors']['allowed_origins']
    print(f"当前允许的跨域源: {cors_origins}")  # 添加调试日志
    app.config['CORS_ORIGINS'] = cors_origins  # 保存到应用配置中供其他函数使用
    
    # 配置跨域 (支持带凭证的请求)
    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token", "Accept", "Origin"],
            "expose_headers": ["Content-Type", "Authorization", "X-CSRF-Token"],
            "supports_credentials": True,
            "max_age": 3600
        }
    })

    # 初始化MQTT服务组件 - 在注册路由前添加
    with app.app_context():
        try:
            init_mqtt_services(app, config)
        except Exception as e:
            print(f"初始化MQTT服务组件失败: {str(e)}")
            # 即使MQTT服务初始化失败，也允许应用继续启动

    # 注册路由
    register_routes(app)  # 使用总的路由注册函数

    # Swagger UI配置
    SWAGGER_URL = '/docs'
    API_URL = '/api-spec.json'
    
    swagger_ui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "智能家居API文档",
            'layout': "BaseLayout",
            'deepLinking': True
        }
    )
    app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

    @app.route(API_URL)
    def get_api_spec():
        from docs.openapi_config import spec
        # 动态添加路由到规范
        with app.test_request_context():
            for name, func in app.view_functions.items():
                if name.startswith('api'):
                    spec.path(view=func)
        # 生成规范并确保正确格式
        spec_dict = spec.to_dict()
        spec_dict['openapi'] = '3.0.0'
        # 直接返回规范字典，避免被响应包装中间件处理
        return jsonify(spec_dict), 200, {'Content-Type': 'application/json'}

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
    # 从配置文件获取应用设置，如果没有则使用默认值
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    app_config = config.get('app', {})
    debug_mode = app_config.get('debug', False)
    host = app_config.get('host', '0.0.0.0')
    port = app_config.get('port', 15000)
    
    # 在应用真正启动前，启动MQTT服务
    with app.app_context():
        try:
            start_mqtt_services(app)
        except Exception as e:
            print(f"启动MQTT服务失败: {str(e)}")
            # 即使MQTT服务启动失败，也继续运行应用
    
    app.run(host=host, port=port, debug=debug_mode)
