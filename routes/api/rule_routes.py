# rule_routes.py
# 这是一个Flask蓝图，用于管理智能家居设备的MQTT控制规则
import logging
import paho.mqtt.client as mqtt # 导入 MQTT 客户端库
from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from models import db, User, Rule, Node  # 导入数据库模型 (用户, 规则, 节点).  假设 Node 模型代表设备, Rule 模型代表控制规则
from sqlalchemy import or_
import re # 导入正则表达式库，可能用于输入验证

logger = logging.getLogger(__name__)

# MQTT Broker 配置 - 生产环境中应移至配置文件或环境变量
MQTT_BROKER_HOST = "broker.emqx.io" # MQTT Broker 主机地址 (替换成你的 MQTT broker 地址)
MQTT_BROKER_PORT = 1883 # MQTT Broker 端口，默认为 1883
MQTT_BROKER_USERNAME = "your_mqtt_username" # MQTT Broker 用户名 (如果你的 broker 需要身份验证，则填写)
MQTT_BROKER_PASSWORD = "your_mqtt_password" # MQTT Broker 密码 (如果你的 broker 需要身份验证，则填写)

# MQTT Topic 基础路径 - 定义智能家居设备 Topic 的基础路径
MQTT_TOPIC_BASE = "smart_home"

# 设备操作 - 定义智能家居设备可以执行的操作。根据实际设备能力进行调整。
DEVICE_ACTIONS = ["on", "off", "toggle", "brightness", "color"] # 示例操作：开，关，切换，亮度，颜色

def register_rule_routes(app):
    """
    注册设备控制相关的路由
    """

    def on_connect(client, userdata, flags, rc):
        """
        MQTT 连接回调函数
        当客户端连接到 MQTT Broker 后被调用
        """
        if rc == 0:
            logger.info("Connected to MQTT Broker!") # 连接成功日志
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}") # 连接失败日志

    # 初始化 MQTT 客户端 - 在路由函数外部初始化，以便复用
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect # 设置连接回调函数
    if MQTT_BROKER_USERNAME and MQTT_BROKER_PASSWORD:
        mqtt_client.username_pw_set(MQTT_BROKER_USERNAME, MQTT_BROKER_PASSWORD) # 设置用户名和密码 (如果需要)
    try:
        mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60) # 连接到 MQTT Broker
        mqtt_client.loop_start() # 启动 MQTT 客户端后台循环，处理重连和消息接收
    except Exception as e:
        logger.error(f"MQTT Client connection error: {e}") # 连接错误日志
        flash(f"Error: Could not connect to MQTT Broker.", 'danger') # 显示错误消息给用户


    @app.route('/device/control/add', methods=['GET', 'POST']) # 设备控制添加路由 (URL 路径已修改)
    @login_required
    def add_device_control(): # 添加设备控制规则函数 (函数名已修改)
        """
        添加新的设备控制规则
        """
        devices = Node.query.filter(Node.role.like('%device%')).all() # 查询所有角色包含 'device' 的节点，假设这些是智能家居设备
        users = User.query.all() # 查询所有用户
        actions = DEVICE_ACTIONS # 使用预定义的设备操作列表

        if request.method == 'POST': # 如果是 POST 请求 (提交表单)
            name = request.form.get('name') # 获取规则名称 (可以作为设备控制的名称)
            device_id = request.form.get('device_id') # 获取设备 ID (使用 device_id 代替 source/destination)
            action = request.form.get('action') # 获取要执行的操作
            parameters = request.form.get('parameters') # 获取操作参数 (可选，例如亮度/颜色值)

            if not all([name, device_id, action]): # 检查必填字段是否都已填写
                flash('Name, Device ID, and Action are required.', 'danger') # 显示错误消息
                return render_template('device_control_add.html', devices=devices, users=users, # 重新渲染添加规则页面，并回显用户输入
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)

            if action not in actions: # 验证用户选择的操作是否在允许的操作列表中
                flash('Invalid action selected.', 'danger') # 显示错误消息
                return render_template('device_control_add.html', devices=devices, users=users, # 重新渲染添加规则页面，并回显用户输入
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)


            try:
                if current_user.role == 'admin': # 如果是管理员用户
                    user_id = request.form.get('user_id') # 获取用户 ID (管理员可以为其他用户创建规则)
                    if not user_id: # 管理员角色需要选择用户
                        flash('Admin: User is required.', 'danger') # 显示错误消息
                        return render_template('device_control_add.html', devices=devices, # 重新渲染添加规则页面，并回显用户输入
                                               users=users, current_user=current_user, actions=actions,
                                               device_id=device_id, action=action, parameters=parameters, name=name)
                    user = User.query.get_or_404(user_id) # 获取指定用户，如果用户不存在则返回 404 错误
                else:
                    user = current_user # 非管理员用户，规则属于当前用户

                device_node = Node.query.get_or_404(device_id) # 获取设备节点，如果设备不存在则返回 404 错误

                # 构建 MQTT Topic - 根据你的 MQTT Topic 结构进行调整
                topic = f"{MQTT_TOPIC_BASE}/{device_node.name}/{action}" # 示例 Topic 结构： smart_home/设备名称/操作

                payload = parameters if parameters else "" # 如果有参数则使用参数作为 Payload，否则使用空字符串。 Payload 格式根据你的设备需求调整
                if action in ["brightness", "color"] and not parameters: # 亮度或颜色操作需要参数
                    flash(f'Parameter is required for action: {action}', 'danger') # 显示错误消息
                    return render_template('device_control_add.html', devices=devices, users=users, # 重新渲染添加规则页面，并回显用户输入
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)


                # 发布 MQTT 消息
                mqtt_client.publish(topic, payload) # 发布消息到 MQTT Broker
                logger.info(f"Published to topic: {topic}, payload: {payload}") # 记录日志
                flash(f'Sent command "{action}" to device "{device_node.name}". Topic: {topic}', 'success') # 显示成功消息给用户


                new_rule = Rule( # 创建新的规则对象 (重用 Rule 模型，调整字段) - 考虑将 Rule 模型重命名为 DeviceControl 或 Action 如果只用于设备控制
                    name=name,
                    device_id=device_id, # 存储设备 ID (Node ID)
                    action=action,
                    parameters=parameters, # 存储参数
                    user_id=user.id,
                    node_id=device_id # 仍然使用 node_id 关联到设备 Node，如果需要可以调整
                    # 移除 GOST 相关的字段： entry_node_id, chain_uuid 等
                )
                db.session.add(new_rule) # 添加新规则到数据库会话
                db.session.commit() # 提交数据库更改
                flash('Device control rule added successfully.', 'success') # 显示成功消息
                return redirect(url_for('index')) # 重定向到规则列表页面 (index 页面，假设是规则列表页)

            except Exception as e:
                db.session.rollback() # 发生异常时回滚数据库事务
                logger.exception(f"Error adding device control rule: {e}")  # 记录完整错误日志
                flash(f'An error occurred: {e}', 'danger') # 显示错误消息
                return render_template('device_control_add.html', devices=devices, users=users, # 重新渲染添加规则页面，并回显用户输入
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)

        return render_template('device_control_add.html', devices=devices, users=users, # 渲染添加规则页面，传递设备列表，用户列表，当前用户和操作列表
                               current_user=current_user, actions=actions) # 渲染设备控制添加页面 (模板名已修改)


    @app.route('/device/control/edit/<int:rule_id>', methods=['GET', 'POST']) # 设备控制编辑路由 (URL 路径已修改)
    @login_required
    def edit_device_control(rule_id): # 编辑设备控制规则函数 (函数名已修改)
        """
        编辑已有的设备控制规则
        """
        rule = Rule.query.get_or_404(rule_id) # 获取要编辑的规则，如果规则不存在则返回 404 错误

        if current_user.role != 'admin' and rule.user_id != current_user.id: # 检查用户权限，非管理员用户只能编辑自己的规则
            abort(403) # 如果没有权限，返回 403 错误 (禁止访问)

        devices = Node.query.filter(Node.role.like('%device%')).all() # 获取所有设备节点
        users = User.query.all() # 获取所有用户
        actions = DEVICE_ACTIONS # 获取设备操作列表

        if request.method == 'POST': # 如果是 POST 请求 (提交表单)
            name = request.form.get('name') # 获取规则名称
            device_id = request.form.get('device_id') # 获取设备 ID
            action = request.form.get('action') # 获取操作
            parameters = request.form.get('parameters') # 获取参数

            if not all([name, device_id, action]): # 检查必填字段
                flash('Name, Device ID, and Action are required.', 'danger') # 显示错误消息
                return render_template('device_control_edit.html', rule=rule, devices=devices, users=users, # 重新渲染编辑页面，并回显用户输入和当前规则信息
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)
            if action not in actions: # 验证操作是否合法
                flash('Invalid action selected.', 'danger') # 显示错误消息
                return render_template('device_control_edit.html', rule=rule, devices=devices, users=users, # 重新渲染编辑页面，并回显用户输入和当前规则信息
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)
            if action in ["brightness", "color"] and not parameters: # 亮度或颜色操作需要参数
                    flash(f'Parameter is required for action: {action}', 'danger') # 显示错误消息
                    return render_template('device_control_edit.html', rule=rule, devices=devices, users=users, # 重新渲染编辑页面，并回显用户输入和当前规则信息
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)


            try:
                rule.name = name # 更新规则名称
                rule.device_id = device_id # 更新设备 ID (Node ID)
                rule.action = action # 更新操作
                rule.parameters = parameters # 更新参数

                if current_user.role == 'admin': # 如果是管理员用户
                    user_id = request.form.get('user_id') # 获取用户 ID
                    if not user_id: # 管理员角色需要选择用户
                        flash('Admin: User is required.', 'danger') # 显示错误消息
                        return render_template('device_control_edit.html', rule=rule, devices=devices, # 重新渲染编辑页面，并回显用户输入和当前规则信息
                                               users=users, current_user=current_user, actions=actions,
                                               device_id=device_id, action=action, parameters=parameters, name=name)
                    rule.user_id = user_id # 更新规则所属用户


                device_node = Node.query.get_or_404(device_id) # 获取设备节点

                # 构建 MQTT Topic
                topic = f"{MQTT_TOPIC_BASE}/{device_node.name}/{action}" # 构建 Topic
                payload = parameters if parameters else "" # 获取 Payload

                # 发布 MQTT 消息
                mqtt_client.publish(topic, payload) # 发布消息
                logger.info(f"Published to topic: {topic}, payload: {payload} for edit rule id: {rule_id}") # 记录日志
                flash(f'Sent command "{action}" to device "{device_node.name}". Topic: {topic} (Rule updated)', 'success') # 显示成功消息


                db.session.commit() # 提交数据库更改
                flash('Device control rule updated successfully.', 'success') # 显示成功消息
                return redirect(url_for('index')) # 重定向到规则列表页面
            except Exception as e:
                db.session.rollback() # 回滚数据库事务
                logger.exception(f"Error editing device control rule: {e}")  # 记录错误日志
                flash(f'An error occurred: {e}', 'danger') # 显示错误消息
                return render_template('device_control_edit.html', rule=rule, devices=devices, users=users, # 重新渲染编辑页面，并回显用户输入和当前规则信息
                                       current_user=current_user, actions=actions,
                                       device_id=device_id, action=action, parameters=parameters,
                                       name=name)

        return render_template('device_control_edit.html', rule=rule, devices=devices, users=users, # 渲染设备控制编辑页面，传递规则信息，设备列表，用户列表，当前用户和操作列表
                               current_user=current_user, actions=actions) # 渲染设备控制编辑页面 (模板名已修改)


    @app.route('/device/control/reload/<int:rule_id>', methods=['POST']) # 设备控制重新加载路由 (重新加载功能对于 MQTT 控制可能不适用)
    @login_required
    def reload_device_control(rule_id): # 重新加载设备控制规则函数 (函数名已修改, 功能需要重新考虑)
        """
        重新加载设备控制规则 (对于 MQTT 控制，此功能可能需要重新定义，例如设备状态刷新)
        """
        flash('Reload function is not directly applicable to MQTT device control in the same way. Consider device status refresh or other relevant actions.', 'warning') # 显示警告消息，说明 reload 功能不直接适用于 MQTT 设备控制
        return redirect(url_for('index')) # 重定向到规则列表页面。 如果实现了设备状态刷新或其他类似功能，则需要调整此函数。
        # rule = Rule.query.get_or_404(rule_id) # 原始 GOST reload 逻辑 - MQTT 控制不需要
        # if current_user.role != 'admin' and rule.user_id != current_user.id:
        #     abort(403)
        # # ... (GOST reload 逻辑已移除) ...
        # return redirect(url_for('index'))


    @app.route('/device/control/delete/<int:rule_id>', methods=['POST']) # 设备控制删除路由 (URL 路径已修改)
    @login_required
    def delete_device_control(rule_id): # 删除设备控制规则函数 (函数名已修改)
        """
        删除设备控制规则
        """
        rule = Rule.query.get_or_404(rule_id) # 获取要删除的规则

        if current_user.role != 'admin' and rule.user_id != current_user.id: # 检查用户权限
            abort(403) # 没有权限返回 403 错误
        try:
            db.session.delete(rule) # 从数据库会话中删除规则
            db.session.commit() # 提交数据库更改
            flash('Device control rule deleted successfully.', 'success') # 显示成功消息

        except Exception as e:
            db.session.rollback() # 回滚数据库事务
            logger.exception(f"Error deleting device control rule: {e}") # 记录错误日志
            flash(f'Failed to delete device control rule: {e}', 'danger') # 显示错误消息

        return redirect(url_for('index')) # 重定向到规则列表页面

    # 应用上下文结束时关闭 MQTT 连接 (可选，但建议实践)
    @app.teardown_appcontext
    def close_mqtt_client(exception):
        """
        Flask 应用上下文结束时执行的函数，用于关闭 MQTT 客户端连接
        """
        if mqtt_client:
            mqtt_client.loop_stop() # 停止 MQTT 客户端后台循环
            mqtt_client.disconnect() # 断开 MQTT 连接
