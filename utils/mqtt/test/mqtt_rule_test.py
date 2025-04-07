# ==============================================================================
# ======================= 规则管理测试函数 ====================================
# ==============================================================================
import logging
import time

from utils.mqtt.logic.rule_manager import RuleManager


def test_rule_management(rule_manager: RuleManager):
    """
    用于测试 RuleManager 的添加、修改、删除规则功能的独立函数。

    Args:
        rule_manager: 一个已经初始化好的 RuleManager 实例。
    """
    logging.info("----- 开始执行规则管理测试 -----")

    added_rule_id = None # 用于存储成功添加的规则的ID

    # --- 1. 测试添加规则 ---
    logging.info("[测试步骤 1/3] 尝试添加新规则...")
    new_light_rule_data = {
        # 'id' 会在 add_rule 内部自动生成（如果未提供）
        "name": "测试规则：低温开灯",  # 规则名称
        "enabled": True,          # 规则是否启用
        "trigger": {              # 触发条件
            "topic": "/device/test/sensor123/status", # 监听的 MQTT 主题
            "condition": {        # 具体条件
                "data_key": "temperature", # 关心的 payload 中的数据键 (在 params 下)
                "operator": "<",           # 比较操作符
                "value": 15                # 阈值
            }
        },
        "action": {               # 触发后执行的动作
            "type": "device_command",     # 动作类型：控制设备
            "device_id": "light_bedroom", # 目标设备的 ID (来自 devices.json)
            "command": "set_state",       # 要执行的命令 (来自 devices.json)
            "params": {                   # 命令所需的参数
                "state": "on"
            }
        }
    }

    # 调用 RuleManager 的 add_rule 方法
    if rule_manager.add_rule(new_light_rule_data):
        added_rule_id = new_light_rule_data.get('id') # 获取生成的 ID
        print(f"✅ 成功添加规则 '{new_light_rule_data['name']}'，ID为: {added_rule_id}")
    else:
        print(f"❌ 添加规则 '{new_light_rule_data['name']}' 失败。")

    time.sleep(1) # 短暂暂停，模拟操作间隔

    # --- 2. 测试修改规则 ---
    logging.info("[测试步骤 2/3] 尝试修改刚才添加的规则...")
    if added_rule_id: # 仅在成功添加后才尝试修改
        modified_light_rule_data = {
            "id": added_rule_id, # 必须提供要修改规则的ID
            "name": "测试规则：低温开灯(已修改并禁用)", # 修改名称
            "enabled": False, # 修改为禁用状态
            "trigger": {
                "topic": "/device/test/sensor123/status", # 主题一般不变
                "condition": {
                    "data_key": "temperature",
                    "operator": "<",
                    "value": 10 # 修改阈值为 10
                }
            },
            "action": { # 动作部分可以不变，也可以修改
                "type": "device_command",
                "device_id": "light_bedroom",
                "command": "set_state",
                "params": { "state": "on" }
            }
        }
        # 调用 RuleManager 的 modify_rule 方法，通过 ID 识别
        if rule_manager.modify_rule(added_rule_id, modified_light_rule_data, identifier_key='id'):
            print(f"✅ 成功修改规则 ID: {added_rule_id}。")
        else:
            print(f"❌ 修改规则 ID: {added_rule_id} 失败。")
    else:
        print("⚠️ 跳过修改规则测试，因为添加步骤失败或未获取到ID。")

    time.sleep(1)

    # --- 3. 测试删除规则 ---
    logging.info("[测试步骤 3/3] 尝试删除刚才添加并修改的规则...")
    if added_rule_id: # 仅在有 ID 时尝试删除
        # 调用 RuleManager 的 delete_rule 方法，通过 ID 删除
        if rule_manager.delete_rule(added_rule_id, identifier_key='id'):
            print(f"✅ 成功删除规则 ID: {added_rule_id}。")
        else:
            print(f"❌ 删除规则 ID: {added_rule_id} 失败 (可能已被删除或未找到)。")
    else:
        print("⚠️ 跳过删除规则测试，因为添加步骤失败或未获取到ID。")

    # --- 附加测试：尝试删除一个可能存在的旧规则 (按名称) ---
    # 这有助于清理测试环境，即使前面的步骤失败了
    logging.info("[附加测试] 尝试按名称删除规则 '测试规则：低温开灯(已修改并禁用)'...")
    rule_name_to_delete = "测试规则：低温开灯(已修改并禁用)"
    if rule_manager.delete_rule(rule_name_to_delete, identifier_key='name'):
        print(f"✅ (附加测试) 成功删除规则名称: '{rule_name_to_delete}'。")
    else:
        # 这不一定是错误，可能规则确实不存在
        print(f"ℹ️ (附加测试) 未找到或无法删除规则名称: '{rule_name_to_delete}'。")

    logging.info("----- 规则管理测试结束 -----")
# ==============================================================================
# ======================= 测试函数结束 =========================================
# ==============================================================================
