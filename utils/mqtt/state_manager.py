# state_manager.py
import logging
import time
import json
from threading import RLock # 引入可重入锁，保证线程安全
from typing import Dict, Any, Optional

# 假设 DeviceManager 在这个路径，根据你的项目调整
from device_manager import DeviceManager

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
        self.device_manager = device_manager
        self._states = {}  # 存储设备状态的字典
        self._lock = RLock()  # 可重入锁，用于线程安全
        self.logger = logging.getLogger(__name__)
        logging.info("状态管理器 (StateManager) 已初始化。")

    def update_state_from_mqtt(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        从MQTT消息更新设备状态
        :param topic: MQTT主题
        :param payload: 消息负载
        :return: 是否成功更新
        """
        try:
            with self._lock:
                # 查找匹配的设备
                device = self._find_device_by_topic(topic)
                if not device:
                    self.logger.warning(f"未找到匹配主题 {topic} 的设备")
                    return False

                device_id = device["device_id"]
                
                # 根据payload格式处理数据
                if device.get("payload_format") == "nested_params":
                    # 处理嵌套参数格式
                    if "params" in payload:
                        data = payload["params"]
                    else:
                        self.logger.warning(f"消息格式错误，缺少params字段: {payload}")
                        return False
                else:
                    # 处理普通格式
                    data = payload

                # 更新设备状态
                self._states[device_id] = {
                    "last_update": time.time(),
                    "data": data
                }
                
                self.logger.debug(f"更新设备 {device_id} 状态: {data}")
                return True

        except Exception as e:
            self.logger.error(f"更新状态时发生错误: {e}")
            return False

    def _find_device_by_topic(self, topic: str) -> Optional[Dict[str, Any]]:
        """根据主题查找设备"""
        try:
            devices = self.device_manager.get_all_devices()
            for device in devices.values():
                if device.get("status_topic") == topic:
                    return device
            return None
        except Exception as e:
            self.logger.error(f"查找设备时发生错误: {e}")
            return None

    def get_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定设备的状态
        :param device_id: 设备ID
        :return: 设备状态，如果设备不存在则返回None
        """
        try:
            with self._lock:
                return self._states.get(device_id)
        except Exception as e:
            self.logger.error(f"获取设备状态时发生错误: {e}")
            return None

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有设备的状态
        :return: 所有设备状态的字典
        """
        try:
            with self._lock:
                return self._states.copy()
        except Exception as e:
            self.logger.error(f"获取所有状态时发生错误: {e}")
            return {}

    def get_states_by_type(self, device_type: str) -> Dict[str, Dict[str, Any]]:
        """
        获取指定类型的所有设备状态
        :param device_type: 设备类型（如"sensor"或"actuator"）
        :return: 设备状态字典
        """
        try:
            with self._lock:
                result = {}
                devices = self.device_manager.get_all_devices()
                for device_id, device in devices.items():
                    if device.get("type") == device_type:
                        result[device_id] = self._states.get(device_id, {})
                return result
        except Exception as e:
            self.logger.error(f"按类型获取状态时发生错误: {e}")
            return {}

    def clear_state(self, device_id: str) -> bool:
        """
        清除指定设备的状态
        :param device_id: 设备ID
        :return: 是否成功清除
        """
        try:
            with self._lock:
                if device_id in self._states:
                    del self._states[device_id]
                    return True
                return False
        except Exception as e:
            self.logger.error(f"清除状态时发生错误: {e}")
            return False

    def clear_all_states(self) -> None:
        """清除所有设备的状态"""
        try:
            with self._lock:
                self._states.clear()
        except Exception as e:
            self.logger.error(f"清除所有状态时发生错误: {e}")