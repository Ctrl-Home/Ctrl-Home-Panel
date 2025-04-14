# routes/register_all_api_routes.py

# --- 导入你现有的注册函数 ---
from .api.user_routes import register_user_routes
from .api.rule_list import register_other_routes # 假设这个包含其他路由

# --- 导入认证路由注册函数 ---
from .api.auth_routes import register_auth_routes

# --- 导入新的引擎路由注册函数 ---
from .api.engine_routes import register_engine_routes # 导入新的函数

def register_routes(app):
    """注册应用中所有的 API 蓝图。"""
    # 注册你现有的蓝图
    register_user_routes(app)
    register_other_routes(app)

    # --- 注册认证路由 ---
    register_auth_routes(app)
    
    # --- 注册新的引擎蓝图 ---
    register_engine_routes(app)

    print("所有 API 路由蓝图已完成注册。")
