import json
import logging
import os
from utils.mqtt.device_manager import DeviceManager # 引入 DeviceManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# evaluate_condition 函数保持不变...
def evaluate_condition(condition, data_value):
    op = condition['operator']
    threshold = condition['value']
    try:
        num_data_value = float(data_value)
        num_threshold = float(threshold)
        if op == '>': return num_data_value > num_threshold
        elif op == '<': return num_data_value < num_threshold
        elif op == '>=': return num_data_value >= num_threshold
        elif op == '<=': return num_data_value <= num_threshold
        elif op == '==': return num_data_value == num_threshold
        elif op == '!=': return num_data_value != num_threshold
        else:
            logging.warning(f"不支持的操作符: {op}")
            return False
    except (ValueError, TypeError) as e:
         if op == '==': return str(data_value) == str(threshold)
         elif op == '!=': return str(data_value) != str(threshold)
         else:
            logging.warning(f"无法对值 '{data_value}' 使用操作符 '{op}' 进行数字比较: {e}")
            return False

class RuleEngine:
    def __init__(self, device_manager: DeviceManager, rules_file="rules.json"):
        self.device_manager = device_manager
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.rules_file_path = os.path.join(script_dir, rules_file)
        self.rules = [] # Initialize as empty, load later
        self.action_handler = None
        self._load_rules() # Load rules during initialization

    def _load_rules(self):
        """从指定的 JSON 文件加载规则并更新内部列表。"""
        try:
            # --- 添加文件锁，防止并发读写问题 (如果可能在多线程环境调用) ---
            # import fcntl # Or portalocker on Windows/cross-platform
            # with open(self.rules_file_path, 'r+', encoding='utf-8') as f:
            #    fcntl.flock(f, fcntl.LOCK_SH) # Shared lock for reading
            #    rules_data = json.load(f)
            #    fcntl.flock(f, fcntl.LOCK_UN) # Unlock
            # --- 简化版，无锁 ---
            with open(self.rules_file_path, 'r', encoding='utf-8') as f:
                 rules_data = json.load(f)

            logging.info(f"从 {self.rules_file_path} 加载了 {len(rules_data)} 条规则定义。")
            # Filter enabled rules and store them
            self.rules = [rule for rule in rules_data if rule.get("enabled", False)]
            logging.info(f"{len(self.rules)} 条规则已启用并加载到引擎。")
            return True # Indicate success
        except FileNotFoundError:
            logging.warning(f"规则文件未找到: {self.rules_file_path}。规则列表将为空。")
            self.rules = []
            # Create an empty file if it doesn't exist? Optional.
            # with open(self.rules_file_path, 'w', encoding='utf-8') as f:
            #     json.dump([], f)
            return False
        except json.JSONDecodeError as e:
            logging.error(f"解码 {self.rules_file_path} 中的 JSON 时出错: {e}。规则未加载。")
            # Keep the old rules? Or clear them? Let's clear for safety.
            self.rules = []
            return False
        except Exception as e:
            logging.error(f"加载规则时发生意外错误: {e}。规则未加载。")
            self.rules = []
            return False

    def reload_rules(self):
        """重新从文件加载规则。"""
        logging.info("正在从文件重新加载规则...")
        return self._load_rules()

    # --- get_trigger_topics 不变 ---
    def get_trigger_topics(self):
        """返回当前已加载的启用规则的触发器主题集合。"""
        topics = set()
        # Iterate over the rules currently loaded in memory
        for rule in self.rules:
            # No need to check enabled again, as self.rules only contains enabled ones
            if "trigger" in rule and "topic" in rule["trigger"]:
                topics.add(rule["trigger"]["topic"])
        return list(topics)

    def set_action_handler(self, handler):
        self.action_handler = handler

    # get_trigger_topics 仍然有用，可以获取规则中明确写出的 topic
    def get_trigger_topics(self):
        """返回规则触发器中提到的唯一主题集合。"""
        topics = set()
        for rule in self.rules:
             # 也检查一下启用的规则
            if rule.get("enabled", False) and "trigger" in rule and "topic" in rule["trigger"]:
                topics.add(rule["trigger"]["topic"])
        return list(topics)

    def process_message(self, topic, payload_str):
        """根据规则处理传入的 MQTT 消息。"""
        if not self.action_handler:
            logging.warning("RuleEngine 中未设置动作处理器。")
            return

        try:
            payload_dict = json.loads(payload_str)
            logging.debug(f"处理主题 '{topic}' 上的消息: {payload_dict}")
        except json.JSONDecodeError:
            logging.warning(f"无法解码主题 '{topic}' 上的 JSON payload: {payload_str}")
            return

        for rule in self.rules:
            trigger = rule.get("trigger", {})
            trigger_topic = trigger.get("topic")
            condition = trigger.get("condition")

            # 检查主题是否匹配
            if topic == trigger_topic and condition:
                data_key = condition.get("data_key")
                data_value = None

                # --- 处理嵌套的 'params' ---
                trigger_device = None
                # 尝试根据 topic 找到对应的设备，以确定 payload 格式
                for dev_id, dev_info in self.device_manager.get_all_devices().items():
                     if dev_info.get("status_topic") == topic:
                         trigger_device = dev_info
                         break

                # 如果找到了设备并且格式是 'nested_params'
                if trigger_device and trigger_device.get("payload_format") == "nested_params":
                    if "params" in payload_dict and isinstance(payload_dict.get("params"), dict):
                        if data_key in payload_dict["params"]:
                            data_value = payload_dict["params"][data_key]
                # 否则，尝试直接在顶层查找 (兼容旧格式或简单格式)
                elif data_key in payload_dict:
                     data_value = payload_dict[data_key]
                # --- 结束处理嵌套 'params' ---


                if data_value is not None:
                    logging.debug(f"检查规则 '{rule.get('name', '未命名')}'，值为 {data_key}={data_value}")

                    if evaluate_condition(condition, data_value):
                        logging.info(f"规则 '{rule.get('name', '未命名')}' 已触发！")
                        action = rule.get("action")
                        if action:
                            # --- 处理动作 ---
                            action_type = action.get("type")

                            if action_type == "device_command":
                                device_id = action.get("device_id")
                                command_name = action.get("command")
                                params = action.get("params", {}) # 获取规则中定义的参数

                                if device_id and command_name:
                                    # 从 DeviceManager 获取命令主题和 payload 模板
                                    command_topic, payload_template = self.device_manager.get_command_details(device_id, command_name)

                                    if command_topic and payload_template is not None:
                                        # 使用模板和参数构建最终的 payload
                                        final_payload = self.device_manager.build_payload(payload_template, params)

                                        if final_payload is not None:
                                            # 准备要传递给 action_handler 的信息
                                            resolved_action = {
                                                "type": "mqtt_publish", # 最终都是发布 MQTT
                                                "topic": command_topic,
                                                "payload": final_payload
                                            }
                                            self.action_handler(resolved_action)
                                        else:
                                            logging.error(f"为规则 '{rule.get('name', '未命名')}' 构建 payload 失败。")
                                    else:
                                         logging.warning(f"无法为规则 '{rule.get('name', '未命名')}' 获取设备 '{device_id}' 的命令 '{command_name}' 详情。")
                                else:
                                     logging.warning(f"规则 '{rule.get('name', '未命名')}' 的 device_command 缺少 device_id 或 command。")

                            elif action_type == "mqtt_publish": # 保留直接发布的能力
                                if "topic" in action and "payload" in action:
                                     self.action_handler(action) # 直接传递
                                else:
                                     logging.warning(f"规则 '{rule.get('name', '未命名')}' 的 mqtt_publish 动作缺少 topic 或 payload。")

                            else:
                                logging.warning(f"规则 '{rule.get('name', '未命名')}' 中不支持的动作类型: {action_type}")
                        else:
                            logging.warning(f"规则 '{rule.get('name', '未命名')}' 已触发但未定义动作。")
                # else: 在 payload 中未找到 data_key
            # else: 主题不匹配或无条件