from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from apispec.ext.marshmallow import MarshmallowPlugin

spec = APISpec(
    title="智能家居控制API",
    version="1.0.0",
    openapi_version="3.0.0",
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
    info={
        "description": "智能家居设备管理及自动化规则引擎API文档\n\n**认证方式**: JWT Cookie认证",
        "contact": {
            "name": "API支持",
            "url": "http://support.smarthome.com",
            "email": "api@smarthome.com"
        }
    },
    servers=[
        {"url": "http://localhost:15000", "description": "开发环境"},
        {"url": "https://api.smarthome.com", "description": "生产环境"}
    ],
    components={
        "securitySchemes": {
            "jwtCookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token_cookie",
                "description": "JWT认证Token通过Cookie传输"
            }
        }
    }
)
