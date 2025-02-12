from flask import Flask, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, User, Rule, Server

def register_relay_routes(app):
    @app.route('/relay/add', methods=['GET', 'POST'])
    @login_required
    def add_relay():
        entry_servers = Server.query.filter_by(server_type='entry').all()
        exit_servers = Server.query.filter_by(server_type='exit').all()
        users = User.query.all()

        if request.method == 'POST':
            name = request.form['name']
            source = request.form['source']
            destination = request.form['destination']
            protocol = request.form['protocol']

            if current_user.role == 'admin':
                entry_server_id = request.form.get('entry_server_id')
                exit_server_id = request.form['exit_server_id']
                user_id = request.form['user_id']

                if not exit_server_id or not user_id:
                    flash('管理员添加规则时，出口服务器和关联用户为必选项', 'danger')
                    return render_template('relay_add.html', entry_servers=entry_servers, exit_servers=exit_servers, users=users, current_user=current_user)

                server_id = exit_server_id
                user = User.query.get(user_id)
                server = Server.query.get(server_id)
                if not user or not server:
                    flash('无效的用户ID或服务器ID', 'danger')
                    return render_template('relay_add.html', entry_servers=entry_servers, exit_servers=exit_servers, users=users, current_user=current_user)

            else:
                exit_server_id = request.form['exit_server_id']
                server_id = exit_server_id
                user_id = current_user.id

                if not exit_server_id:
                    flash('出口服务器为必选项', 'danger')
                    return render_template('relay_add.html', exit_servers=exit_servers, current_user=current_user)

                server = Server.query.get(server_id)
                user = current_user
                if not server:
                    flash('无效的服务器ID', 'danger')
                    return render_template('relay_add.html', exit_servers=exit_servers, current_user=current_user)

            new_rule = Rule(
                name=name,
                source=source,
                destination=destination,
                protocol=protocol,
                user_id=user_id,
                server_id=server_id
            )
            db.session.add(new_rule)
            db.session.commit()
            flash('转发规则添加成功', 'success')
            return redirect(url_for('index'))

        if current_user.role == 'admin':
            return render_template('relay_add.html', entry_servers=entry_servers, exit_servers=exit_servers, users=users, current_user=current_user)
        else:
            allowed_exit_server_ids_str = current_user.permission_group.allowed_exit_servers if current_user.permission_group else ''
            allowed_exit_server_ids = [int(id) for id in allowed_exit_server_ids_str.split(',') if id] if allowed_exit_server_ids_str else []
            filtered_exit_servers = [server for server in exit_servers if server.id in allowed_exit_server_ids]

            return render_template('relay_add.html', exit_servers=filtered_exit_servers, current_user=current_user)