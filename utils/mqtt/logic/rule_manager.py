# utils/mqtt/logic/rule_manager.py

import json
import logging
import os
import uuid
# Use TYPE_CHECKING to avoid circular import issues if RuleEngine/MqttController
# also import something related to RuleManager in the future. For simple cases,
# direct import might work, but this is safer.
from typing import TYPE_CHECKING, List, Dict, Optional, Any

if TYPE_CHECKING:
    from rule_engine import RuleEngine # Adjust import path as needed
    from mqtt_controller import MqttController    # Adjust import path as needed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RuleManager:
    """
    Manages loading, saving, adding, modifying, and deleting rules
    stored in a JSON file and coordinates updates with RuleEngine and MqttController.
    """
    def __init__(self, rules_file_path: str, rule_engine: 'RuleEngine', mqtt_controller: 'MqttController'):
        """
        Initializes the RuleManager.

        Args:
            rules_file_path: The absolute path to the rules JSON file.
            rule_engine: An instance of the RuleEngine.
            mqtt_controller: An instance of the MqttController.
        """
        if not os.path.isabs(rules_file_path):
             logging.warning(f"Provided rules_file_path '{rules_file_path}' is not absolute. This might cause issues.")
        self.rules_file_path = rules_file_path
        self.rule_engine = rule_engine
        self.mqtt_controller = mqtt_controller
        logging.info(f"RuleManager initialized for file: {self.rules_file_path}")

    def _load_all_rules(self) -> Optional[List[Dict[str, Any]]]:
        """Loads all rules (enabled and disabled) from the JSON file."""
        try:
            # Consider adding file locking (e.g., fcntl or portalocker) here
            # for concurrent access safety if needed in the future.
            with open(self.rules_file_path, 'r', encoding='utf-8') as f:
                rules_list = json.load(f)
            logging.debug(f"Successfully loaded {len(rules_list)} rules definitions from {self.rules_file_path}")
            return rules_list
        except FileNotFoundError:
            logging.info(f"Rules file {self.rules_file_path} not found. Returning empty list.")
            return [] # Return empty list if file doesn't exist yet
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {self.rules_file_path}: {e}")
            return None # Indicate error by returning None
        except Exception as e:
            logging.error(f"Error reading rules file {self.rules_file_path}: {e}")
            return None

    def _save_all_rules(self, rules_list: List[Dict[str, Any]]) -> bool:
        """Saves the complete list of rules back to the JSON file."""
        try:
             # Consider adding file locking (e.g., fcntl or portalocker) here.
            with open(self.rules_file_path, 'w', encoding='utf-8') as f:
                json.dump(rules_list, f, indent=2, ensure_ascii=False)
            logging.info(f"Successfully saved {len(rules_list)} rules to {self.rules_file_path}")
            return True
        except IOError as e:
            logging.error(f"IOError writing rules file {self.rules_file_path}: {e}")
            return False
        except Exception as e:
            logging.error(f"Error writing rules file {self.rules_file_path}: {e}")
            return False

    def _trigger_runtime_update(self) -> bool:
        """Reloads rules in the engine and updates MQTT subscriptions."""
        if self.rule_engine.reload_rules():
            self.mqtt_controller.update_subscriptions()
            logging.debug("Rule engine reloaded and MQTT subscriptions updated.")
            return True
        else:
            logging.error("Failed to reload rules in the running engine after file update.")
            # Maybe log inconsistency between file and runtime state
            return False

    def add_rule(self, new_rule_data: Dict[str, Any]) -> bool:
        """
        Adds a new rule to the rules file and updates the runtime.

        Args:
            new_rule_data: Dictionary containing the new rule definition.
                           Should include 'name', 'enabled', 'trigger', 'action'.
                           An 'id' will be generated if not provided.

        Returns:
            True if the rule was successfully added and loaded, False otherwise.
        """
        if not all(k in new_rule_data for k in ['name', 'enabled', 'trigger', 'action']):
            logging.error("Add rule failed: Missing required keys (name, enabled, trigger, action).")
            return False

        # Ensure a unique ID
        if 'id' not in new_rule_data or not new_rule_data['id']:
            new_rule_data['id'] = str(uuid.uuid4())
            logging.info(f"Generated ID for new rule '{new_rule_data['name']}': {new_rule_data['id']}")

        all_rules = self._load_all_rules()
        if all_rules is None:
            logging.error("Add rule failed: Could not load existing rules.")
            return False

        # Check for duplicate ID or Name (adjust logic as needed)
        existing_ids = {rule.get('id') for rule in all_rules if rule.get('id')}
        existing_names = {rule.get('name') for rule in all_rules if rule.get('name')}
        if new_rule_data['id'] in existing_ids:
            logging.error(f"Add rule failed: Rule ID '{new_rule_data['id']}' already exists.")
            return False
        if new_rule_data['name'] in existing_names:
            logging.warning(f"Rule name '{new_rule_data['name']}' already exists. Adding anyway (ID is unique).")
            # Decide if this should be an error or just a warning

        all_rules.append(new_rule_data)

        if self._save_all_rules(all_rules):
            # Trigger update only after successful save
            if self._trigger_runtime_update():
                logging.info(f"Rule '{new_rule_data['name']}' (ID: {new_rule_data['id']}) added successfully.")
                return True
            else:
                # File saved, but runtime update failed
                return False # Indicate partial failure
        else:
            logging.error("Add rule failed: Could not save updated rules file.")
            return False

    def modify_rule(self, rule_identifier: str, updated_rule_data: Dict[str, Any], identifier_key: str = 'id') -> bool:
        """
        Modifies an existing rule identified by its ID or name.

        Args:
            rule_identifier: The ID or name of the rule to modify.
            updated_rule_data: Dictionary containing the complete updated rule definition.
                               Must include the key specified by `identifier_key`.
            identifier_key: The key ('id' or 'name') used to find the rule. Defaults to 'id'.

        Returns:
            True if the rule was successfully modified and reloaded, False otherwise.
        """
        if identifier_key not in updated_rule_data or updated_rule_data[identifier_key] != rule_identifier:
             logging.error(f"Modify rule failed: Identifier mismatch or missing key '{identifier_key}' in updated data.")
             # Make sure the identifier in the data matches the one passed to the function
             # This helps prevent accidentally changing the ID/Name used for lookup.
             # You could relax this if you want modify_rule to be able to change the identifier itself.
             # return False
             pass # Allow changing the identifier for now, but be cautious.


        all_rules = self._load_all_rules()
        if all_rules is None:
            logging.error("Modify rule failed: Could not load existing rules.")
            return False

        found_index = -1
        for i, rule in enumerate(all_rules):
            if rule.get(identifier_key) == rule_identifier:
                found_index = i
                break

        if found_index == -1:
            logging.error(f"Modify rule failed: Rule with {identifier_key} '{rule_identifier}' not found.")
            return False

        # --- Optional: Check for name conflicts if name is changed ---
        new_name = updated_rule_data.get('name')
        old_name = all_rules[found_index].get('name')
        if new_name and new_name != old_name:
            existing_names = {r.get('name') for i, r in enumerate(all_rules) if i != found_index and r.get('name')}
            if new_name in existing_names:
                 logging.error(f"Modify rule failed: New name '{new_name}' conflicts with another rule.")
                 return False
        # --- End Optional Name Conflict Check ---

        # Replace the rule in the list
        all_rules[found_index] = updated_rule_data
        logging.info(f"Preparing to update rule with {identifier_key} '{rule_identifier}'.")


        if self._save_all_rules(all_rules):
            if self._trigger_runtime_update():
                logging.info(f"Rule with {identifier_key} '{rule_identifier}' modified successfully.")
                return True
            else:
                 # File saved, but runtime update failed
                 return False
        else:
            logging.error("Modify rule failed: Could not save updated rules file.")
            return False

    def delete_rule(self, rule_identifier: str, identifier_key: str = 'id') -> bool:
        """
        Deletes a rule identified by its ID or name.

        Args:
            rule_identifier: The ID or name of the rule to delete.
            identifier_key: The key ('id' or 'name') used to find the rule. Defaults to 'id'.

        Returns:
            True if the rule was successfully deleted and runtime updated, False otherwise.
        """
        all_rules = self._load_all_rules()
        if all_rules is None:
            logging.error("Delete rule failed: Could not load existing rules.")
            return False

        initial_length = len(all_rules)
        rules_to_keep = [rule for rule in all_rules if rule.get(identifier_key) != rule_identifier]

        if len(rules_to_keep) == initial_length:
            logging.warning(f"Delete rule: Rule with {identifier_key} '{rule_identifier}' not found. No changes made.")
            return False # Indicate rule not found

        if self._save_all_rules(rules_to_keep):
            if self._trigger_runtime_update():
                 logging.info(f"Rule with {identifier_key} '{rule_identifier}' deleted successfully.")
                 return True
            else:
                 # File saved, but runtime update failed
                 return False
        else:
            logging.error("Delete rule failed: Could not save updated rules file.")
            return False

    def get_rule(self, rule_identifier: str, identifier_key: str = 'id') -> Optional[Dict[str, Any]]:
        """Gets a specific rule by its identifier."""
        all_rules = self._load_all_rules()
        if all_rules is None:
            return None
        for rule in all_rules:
            if rule.get(identifier_key) == rule_identifier:
                return rule
        return None

    def get_all_rules(self) -> Optional[List[Dict[str, Any]]]:
        """Gets all rules defined in the file."""
        return self._load_all_rules()