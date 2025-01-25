
class TopologyDiscoveryThread(QThread):
    discovery_complete = pyqtSignal(dict)
    progress_update = pyqtSignal(str)
    device_found = pyqtSignal(str, str)  # ip, type

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.topology = {
            'devices': {},
            'links': []
        }
        self.stop_flag = False
        self.network_graph = nx.Graph()
        self.discovered_devices = set()
        self.scan_queue = queue.Queue()
        self.lock = threading.Lock()

    def run(self):
        try:
            self.progress_update.emit("开始自动发现网络拓扑...")
            
            # 1. 获取本地网络信息
            local_networks = self.get_local_networks()
            if not local_networks:
                raise Exception("未找到可用的网络接口")
            
            self.progress_update.emit(f"发现本地网络: {len(local_networks)} 个")
            
            # 2. 并行扫描所有网段
            with ThreadPoolExecutor(max_workers=min(len(local_networks), 5)) as executor:
                future_to_network = {
                    executor.submit(self.scan_network, network): network 
                    for network in local_networks
                }
                
                for future in as_completed(future_to_network):
                    network = future_to_network[future]
                    try:
                        devices = future.result()
                        self.progress_update.emit(f"完成网段 {network} 扫描，发现 {len(devices)} 个设备")
                    except Exception as e:
                        self.logger.error(f"扫描网段 {network} 失败: {str(e)}")

            # 3. 分析网络拓扑
            self.analyze_network_topology()
            
            # 4. 优化布局
            self.optimize_layout()
            
            self.progress_update.emit("拓扑发现完成")
            self.discovery_complete.emit(self.topology)

        except Exception as e:
            self.logger.error(f"拓扑发现失败: {str(e)}")
            self.progress_update.emit(f"错误: {str(e)}")

    def get_local_networks(self) -> List[str]:
        """获取本地网络信息"""
        networks = set()
        try:
            # 获取所有网络接口信息
            output = subprocess.check_output("ipconfig /all", text=True)
            
            # 解析IP地址和子网掩码
            sections = output.split('\n\n')
            for section in sections:
                if '以太网适配器' in section or '无线局域网适配器' in section:
                    ip_match = re.search(r"IPv4 地址[. ]+: ([0-9.]+)", section)
                    mask_match = re.search(r"子网掩码[. ]+: ([0-9.]+)", section)
                    
                    if ip_match and mask_match:
                        ip = ip_match.group(1)
                        mask = mask_match.group(1)
                        
                        if not ip.startswith('127.'):
                            # 计算网段
                            network = self.calculate_network(ip, mask)
                            networks.add(network)
                            
                            # 添加相邻网段
                            self.add_adjacent_networks(networks, network)
                            
        except Exception as e:
            self.logger.error(f"获取本地网络失败: {str(e)}")
        
        return list(networks)

    def calculate_network(self, ip: str, mask: str) -> str:
        """计算网络地址"""
        try:
            ip_int = struct.unpack('!I', socket.inet_aton(ip))[0]
            mask_int = struct.unpack('!I', socket.inet_aton(mask))[0]
            network_int = ip_int & mask_int
            network_ip = socket.inet_ntoa(struct.pack('!I', network_int))
            return f"{network_ip}/24"
        except:
            ip_parts = list(map(int, ip.split('.')))
            return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"

    def add_adjacent_networks(self, networks: Set[str], network: str):
        """添加相邻网段"""
        try:
            net = ipaddress.ip_network(network)
            base_net = list(net.network_address.exploded.split('.'))
            
            # 添加前后两个网段
            for i in range(-2, 3):
                if i != 0:  # 跳过当前网段
                    new_third_octet = int(base_net[2]) + i
                    if 0 <= new_third_octet <= 255:
                        adjacent_net = f"{base_net[0]}.{base_net[1]}.{new_third_octet}.0/24"
                        networks.add(adjacent_net)
        except Exception as e:
            self.logger.debug(f"添加相邻网段失败: {str(e)}")

    def scan_network(self, network: str) -> List[Dict]:
        """扫描网段"""
        devices = []
        try:
            net = ipaddress.ip_network(network)
            
            # 创建线程池
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_ip = {
                    executor.submit(self.check_device, str(ip), network): str(ip)
                    for ip in net.hosts()
                }
                
                for future in as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    try:
                        device = future.result()
                        if device:
                            devices.append(device)
                    except Exception as e:
                        self.logger.debug(f"检查设备 {ip} 失败: {str(e)}")
                        
        except Exception as e:
            self.logger.error(f"扫描网段 {network} 失败: {str(e)}")
            
        return devices

    def check_device(self, ip: str, network: str) -> Dict:
        """检查单个设备"""
        try:
            # 快速ping检测
            if self.fast_ping(ip):
                # 检查设备类型
                device_type = self.identify_device_type(ip)
                device_name = f"Device_{ip.split('.')[-1]}"
                
                device = {
                    'name': device_name,
                    'ip': ip,
                    'type': device_type,
                    'network': network
                }
                
                # 添加到图和拓扑
                with self.lock:
                    self.network_graph.add_node(
                        ip,
                        **device
                    )
                    self.topology['devices'][ip] = device
                    self.discovered_devices.add(ip)
                
                self.device_found.emit(ip, device_type)
                return device
                
        except Exception as e:
            self.logger.debug(f"检查设备 {ip} 失败: {str(e)}")
        
        return None

    def fast_ping(self, ip: str) -> bool:
        """快速ping检测"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
                sock.settimeout(0.2)
                sock.connect((ip, 0))
                return True
        except:
            return False

    def identify_device_type(self, ip: str) -> str:
        """识别设备类型"""
        try:
            # 检查常见网络设备端口
            device_type = 'host'
            for port in [22, 23, 80, 443, 161]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                if sock.connect_ex((ip, port)) == 0:
                    if port == 161:  # SNMP
                        device_type = 'switch'
                    elif port in [22, 23]:  # SSH/Telnet
                        device_type = 'router'
                    elif port in [80, 443]:  # HTTP/HTTPS
                        device_type = 'server'
                    sock.close()
                    break
                sock.close()
                
            return device_type
            
        except Exception as e:
            self.logger.debug(f"识别设备类型失败: {str(e)}")
            return 'host'

    def analyze_network_topology(self):
        """分析网络拓扑"""
        try:
            # 分析设备连接
            for ip1, device1 in self.topology['devices'].items():
                if device1['type'] in ['switch', 'router']:
                    # 分析同网段连接
                    for ip2, device2 in self.topology['devices'].items():
                        if ip1 != ip2 and device1['network'] == device2['network']:
                            self.add_link(ip1, ip2)
                    
                    # 分析跨网段连接
                    if device1['type'] == 'router':
                        other_networks = set(d['network'] for d in self.topology['devices'].values()) - {device1['network']}
                        for network in other_networks:
                            network_devices = [ip for ip, d in self.topology['devices'].items() if d['network'] == network]
                            if network_devices:
                                self.add_link(ip1, network_devices[0], is_routed=True)

            # 使用NetworkX优化布局
            pos = nx.spring_layout(
                self.network_graph,
                k=2.0,
                iterations=50,
                weight='weight'
            )
            
            # 更新节点位置
            for node in self.network_graph.nodes:
                if node in self.topology['devices']:
                    self.topology['devices'][node]['position'] = pos[node]

        except Exception as e:
            self.logger.error(f"分析网络拓扑失败: {str(e)}")

    def add_link(self, source: str, target: str, is_routed: bool = False):
        """添加连接"""
        try:
            # 添加到NetworkX图
            self.network_graph.add_edge(
                source, target,
                weight=2 if is_routed else 1
            )
            
            # 添加到拓扑字典
            link = {
                'source': source,
                'target': target,
                'source_port': 'auto',
                'target_port': 'auto',
                'is_routed': is_routed
            }
            
            if not any(l['source'] == source and l['target'] == target 
                      for l in self.topology['links']):
                self.topology['links'].append(link)
                
        except Exception as e:
            self.logger.error(f"添加连接失败: {str(e)}")

    def stop(self):
        """停止扫描"""
        self.stop_flag = True 

    def optimize_layout(self):
        """优化网络拓扑布局"""
        try:
            # 使用不同的布局算法
            if len(self.network_graph) < 10:
                pos = nx.spring_layout(self.network_graph, k=2.0, iterations=50)
            elif len(self.network_graph) < 30:
                pos = nx.kamada_kawai_layout(self.network_graph)
            else:
                pos = nx.fruchterman_reingold_layout(self.network_graph)
            
            # 应用布局
            for node in self.network_graph.nodes:
                if node in self.topology['devices']:
                    self.topology['devices'][node]['position'] = pos[node]
                    
        except Exception as e:
            self.logger.error(f"优化布局失败: {str(e)}") 
