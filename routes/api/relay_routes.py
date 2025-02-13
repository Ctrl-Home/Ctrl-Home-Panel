from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from models import db, User, Rule, Node  # 使用 Node 替换 Server
from sqlalchemy import or_  # 导入 or_
import yaml  # 导入 yaml
#  注意这里修改了导入
from routes.utils.agent_control import agent_control


def load_protocols(file_path="tools/gost/protocols.yaml"):  #  修正文件路径
    """从 YAML 文件加载协议配置."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:  #  指定编码为 utf-8
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"错误：未找到协议配置文件 {file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"错误：解析 YAML 文件时出错: {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"错误：使用utf-8编码读取文件时出错: {e}")  # 增加错误提示
        return None

def register_relay_routes(app):
    @app.route('/relay/add', methods=['GET', 'POST'])
    @login_required
    def add_relay():
        entry_nodes = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).all()
        exit_nodes = Node.query.filter(or_(Node.role.like('%egress%'), Node.role == 'both')).all()
        users = User.query.all()
        protocols_config = load_protocols() #加载协议配置
        protocols = protocols_config.get('protocols', {}) if protocols_config else {} #获取protocols配置

        if request.method == 'POST':
            name = request.form.get('name')
            source = request.form.get('source')
            destination = request.form.get('destination')
            protocol = request.form.get('protocol')

            if not all([name, source, destination, protocol]):
                flash('所有字段均为必填项', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols
                                                                                                                                                                #  传递 protocols 给模板
            if not (source.count(':') == 1 and destination.count(':') == 1):
                flash('源和目标地址格式错误，请使用 IP:端口 的格式', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols

            try:
                if current_user.role == 'admin':
                    entry_node_id = request.form.get('entry_node_id')
                    exit_node_id = request.form.get('exit_node_id')
                    user_id = request.form.get('user_id')

                    if not all([exit_node_id, user_id, entry_node_id]):
                        flash('管理员添加规则时，入口、出口节点和关联用户为必选项', 'danger')
                        return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols

                    user = User.query.get_or_404(user_id)
                    entry_node = Node.query.get_or_404(entry_node_id)
                    exit_node = Node.query.get_or_404(exit_node_id)

                    node_id = exit_node_id  # 出口节点ID
                else:
                    exit_node_id = request.form.get('exit_node_id')
                    if not exit_node_id:
                        flash('出口节点为必选项', 'danger')
                        return render_template('relay_add.html', exit_nodes=exit_nodes, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols

                    exit_node = Node.query.get_or_404(exit_node_id)
                    node_id = exit_node_id  # 出口节点ID
                    user = current_user  # 普通用户使用当前用户

                    entry_node = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).first()
                    if not entry_node:
                        flash('未配置入口节点', 'danger')
                        return render_template('relay_add.html', exit_nodes=exit_nodes, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols
                    entry_node_id = entry_node.id
                # 无论管理员还是用户，都需要entry_node_id
                if current_user.role != 'admin':
                    entry_node_id = entry_node.id

                # 调用 agent_control 函数
                success, message = agent_control(
                    protocol,
                    source,
                    destination,
                    entry_node,  # 入口节点对象
                    exit_node,  # 出口节点对象
                    current_user  # 当前用户
                )

                if success:
                    new_rule = Rule(
                        name=name,
                        source=source,
                        destination=destination,
                        protocol=protocol,
                        user_id=user.id,
                        node_id=node_id,  # 使用 node_id 而不是 server_id
                        entry_node_id=entry_node_id
                    )
                    db.session.add(new_rule)
                    db.session.commit()
                    flash('转发规则添加成功', 'success')
                    return redirect(url_for('index'))
                else:
                    flash(f'启动转发规则失败: {message}', 'danger')
                    return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols

            except Exception as e:
                db.session.rollback()
                flash(f'添加规则时发生错误: {str(e)}', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols) # 修改这里，传入 protocols

        if current_user.role == 'admin':
            return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)  # 修改这里，传入 protocols
        else:
            return render_template('relay_add.html', exit_nodes=exit_nodes, current_user=current_user, protocols=protocols)  # 修改这里，传入 protocols

    @app.route('/relay/edit/<int:rule_id>', methods=['GET', 'POST'])
    @login_required
    def edit_relay(rule_id):
        rule = Rule.query.get_or_404(rule_id)

        if current_user.role != 'admin' and rule.user_id != current_user.id:
            abort(403)

        entry_nodes = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).all()
        exit_nodes = Node.query.filter(or_(Node.role.like('%egress%'), Node.role == 'both')).all()
        users = User.query.all()
        protocols_config = load_protocols() #加载协议配置
        protocols = protocols_config.get('protocols', {}) if protocols_config else {} #获取protocols配置

        if request.method == 'POST':
            name = request.form.get('name')
            source = request.form.get('source')
            destination = request.form.get('destination')
            protocol = request.form.get('protocol')

            if not all([name, source, destination, protocol]):
                flash('所有字段均为必填项', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)

            if not (source.count(':') == 1 and destination.count(':') == 1):
                flash('源和目标地址格式错误，请使用 IP:端口 的格式', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)

            try:
                rule.name = name
                rule.source = source
                rule.destination = destination
                rule.protocol = protocol

                if current_user.role == 'admin':
                    entry_node_id = request.form.get('entry_node_id')
                    exit_node_id = request.form.get('exit_node_id')
                    user_id = request.form.get('user_id')

                    if not all([exit_node_id, user_id, entry_node_id]):
                        flash('管理员编辑规则时，入口、出口节点和关联用户为必选项', 'danger')
                        return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)

                    rule.user_id = user_id
                    rule.entry_node_id = entry_node_id
                    rule.node_id = exit_node_id  # 出口节点ID
                else:
                    exit_node_id = request.form.get('exit_node_id')
                    if not exit_node_id:
                        flash('出口节点为必选项', 'danger')
                        return render_template('relay_edit.html', rule=rule, exit_nodes=exit_nodes, current_user=current_user, protocols=protocols)
                    rule.node_id = exit_node_id  # 出口节点ID

                success, message = agent_control(
                    protocol,
                    source,
                    destination,
                    entry_nodes,
                    exit_nodes,
                    current_user
                )

                if success:
                    db.session.commit()
                    flash('转发规则更新成功', 'success')
                    return redirect(url_for('index'))
                else:
                    flash(f'启动转发规则失败: {message}', 'danger')
                    return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)
            except Exception as e:
                db.session.rollback()
                flash(f'编辑规则时发生错误: {str(e)}', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)

        return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)