# config.py
import os
import yaml
import logging

# 获取日志记录器
logger = logging.getLogger(__name__)
# 配置日志基础设置（如果还没有其他地方配置的话）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ConfigLoadingError(Exception):
    """自定义配置加载错误"""
    pass

class Config:
    """基础配置类 - 从 config.yaml 加载"""

    # --- 先加载 YAML 文件 ---
    yaml_config = {}
    try:
        # 确定 config.yaml 的路径，这里假设它在项目根目录
        # 如果 config.py 在某个子目录（例如 'app/'），你可能需要调整路径
        # base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) # 获取项目根目录
        # config_path = os.path.join(base_dir, 'config.yaml')
        config_path = 'config.yaml' # 假设就在运行脚本的当前工作目录或者项目根目录

        if not os.path.exists(config_path):
             logger.error(f"错误: 配置文件 '{config_path}' 未找到。请确保文件存在于正确的位置。")
             raise ConfigLoadingError(f"配置文件 '{config_path}' 未找到。")

        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if not isinstance(yaml_config, dict):
                logger.error(f"错误: '{config_path}' 文件内容不是有效的 YAML 字典。")
                raise ConfigLoadingError(f"'{config_path}' 文件内容不是有效的 YAML 字典。")
            logger.info(f"成功加载配置文件: '{config_path}'")
    except FileNotFoundError:
        # 这个错误理论上已经被上面的 os.path.exists 捕获，但保留以防万一
        logger.error(f"错误: 配置文件 '{config_path}' 未找到。请确保文件存在。")
        raise ConfigLoadingError(f"配置文件 '{config_path}' 未找到。")
    except yaml.YAMLError as e:
        logger.error(f"错误: 解析配置文件 '{config_path}' 失败: {e}")
        raise ConfigLoadingError(f"解析配置文件 '{config_path}' 失败: {e}")
    except Exception as e:
        logger.error(f"加载配置文件 '{config_path}' 时发生未知错误: {e}", exc_info=True) # 添加 exc_info=True 获取更详细的回溯信息
        raise ConfigLoadingError(f"加载配置文件 '{config_path}' 时发生未知错误: {e}")

    # --- 从加载的 yaml_config 中提取配置 ---

    # Flask 和 JWT 密钥 (必需)
    SECRET_KEY = yaml_config.get('secret_key')
    JWT_SECRET_KEY = yaml_config.get('jwt_secret_key')

    # SQLAlchemy 配置 (必需)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    database_config = yaml_config.get('database', {})
    SQLALCHEMY_DATABASE_URI = database_config.get('uri')

    # MQTT 配置 (必需核心部分，可选认证)
    mqtt_config = yaml_config.get('mqtt', {})
    MQTT_BROKER_HOST = mqtt_config.get('broker_host')
    MQTT_BROKER_PORT = int(mqtt_config.get('broker_port', 11883)) # 提供默认端口以防万一，但最好在yaml中指定
    MQTT_USERNAME = mqtt_config.get('username') # 可以是 None
    MQTT_PASSWORD = mqtt_config.get('password') # 可以是 None
    MQTT_TOPIC_BASE = mqtt_config.get('topic_base')

    # 初始管理员用户 (可选)
    INITIAL_ADMIN_USER = yaml_config.get('admin_user', {})

    # --- 验证必需的配置 ---
    # 将验证逻辑移到类加载后，或者在 get_config 中进行，确保日志系统已初始化
    # (放在这里，如果日志还没配置好，错误可能无法记录)
    # 也可以考虑在 __init__ 中做，但这些是类变量
    @classmethod
    def validate_mandatory_keys(cls):
        """验证必要的配置项是否存在"""
        MANDATORY_KEYS = {
            'SECRET_KEY': cls.SECRET_KEY,
            'JWT_SECRET_KEY': cls.JWT_SECRET_KEY,
            'SQLALCHEMY_DATABASE_URI': cls.SQLALCHEMY_DATABASE_URI,
            'MQTT_BROKER_HOST': cls.MQTT_BROKER_HOST,
            'MQTT_BROKER_PORT': cls.MQTT_BROKER_PORT, # 验证确保明确配置
            'MQTT_TOPIC_BASE': cls.MQTT_TOPIC_BASE
        }
        missing_keys = [k for k, v in MANDATORY_KEYS.items() if v is None or str(v).strip() == '']
        if missing_keys:
            error_message = f"错误: config.yaml 文件中缺少以下必需的配置项: {', '.join(missing_keys)}"
            logger.error(error_message)
            raise ConfigLoadingError(error_message)
        else:
            logger.info("所有必需的配置项已加载。")

    # --- 其他固定配置 ---
    # (可以在这里添加不常变或不适合放yaml的配置)


# --- 环境特定配置 ---
class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    # 如果需要，可以覆盖或添加特定于开发的设置
    # 例如: SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # 生产环境特定配置...
    # 例如，配置不同的日志级别或日志文件

# --- 获取配置的函数 ---
config_by_name = dict(
    development=DevelopmentConfig,
    production=ProductionConfig,
    default=DevelopmentConfig # 默认使用开发配置
)

# ========== 修改这里 ==========
# def get_config(): # 原来的定义
def get_config(name='default'): # 修改后的定义，接收 name 参数，并提供默认值
    """
    根据提供的名称选择并返回相应的配置类实例。
    Args:
        name (str): 配置环境的名称 ('development', 'production', etc.)。
                    如果未提供或为 None，则使用 'default'。
    Returns:
        Config: 选定的配置类。
    """
    if name is None:
        name = 'default'
    # 使用传入的 name (转换为小写以增加兼容性) 来选择配置类
    env = name.lower()
    selected_config_class = config_by_name.get(env, config_by_name['default']) # 获取类本身

    # 在选定配置类后，进行一次验证
    try:
        selected_config_class.validate_mandatory_keys()
    except ConfigLoadingError as e:
        # 如果验证失败，记录错误并可能重新抛出或返回 None，取决于你的错误处理策略
        logger.critical(f"配置验证失败，无法启动应用: {e}")
        raise  # 重新抛出错误，阻止应用启动

    logger.info(f"使用配置环境: '{env}' (选择配置类: {selected_config_class.__name__})")
    # 注意：这里返回的是配置类本身，Flask 会处理它
    # 如果需要返回实例，可以写成 selected_config_class()
    return selected_config_class
# ========== 修改结束 ==========


# --- 使用示例 (在 app.py 中应该像这样) ---
# import os
# from config import get_config
#
# config_name = os.getenv('FLASK_ENV', 'default') # 从环境变量获取名称
# AppConfig = get_config(config_name) # 调用修改后的函数获取配置类
# app.config.from_object(AppConfig) # 从配置类加载配置