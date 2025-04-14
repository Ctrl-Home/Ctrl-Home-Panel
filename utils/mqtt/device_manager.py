import json
import logging
import os # 引入 os 模块
import copy
from typing import Dict, List, Any, Optional, Union

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DeviceManager:
    def __init__(self, devices_file="devices.json"):
        # 使用 os.path.join 来构建绝对路径，确保在任何地方运行脚本都能找到文件
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.devices_file_path = os.path.join(script_dir, devices_file)
        self.devices = self._load_devices()

    def _load_devices(self):
        """从 JSON 文件加载设备定义。"""
        try:
            with open(self.devices_file_path, 'r', encoding='utf-8') as f:
                devices_data = json.load(f)
                logging.info(f"从 {self.devices_file_path} 成功加载 {len(devices_data)} 个设备定义。")
                return devices_data
        except FileNotFoundError:
            logging.error(f"设备文件未找到: {self.devices_file_path}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"解码 {self.devices_file_path} 中的 JSON 时出错: {e}")
            return {}
        except Exception as e:
            logging.error(f"加载设备时发生意外错误: {e}")
            return {}

    def _save_devices(self) -> bool:
        """将设备定义保存到 JSON 文件。"""
        try:
            with open(self.devices_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.devices, f, indent=2, ensure_ascii=False)
            logging.info(f"成功保存 {len(self.devices)} 个设备定义到 {self.devices_file_path}")
            return True
        except Exception as e:
            logging.error(f"保存设备定义时出错: {e}")
            return False

    def get_device(self, device_id):
        """根据设备 ID 获取设备信息。"""
        return self.devices.get(device_id)

    def get_all_devices(self):
        """获取所有设备信息。"""
        return self.devices

    def get_status_topics(self):
        """获取所有传感器类型设备的 status_topic 列表。"""
        topics = set()
        for device_id, device_info in self.devices.items():
            if device_info.get("type") == "sensor" and "status_topic" in device_info:
                topics.add(device_info["status_topic"])
        return list(topics)

    def get_command_details(self, device_id, command_name):
        """获取设备的命令主题和该命令的 payload 模板。"""
        device = self.get_device(device_id)
        if not device:
            logging.warning(f"未找到设备 ID: {device_id}")
            return None, None

        command_topic = device.get("command_topic")
        commands = device.get("commands", {})
        command_info = commands.get(command_name)

        if not command_topic:
             logging.warning(f"设备 {device_id} 未定义 command_topic。")
             return None, None

        if not command_info:
            logging.warning(f"设备 {device_id} 不支持命令: {command_name}")
            return None, None

        payload_template = command_info.get("payload_template")
        return command_topic, payload_template

    def add_device(self, device_data: Dict[str, Any]) -> Union[Dict[str, Any], Dict[str, str]]:
        """
        添加一个新设备。

        Args:
            device_data: 包含设备定义的字典

        Returns:
            成功: 添加的设备字典
            失败: 包含错误信息的字典
        """
        # 基本验证
        if not isinstance(device_data, dict):
            return {"error": "设备数据必须是字典格式"}
        
        device_id = device_data.get("id")
        if not device_id:
            return {"error": "设备必须包含 id 字段"}
        
        # 检查是否已存在同ID设备
        if device_id in self.devices:
            return {"error": f"设备ID '{device_id}' 已存在"}
        
        # 验证必填字段
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in device_data:
                return {"error": f"缺少必填字段: {field}"}
        
        # 根据设备类型验证其他必填字段
        device_type = device_data.get("type")
        if device_type == "sensor":
            if "status_topic" not in device_data:
                return {"error": "传感器设备必须包含 status_topic 字段"}
            if "data_fields" not in device_data:
                return {"error": "传感器设备必须定义 data_fields (数据字段)"}
        elif device_type == "actuator":
            if "status_topic" not in device_data:
                return {"error": "执行器设备必须包含 status_topic 字段"}
            if "command_topic" not in device_data:
                return {"error": "执行器设备必须包含 command_topic 字段"}
            if "commands" not in device_data or not device_data["commands"]:
                return {"error": "执行器设备必须定义至少一个 command (命令)"}
        else:
            return {"error": f"不支持的设备类型: {device_type}，支持的类型: sensor, actuator"}

        # 添加设备并保存
        self.devices[device_id] = device_data
        if self._save_devices():
            return device_data
        else:
            # 如果保存失败，回滚更改
            if device_id in self.devices:
                del self.devices[device_id]
            return {"error": "设备保存失败"}

    def update_device(self, device_id: str, updated_data: Dict[str, Any]) -> Union[Dict[str, Any], Dict[str, str]]:
        """
        更新现有设备的信息。

        Args:
            device_id: 要更新的设备ID
            updated_data: 更新后的设备数据

        Returns:
            成功: 更新后的设备字典
            失败: 包含错误信息的字典
        """
        # 检查设备是否存在
        if device_id not in self.devices:
            return {"error": f"设备ID '{device_id}' 不存在"}
        
        # 不允许修改设备ID
        if "id" in updated_data and updated_data["id"] != device_id:
            return {"error": "不允许修改设备ID"}
        
        # 保存原始设备数据（用于失败时回滚）
        original_device = copy.deepcopy(self.devices[device_id])
        
        # 根据设备类型验证必要字段
        if "type" in updated_data:
            device_type = updated_data["type"]
            if device_type not in ["sensor", "actuator"]:
                return {"error": f"不支持的设备类型: {device_type}"}
            
            # 如果类型发生变化，检查必填字段
            if device_type != original_device.get("type"):
                if device_type == "sensor":
                    if "status_topic" not in updated_data and "status_topic" not in original_device:
                        return {"error": "传感器设备必须包含 status_topic 字段"}
                    if "data_fields" not in updated_data and "data_fields" not in original_device:
                        return {"error": "传感器设备必须定义 data_fields (数据字段)"}
                elif device_type == "actuator":
                    if "status_topic" not in updated_data and "status_topic" not in original_device:
                        return {"error": "执行器设备必须包含 status_topic 字段"}
                    if "command_topic" not in updated_data and "command_topic" not in original_device:
                        return {"error": "执行器设备必须包含 command_topic 字段"}
                    if "commands" not in updated_data and "commands" not in original_device:
                        return {"error": "执行器设备必须定义至少一个 command (命令)"}
        
        # 更新设备数据
        # 注意：这里使用字典合并，保留原始字段
        merged_data = {**original_device, **updated_data}
        merged_data["id"] = device_id  # 确保ID不变
        
        # 更新并保存
        self.devices[device_id] = merged_data
        if self._save_devices():
            return merged_data
        else:
            # 保存失败，回滚更改
            self.devices[device_id] = original_device
            return {"error": "设备保存失败"}

    def delete_device(self, device_id: str) -> Dict[str, Any]:
        """
        删除指定的设备。

        Args:
            device_id: 要删除的设备ID

        Returns:
            包含操作结果的字典
        """
        # 检查设备是否存在
        if device_id not in self.devices:
            return {"error": f"设备ID '{device_id}' 不存在"}
        
        # 保存原始设备数据（用于失败时回滚）
        original_device = copy.deepcopy(self.devices[device_id])
        
        # 删除设备
        del self.devices[device_id]
        
        # 保存更改
        if self._save_devices():
            return {"success": True, "message": f"设备 '{device_id}' 已成功删除"}
        else:
            # 保存失败，回滚更改
            self.devices[device_id] = original_device
            return {"error": "设备删除失败，无法保存更改"}

    def build_payload(self, payload_template, params):
        """根据模板和参数构建最终的 MQTT payload。"""
        if isinstance(payload_template, dict):
            payload = {}
            try:
                # 遍历模板字典
                for key, value_template in payload_template.items():
                    # 如果值是字符串并且包含占位符，尝试格式化
                    if isinstance(value_template, str) and '{' in value_template and '}' in value_template:
                         # 使用 params 中的值替换占位符
                        payload[key] = value_template.format(**params)
                        # 尝试转换类型（例如 "25" -> 25）
                        try:
                            # 尝试转整数
                            payload[key] = int(payload[key])
                        except ValueError:
                            try:
                                # 尝试转浮点数
                                payload[key] = float(payload[key])
                            except ValueError:
                                # 保持字符串
                                pass
                    else:
                         # 如果不是带占位符的字符串，直接使用模板中的值
                        payload[key] = value_template
                return payload
            except KeyError as e:
                logging.error(f"构建 payload 失败：参数中缺少键 {e}，模板为 {payload_template}, 参数为 {params}")
                return None
            except Exception as e:
                 logging.error(f"构建 payload 时发生错误: {e}, 模板为 {payload_template}, 参数为 {params}")
                 return None
        else:
            # 如果模板不是字典（可能是一个简单的值），直接返回值（可能需要调整）
            logging.warning(f"Payload 模板不是预期的字典格式: {payload_template}")
            return payload_template # 或者根据需要返回 None

# --- 示例用法 ---
if __name__ == '__main__':
    # 测试 DeviceManager
    manager = DeviceManager()
    print("所有设备:")
    print(manager.get_all_devices())
    print("\n传感器状态主题:")
    print(manager.get_status_topics())
    print("\n获取客厅空调信息:")
    print(manager.get_device("ac_livingroom"))
    print("\n获取卧室灯信息:")
    print(manager.get_device("light_bedroom"))

    print("\n获取空调 set_state_temp 命令详情:")
    topic, template = manager.get_command_details("ac_livingroom", "set_state_temp")
    print(f"Topic: {topic}, Template: {template}")
    if template:
        params = {"state": "cool", "target_temp": 22}
        payload = manager.build_payload(template, params)
        print(f"构建的 Payload ({type(payload['target_temp'])}): {payload}") # 检查类型

    print("\n获取空调 turn_off 命令详情:")
    topic_off, template_off = manager.get_command_details("ac_livingroom", "turn_off")
    print(f"Topic: {topic_off}, Template: {template_off}")
    if template_off:
         payload_off = manager.build_payload(template_off, {}) # 无需参数
         print(f"构建的 Payload: {payload_off}")

    print("\n获取灯 set_state 命令详情:")
    topic_light, template_light = manager.get_command_details("light_bedroom", "set_state")
    print(f"Topic: {topic_light}, Template: {template_light}")
    if template_light:
        params_on = {"state": "on"}
        payload_on = manager.build_payload(template_light, params_on)
        print(f"构建的 Payload (开): {payload_on}")
        params_off = {"state": "off"}
        payload_off = manager.build_payload(template_light, params_off)
        print(f"构建的 Payload (关): {payload_off}")

    print("\n尝试获取不存在的命令:")
    topic_x, template_x = manager.get_command_details("ac_livingroom", "non_existent_cmd")
    print(f"Topic: {topic_x}, Template: {template_x}")

    print("\n尝试使用缺少参数构建:")
    topic, template = manager.get_command_details("ac_livingroom", "set_state_temp")
    if template:
        params_bad = {"state": "heat"} # 缺少 target_temp
        payload_bad = manager.build_payload(template, params_bad)
        print(f"构建的 Payload (错误): {payload_bad}")