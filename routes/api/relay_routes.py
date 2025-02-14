# relay_routes.py
from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from models import db, User, Rule, Node  # Removed unnecessary NodeSoftware
from sqlalchemy import or_
import yaml
import re
from utils.agent.agent_control import agent_control
import logging

logger = logging.getLogger(__name__)

def load_protocols(file_path="utils/gost/protocols.yaml"):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Protocol file not found: {file_path}")
        flash(f"Error: Protocol configuration file not found.", 'danger')
        return None
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        flash(f"Error: Could not parse protocol configuration file.", 'danger')
        return None
    except Exception as e:
        logger.exception(f"Unexpected error loading protocols: {e}")  # Log full traceback
        flash(f"An unexpected error occurred.", 'danger')
        return None

def register_relay_routes(app):
    @app.route('/relay/add', methods=['GET', 'POST'])
    @login_required
    def add_relay():
        entry_nodes = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).all()
        exit_nodes = Node.query.filter(or_(Node.role.like('%egress%'), Node.role == 'both')).all()
        users = User.query.all()
        protocols_config = load_protocols()
        protocols = protocols_config.get('protocols', {}) if protocols_config else {}

        if request.method == 'POST':
            name = request.form.get('name')
            source = request.form.get('source')
            destination = request.form.get('destination')
            landing_destination = request.form.get('landing_destination')
            protocol = request.form.get('protocol')

            if not all([name, source, destination, landing_destination, protocol]):
                flash('All fields are required.', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            ip_port_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$')
            if not ip_port_pattern.match(source) or not ip_port_pattern.match(destination) or not ip_port_pattern.match(landing_destination):
                flash('Invalid format for source, destination, or landing address. Use IP:Port format.', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            try:
                if current_user.role == 'admin':
                    entry_node_id = request.form.get('entry_node_id')
                    exit_node_id = request.form.get('exit_node_id')
                    user_id = request.form.get('user_id')

                    if not all([exit_node_id, user_id, entry_node_id]):
                        flash('Admin: Entry node, exit node, and user are required.', 'danger')
                        return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

                    user = User.query.get_or_404(user_id)
                    entry_node = Node.query.get_or_404(entry_node_id)
                    exit_node = Node.query.get_or_404(exit_node_id)

                else:
                    exit_node_id = request.form.get('exit_node_id')
                    if not exit_node_id:
                        flash('Exit node is required.', 'danger')
                        return render_template('relay_add.html', exit_nodes=exit_nodes, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

                    exit_node = Node.query.get_or_404(exit_node_id)
                    user = current_user

                    entry_node = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).first()
                    if not entry_node:
                        flash('No ingress node configured. Contact an administrator.', 'danger')
                        return render_template('relay_add.html', exit_nodes=exit_nodes, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)
                    entry_node_id = entry_node.id


                success, message, rule_data = agent_control(
                    'add',  # Correct operation_type for adding
                    protocol,
                    source,
                    destination,
                    landing_destination,
                    entry_node,
                    exit_node,
                    current_user
                )

                if success:
                    new_rule = Rule(
                        name=name,
                        source=source,
                        destination=destination,
                        landing_destination=landing_destination,  # Store landing_destination, Remove this line if landing_destination is not in your Rule model.
                        protocol=protocol,
                        user_id=user.id,
                        node_id=exit_node.id,
                        entry_node_id=entry_node.id,
                        chain_uuid=rule_data['chain_uuid'],
                        hop_uuid=rule_data['hop_uuid'],
                        node_uuid=rule_data['node_uuid'],
                        entry_service_uuid=rule_data['entry_service_uuid'],
                        exit_service_uuid=rule_data['exit_service_uuid'],
                        target_uuid=rule_data['target_uuid']
                    )
                    db.session.add(new_rule)
                    db.session.commit()
                    flash('Relay rule added successfully.', 'success')
                    return redirect(url_for('index'))
                else:
                    flash(f'Failed to create relay rule: {message}', 'danger')
                    return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                           source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            except Exception as e:
                db.session.rollback()
                logger.exception(f"Error adding relay rule: {e}")  # Log full traceback
                flash(f'An error occurred: {e}', 'danger')
                return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

        return render_template('relay_add.html', entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)


    @app.route('/relay/edit/<int:rule_id>', methods=['GET', 'POST'])
    @login_required
    def edit_relay(rule_id):
        rule = Rule.query.get_or_404(rule_id)

        if current_user.role != 'admin' and rule.user_id != current_user.id:
            abort(403)

        entry_nodes = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).all()
        exit_nodes = Node.query.filter(or_(Node.role.like('%egress%'), Node.role == 'both')).all()
        users = User.query.all()
        protocols_config = load_protocols()
        protocols = protocols_config.get('protocols', {}) if protocols_config else {}

        if request.method == 'POST':
            name = request.form.get('name')
            source = request.form.get('source')
            destination = request.form.get('destination')
            landing_destination = request.form.get('landing_destination')
            protocol = request.form.get('protocol')

            if not all([name, source, destination, landing_destination, protocol]):
                flash('All fields are required.', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            ip_port_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$')
            if not ip_port_pattern.match(source) or not ip_port_pattern.match(destination) or not ip_port_pattern.match(landing_destination):
                flash('Invalid format for source, destination, or landing address. Use IP:Port format.', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            try:
                rule.name = name
                rule.source = source
                rule.destination = destination
                # rule.landing_destination = landing_destination  # Update landing_destination, Remove this line if landing_destination is not in your Rule model.
                rule.protocol = protocol

                if current_user.role == 'admin':
                    entry_node_id = request.form.get('entry_node_id')
                    exit_node_id = request.form.get('exit_node_id')
                    user_id = request.form.get('user_id')

                    if not all([exit_node_id, user_id, entry_node_id]):
                        flash('Admin: Entry node, exit node, and user are required.', 'danger')
                        return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

                    rule.user_id = user_id
                    entry_node = Node.query.get_or_404(entry_node_id)
                    exit_node = Node.query.get_or_404(exit_node_id)
                    rule.node_id = exit_node.id
                    rule.entry_node_id = entry_node.id

                else:
                    exit_node_id = request.form.get('exit_node_id')
                    if not exit_node_id:
                        flash('Exit node is required.', 'danger')
                        return render_template('relay_edit.html', rule=rule, exit_nodes=exit_nodes, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)
                    exit_node = Node.query.get_or_404(exit_node_id)
                    rule.node_id = exit_node.id

                    entry_node = Node.query.filter(or_(Node.role.like('%ingress%'), Node.role == 'both')).first()
                    if not entry_node:
                        flash('No ingress node configured. Contact an administrator.', 'danger')
                        return render_template('relay_edit.html', rule=rule, exit_nodes=exit_nodes, current_user=current_user, protocols=protocols,
                                               source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)
                    rule.entry_node_id = entry_node.id


                success, message, _ = agent_control(
                    'edit',  # Correct operation_type for editing
                    protocol,
                    source,
                    destination,
                    landing_destination,
                    entry_node,
                    exit_node,
                    current_user
                )

                if success:
                    db.session.commit()
                    flash('Relay rule updated successfully.', 'success')
                    return redirect(url_for('index'))
                else:
                    flash(f'Failed to update relay rule: {message}', 'danger')
                    return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                           source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

            except Exception as e:
                db.session.rollback()
                logger.exception(f"Error editing relay rule: {e}")  # Log full traceback
                flash(f'An error occurred: {e}', 'danger')
                return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols,
                                       source=source, destination=destination, landing_destination=landing_destination, name=name, protocol=protocol)

        return render_template('relay_edit.html', rule=rule, entry_nodes=entry_nodes, exit_nodes=exit_nodes, users=users, current_user=current_user, protocols=protocols)