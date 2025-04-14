# state_manager.py
import logging
import time
from threading import RLock # 引入可重入锁，保证线程安全
from typing import Dict, Any, Optional

# 修正导入路径
from utils.mqtt.device_manager import DeviceManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StateManager:
    """
    管理系统中所有设备的最新已知状态。
    状态通过 MQTT 消息更新，并可供 API 查询。
    此类设计为线程安全的。
    """
    def __init__(self, device_manager: DeviceManager):
        """
        初始化状态管理器。

        Args:
            device_manager: DeviceManager 的实例，用于查找设备信息。
        """
        self._device_states: Dict[str, Dict[str, Any]] = {} # 存储格式: {'device_id': {'timestamp': float, 'state': dict}}
        self._device_manager = device_manager
        self._lock = RLock() # 使用可重入锁保护状态字典的读写
        logging.info("状态管理器 (StateManager) 已初始化。")

    def update_state_from_mqtt(self, topic: str, payload_dict: Dict[str, Any]):
        """
        根据收到的 MQTT 消息更新设备状态。

        Args:
            topic: 收到消息的 MQTT 主题。
            payload_dict: 解析后的消息内容 (字典)。
        """
        device_id = None
        device_info = None

        # 根据 topic 查找对应的设备 ID 和信息
        # 注意：这里假设一个 topic 只对应一个设备的状态，如果不是，需要调整逻辑
        for d_id, d_info in self._device_manager.get_all_devices().items():
            if d_info.get("status_topic") == topic:
                device_id = d_id
                device_info = d_info
                break

        if not device_id:
            logging.debug(f"未找到与主题 '{topic}' 关联的设备，忽略状态更新。")
            return

        timestamp = time.time()
        current_state = {}

        # 处理嵌套的 'params' 结构（来自之前的逻辑）
        if device_info and device_info.get("payload_format") == "nested_params":
            if "params" in payload_dict and isinstance(payload_dict.get("params"), dict):
                 current_state = payload_dict["params"]
            else:
                 logging.warning(f"设备 '{device_id}' 的 payload 格式为 nested_params，但在主题 '{topic}' 的消息中未找到 'params' 字典: {payload_dict}")
                 # 可以选择存储原始 payload 或部分内容
                 # current_state = payload_dict # 或者只记录错误
                 return # 或者不更新状态如果格式不对
        else:
            # 对于非嵌套格式，直接使用整个 payload 作为状态 (或者根据设备定义提取)
            current_state = payload_dict

        with self._lock: # 获取锁以安全地更新字典
            self._device_states[device_id] = {
                "timestamp": timestamp,
                "state": current_state,
                "last_raw_payload": payload_dict # 可选：存储原始 payload 供调试
            }
        logging.debug(f"设备 '{device_id}' 状态已更新: {current_state}")

    def get_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定设备的最新状态。

        Args:
            device_id: 要查询的设备 ID。

        Returns:
            包含 'timestamp' 和 'state' 的字典，如果找不到则返回 None。
        """
        with self._lock: # 获取锁以安全地读取
            return self._device_states.get(device_id)

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有已知设备的最新状态。

        Returns:
            一个字典，键是 device_id，值是状态信息字典。
        """
        with self._lock: # 获取锁以安全地复制字典
            # 返回浅拷贝以防止外部修改内部状态
            return self._device_states.copy()

    def get_states_by_type(self, device_type: str) -> Dict[str, Dict[str, Any]]:
        """
        获取特定类型设备（如 'sensor', 'actuator'）的所有状态。

        Args:
            device_type: 设备类型字符串。

        Returns:
            一个筛选后的状态字典。
        """
        filtered_states = {}
        all_devices = self._device_manager.get_all_devices()
        with self._lock: # 获取锁以安全地读取状态
            for device_id, state_info in self._device_states.items():
                device_info = all_devices.get(device_id)
                if device_info and device_info.get("type") == device_type:
                    filtered_states[device_id] = state_info
        return filtered_states