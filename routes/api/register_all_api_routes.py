from .user_routes import register_user_routes
from .relay_routes import register_relay_routes
from .other_routes import register_other_routes
from .node_routes import register_node_blueprint # 导入 Blueprint 注册函数

def register_routes(app):
    register_user_routes(app)
    register_relay_routes(app)
    register_other_routes(app)
    register_node_blueprint(app) # 调用注册 Blueprint 的函数