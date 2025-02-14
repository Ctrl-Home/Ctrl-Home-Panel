# agent_control.py
import requests
import yaml
from flask import jsonify
from models import db, User, Rule, Node  # Removed unnecessary NodeSoftware
import json
import os
import logging
import uuid

# Configure logging (consider moving this to a central location)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)


def gost_manage(operation_type, protocol_name, source, destination, landing_destination, entry_node, exit_node,
                current_user):
    logger.debug(
        f"gost_manage: Starting. Operation: {operation_type}, Protocol: {protocol_name}, Entry: {entry_node.ip_address}, Exit: {exit_node.ip_address}")

    entry_ip = entry_node.ip_address
    entry_port = source.split(":")[1]
    exit_ip = exit_node.ip_address
    exit_port = destination.split(":")[1]
    landing_ip = landing_destination.split(":")[0]
    landing_port = landing_destination.split(":")[1]

    if operation_type == 'add':
        # Generate new UUIDs for a new rule
        chain_uuid_val = str(uuid.uuid4())
        hop_uuid_val = str(uuid.uuid4())
        node_uuid_val = str(uuid.uuid4())
        entry_service_uuid_val = str(uuid.uuid4())  # Separate UUID for entry service
        exit_service_uuid_val = str(uuid.uuid4())  # Separate UUID for exit service
        target_uuid_val = str(uuid.uuid4())

        # For add operation, return the UUIDs
        rule_data = {
            'chain_uuid': chain_uuid_val,
            'hop_uuid': hop_uuid_val,
            'node_uuid': node_uuid_val,
            'entry_service_uuid': entry_service_uuid_val,
            'exit_service_uuid': exit_service_uuid_val,
            'target_uuid': target_uuid_val
        }
    elif operation_type == 'edit':
        # Retrieve existing rule from DB based on criteria (e.g., source and user)
        rule = Rule.query.filter_by(source=source, user_id=current_user.id).first()

        if not rule:
            return False, "Rule not found for editing.", None

        # Use existing UUIDs from the database
        chain_uuid_val = str(rule.chain_uuid)
        hop_uuid_val = str(rule.hop_uuid)
        node_uuid_val = str(rule.node_uuid)
        entry_service_uuid_val = str(rule.entry_service_uuid)  # Use entry_service_uuid
        exit_service_uuid_val = str(rule.exit_service_uuid)  # Use exit_service_uuid
        target_uuid_val = str(rule.target_uuid)
        rule_data = None  # No need to return UUIDs for edit
    else:
        return False, f"Invalid operation type: {operation_type}", None

    entry_base_url = f"http://{entry_ip}:18080"
    exit_base_url = f"http://{exit_ip}:18080"

    # Entry Service Configuration
    entry_service_url = f"{entry_base_url}/config/services"
    if operation_type == 'edit':
        entry_service_url += f"/{entry_service_uuid_val}"  # Use entry_service_uuid
    entry_service_payload = {
        "name": entry_service_uuid_val,  # Use entry_service_uuid
        "addr": f":{entry_port}",
        "handler": {
            "type": "tcp",
            "chain": chain_uuid_val
        },
        "listener": {
            "type": "tcp"
        }
    }

    # Entry Chain Configuration
    entry_chain_url = f"{entry_base_url}/config/chains"
    if operation_type == 'edit':
        entry_chain_url += f"/{chain_uuid_val}"
    entry_chain_payload = {
        "name": chain_uuid_val,
        "hops": [
            {
                "name": hop_uuid_val,
                "nodes": [
                    {
                        "name": node_uuid_val,
                        "addr": f"{exit_ip}:{exit_port}",
                        "connector": {
                            "type": "relay"
                        },
                        "dialer": {
                            "type": protocol_name,
                            "tls": {
                                "serverName": exit_ip
                            }
                        }
                    }
                ]
            }
        ]
    }

    # Exit Service Configuration
    exit_service_url = f"{exit_base_url}/config/services"
    if operation_type == 'edit':
        exit_service_url += f"/{exit_service_uuid_val}"  # Use exit_service_uuid
    exit_service_payload = {
        "name": exit_service_uuid_val,  # Use exit_service_uuid
        "addr": f":{exit_port}",  # Corrected: Use exit_port, not exit_service_uuid_val
        "handler": {
            "type": "relay"
        },
        "listener": {
            "type": protocol_name
        },
        "forwarder": {
            "nodes": [
                {
                    "name": "target-0",
                    "addr": f"{landing_ip}:{landing_port}"
                }
            ]
        }
    }
    def send_config_request(operation_type, url, payload):
        headers = {'Content-Type': 'application/json'}
        try:
            if operation_type == 'add':
                logger.debug(f"Sending POST request to: {url}, payload: {payload}")
                response = requests.post(url, headers=headers, data=json.dumps(payload))
            elif operation_type == 'edit':
                logger.debug(f"Sending PUT request to: {url}, payload: {payload}")
                response = requests.put(url, headers=headers, data=json.dumps(payload))
            elif operation_type == 'delete':
                logger.debug(f"Sending DELETE request to: {url}, payload: {payload}")
                response = requests.delete(url, headers=headers, data=json.dumps(payload))
            else:
                logger.error(f"Unknown operation_type: {operation_type}")
                return False, f"Unknown operation_type: {operation_type}"

            response.raise_for_status()
            logger.debug(f"{operation_type.upper()} request successful: {url}, Status Code: {response.status_code}")
            return True, f"{operation_type.upper()} request successful, Status Code: {response.status_code}"
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url}, Error: {e}")
            return False, f"Request failed: {e}"

    # Clear old config (Not needed with PUT)
    if operation_type == 'edit':
        pass  # Remove delete action

    # Send requests, checking for success
    success_entry_service, message_entry_service = send_config_request(operation_type, entry_service_url,
                                                                       entry_service_payload)
    if not success_entry_service:
        return False, f"Configuring entry service failed: {message_entry_service}", None

    success_entry_chain, message_entry_chain = send_config_request(operation_type, entry_chain_url, entry_chain_payload)
    if not success_entry_chain:
        return False, f"Configuring entry chain failed: {message_entry_chain}", None

    success_exit_service, message_exit_service = send_config_request(operation_type, exit_service_url,
                                                                     exit_service_payload)
    if not success_exit_service:
        return False, f"Configuring exit service failed: {message_exit_service}", None

    return True, f"Gost forwarding rule processed successfully (Operation: {operation_type})", rule_data

def agent_control(operation_type, protocol, source, destination, landing_destination, entry_node, exit_node,
                  current_user):
    logger.debug(
        f"agent_control: Starting. Operation: {operation_type}, Protocol: {protocol}, Source: {source}, Destination: {destination}, Landing: {landing_destination}")

    if protocol == 'wss' or protocol == 'wt':  # Simple string comparison
        return gost_manage(operation_type, protocol, source, destination, landing_destination, entry_node, exit_node,
                           current_user)
    else:
        logger.warning(f"Unsupported protocol: {protocol}")  # Log a warning
        return False, f"Unsupported protocol: {protocol}", None  # Return False for unsupported protocols