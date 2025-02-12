from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt

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

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='online')
    server_type = db.Column(db.String(20), default='exit')
    rules = db.relationship('Rule', backref='server', lazy=True) # 修改 backref 为 'server'

    def __repr__(self):
        return f'<Server {self.name}>'

class PermissionGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    allowed_entry_servers = db.Column(db.String(255), nullable=True)
    allowed_exit_servers = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<PermissionGroup {self.name}>'

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(255))
    destination = db.Column(db.String(255))
    protocol = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
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
    last_modified = db.Column(db.DateTime)  # 新增修改时间
    # ... 其他节点属性 (例如: 负载, 在线用户, 流量统计等)
    def __repr__(self):
        return f'<Node {self.ip_address}:{self.port}>'