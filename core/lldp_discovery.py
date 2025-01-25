import re
from typing import Dict, List
import logging

class LLDPDiscovery:
    def __init__(self, ssh_manager):
        self.ssh = ssh_manager
        self.logger = logging.getLogger(__name__)

    def get_lldp_neighbors(self) -> List[Dict]:
        """获取LLDP邻居信息"""
        try:
            # 执行display lldp neighbor brief命令
            result = self.ssh.execute_command("display lldp neighbor brief")
            if not result:
                return []

            neighbors = []
            # 跳过表头
            lines = result.split('\n')
            header_found = False
            
            for line in lines:
                line = line.strip()
                # 跳过空行和分隔线
                if not line or '-' * 10 in line:
                    continue
                    
                # 跳过表头
                if "Local Interface" in line:
                    header_found = True
                    continue
                    
                if header_found:
                    # 解析邻居信息
                    parts = line.split()
                    if len(parts) >= 4:
                        neighbor = {
                            'local_interface': parts[0],
                            'exptime': parts[1],
                            'remote_interface': parts[2],
                            'remote_device': ' '.join(parts[3:]),  # 设备名可能包含空格
                            'capabilities': ['switch']  # 默认为交换机
                        }
                        neighbors.append(neighbor)

            return neighbors

        except Exception as e:
            self.logger.error(f"获取LLDP邻居信息失败: {str(e)}")
            return []

    def _extract_interface(self, line: str) -> str:
        """提取接口名称"""
        match = re.search(r"port\s+([^\s:]+)", line)
        return match.group(1) if match else ""

    def _extract_value(self, line: str) -> str:
        """提取冒号后的值"""
        parts = line.split(':', 1)
        return parts[1].strip() if len(parts) > 1 else ""

    def _extract_ip(self, line: str) -> str:
        """提取IP地址"""
        match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
        return match.group(0) if match else ""

    def _extract_capabilities(self, line: str) -> List[str]:
        """提取系统功能"""
        caps = []
        if "Bridge" in line:
            caps.append("switch")
        if "Router" in line:
            caps.append("router")
        return caps

    def parse_lldp_topology(self) -> Dict:
        """解析LLDP信息为拓扑字典结构"""
        try:
            # 获取当前设备的主机名
            hostname = self.ssh.execute_command("display current-configuration | include sysname").split()[-1]
            
            # 获取LLDP邻居信息
            neighbors = self.get_lldp_neighbors()
            
            # 构建拓扑字典
            topology = {
                'devices': {
                    hostname: {
                        'name': hostname,
                        'type': 'switch',
                        'interfaces': {}
                    }
                },
                'connections': []
            }
            
            # 处理每个邻居信息
            for neighbor in neighbors:
                local_intf = neighbor['local_interface']
                remote_device = neighbor['remote_device']
                remote_intf = neighbor['remote_interface']
                
                # 添加接口信息
                topology['devices'][hostname]['interfaces'][local_intf] = {
                    'connected_to': remote_device,
                    'remote_interface': remote_intf
                }
                
                # 添加连接信息
                connection = {
                    'source': hostname,
                    'source_interface': local_intf,
                    'target': remote_device,
                    'target_interface': remote_intf
                }
                topology['connections'].append(connection)
                
                # 添加邻居设备
                if remote_device not in topology['devices']:
                    topology['devices'][remote_device] = {
                        'name': remote_device,
                        'type': 'switch',
                        'interfaces': {
                            remote_intf: {
                                'connected_to': hostname,
                                'remote_interface': local_intf
                            }
                        }
                    }
            
            return topology
            
        except Exception as e:
            self.logger.error(f"解析LLDP拓扑失败: {str(e)}")
            return {'devices': {}, 'connections': []} 