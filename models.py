from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt
from datetime import datetime  # 导入 datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    traffic_limit = db.Column(db.Integer, default=1024)
    permission_group_id = db.Column(db.Integer, db.ForeignKey('permission_group.id'))
    permission_group = db.relationship('PermissionGroup', backref='users', lazy=True)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.username}>'

class PermissionGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    allowed_entry_nodes = db.Column(db.String(255), nullable=True)  # Renamed from allowed_entry_servers
    allowed_exit_nodes = db.Column(db.String(255), nullable=True)   # Renamed from allowed_exit_servers

    def __repr__(self):
        return f'<PermissionGroup {self.name}>'

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(255))
    destination = db.Column(db.String(255))
    protocol = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=False)
    node = db.relationship('Node', foreign_keys=[node_id], backref='rules', lazy=True) # 明确指定 foreign_keys 为 [node_id]
    entry_node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    entry_node = db.relationship('Node', foreign_keys=[entry_node_id], lazy=True, backref='entry_rules') # 明确指定 foreign_keys 为 [entry_node_id]

    user = db.relationship('User', backref='rules', lazy=True)

    def __repr__(self):
        return f'<Rule {self.name}>'

class Node(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "ingress", "egress", "both"
    protocols = db.Column(db.String(120))  # "vless,trojan,..."  支持的协议, 逗号分隔
    secret_key = db.Column(db.String(120), nullable=False) # 用于身份验证
    last_heartbeat = db.Column(db.DateTime) #上次心跳时间
    status = db.Column(db.String(20), default='offline') # online, offline
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)  # 新增修改时间, 默认为创建时间

    #  添加 relationship 到 NodeSoftware，一个节点可以有多个软件实例
    software_instances = db.relationship('NodeSoftware', backref='node', lazy=True)  # 多对一关系，一个节点对应多个软件实例

    def __repr__(self):
        return f'<Node {self.ip_address}:{self.port}>'

class NodeSoftware(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=False)  # 外键关联到 Node 表
    software_name = db.Column(db.String(100), nullable=False)  # 软件名称 (例如: "gost", "v2ray")
    version = db.Column(db.String(50))  # 软件版本
    config_path = db.Column(db.String(255)) # 软件配置路径, 可以是文件路径，或者配置的存储位置
    status = db.Column(db.String(20), default='stopped')  #  运行状态：running, stopped, error
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)  #  最后修改时间
    api_username = db.Column(db.String(120))  # API 用户名
    api_password = db.Column(db.String(120))  # API 密码
    # ... (可以添加更多的软件相关信息，例如: 启动命令，运行参数, 进程 ID 等)

    def __repr__(self):
        return f'<NodeSoftware {self.software_name} on Node {self.node_id}>'