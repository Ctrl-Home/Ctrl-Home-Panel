import os
from app import create_app

# 从环境变量获取配置名称，默认为 'default'
config_name = os.getenv('FLASK_ENV', 'default')
app = create_app(config_name)

if __name__ == '__main__':
    # 从环境变量或配置中获取 host 和 port
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 15000)) # 与你原来一致
    debug = app.config.get('DEBUG', False)

    # 使用 Flask 开发服务器运行 (生产环境建议用 Gunicorn/uWSGI)
    print(f"Starting Flask API server on http://{host}:{port}/ (Debug: {debug})")
    app.run(host=host, port=port, debug=debug)