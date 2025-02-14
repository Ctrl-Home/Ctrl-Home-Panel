from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt
from datetime import datetime

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
    node = db.relationship('Node', foreign_keys=[node_id], backref='rules', lazy=True)  # 明确指定 foreign_keys
    entry_node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    entry_node = db.relationship('Node', foreign_keys=[entry_node_id], lazy=True, backref='entry_rules')  # 明确指定 foreign_keys
    user = db.relationship('User', backref='rules', lazy=True)
    landing_destination = db.Column(db.String(255), nullable=False)

    # 新增的字段 (用于支持更复杂的规则，例如链式代理、多跳等)
    chain_uuid = db.Column(db.String(128), nullable=True)  # 链的唯一标识符 (如果规则属于一个链)
    hop_uuid = db.Column(db.String(128), nullable=True)    # 多跳节点的唯一标识符 (如果规则是多跳的一部分)
    node_uuid = db.Column(db.String(128), nullable=True)    # 节点的唯一标识符(如果规则是和特定节点绑定的)
    entry_service_uuid = db.Column(db.String(128), nullable=True) # 入口服务的唯一标识符
    exit_service_uuid = db.Column(db.String(128), nullable=True)  # 出口服务的唯一标识符
    target_uuid = db.Column(db.String(128), nullable=True)        # 目标对象的唯一标识 (例如, 目标服务器、目标用户)
    status = db.Column(db.String(255), nullable=True, default='pending')
    def __repr__(self):
        return f'<Rule {self.name}>'



class Node(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "ingress", "egress", "both"
    protocols = db.Column(db.String(120))  # "vless,trojan,..."  支持的协议, 逗号分隔
    secret_key = db.Column(db.String(120), nullable=False)  # 用于身份验证
    last_heartbeat = db.Column(db.DateTime)  # 上次心跳时间
    status = db.Column(db.String(20), default='offline')  # online, offline
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)  # 新增修改时间, 默认为创建时间

    software_instances = db.relationship('NodeSoftware', backref='node', lazy=True)

    def __repr__(self):
        return f'<Node {self.ip_address}:{self.port}>'

class NodeSoftware(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=False)
    software_name = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(50))
    config_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='stopped')
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)
    api_username = db.Column(db.String(120))
    api_password = db.Column(db.String(120))

    def __repr__(self):
        return f'<NodeSoftware {self.software_name} on Node {self.node_id}>'