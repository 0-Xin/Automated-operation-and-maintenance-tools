from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                            QTableWidgetItem, QPushButton, QTextEdit, QLabel,
                            QFileDialog, QProgressBar, QListWidget, QMessageBox,
                            QDialog, QProgressDialog, QGraphicsView, QGraphicsScene,
                            QGraphicsItem, QGraphicsLineItem, QGraphicsTextItem,
                            QGraphicsRectItem, QGraphicsDropShadowEffect, QRadioButton,
                            QListWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath,
                        QImage, QPixmap, QRadialGradient)
import logging
import os
from core.command_executor import CommandExecutor
from core.ftp_manager import FTPManager
from core.topology_discovery import TopologyDiscoveryThread
import networkx as nx
import math
from typing import Dict, List
from core.lldp_discovery import LLDPDiscovery
from core.ssh_manager import SSHManager
import json
import webbrowser
from .resources import HTML_TEMPLATE
from concurrent.futures import ThreadPoolExecutor, as_completed

class TopologyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setup_ui()
        self.devices = {}
        self.links = []
        self.layout_engine = nx.spring_layout

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新拓扑")
        self.auto_discover_btn = QPushButton("自动发现")
        self.lldp_discover_btn = QPushButton("LLDP发现")
        self.export_btn = QPushButton("导出拓扑图")
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.auto_discover_btn)
        toolbar.addWidget(self.lldp_discover_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 拓扑视图
        self.scene = QGraphicsScene()
        self.view = TopologyView(self.scene)
        layout.addWidget(self.view)

        # 连接信号
        self.refresh_btn.clicked.connect(self.refresh_topology)
        self.auto_discover_btn.clicked.connect(self.discover_topology)
        self.lldp_discover_btn.clicked.connect(self.discover_lldp_topology)
        self.export_btn.clicked.connect(self.export_topology)

        # 初始状态
        self.refresh_btn.setEnabled(False)  # 初始时禁用刷新按钮
        self.export_btn.setEnabled(False)   # 初始时禁用导出按钮

    def refresh_topology(self):
        """刷新拓扑图"""
        if hasattr(self, 'devices') and self.devices:
            self.draw_topology()
        else:
            self.discover_topology()

    def discover_topology(self):
        """自动发现拓扑"""
        try:
            # 创建进度对话框
            progress_dialog = QProgressDialog("正在发现网络拓扑...", "取消", 0, 0, self)
            progress_dialog.setWindowTitle("拓扑发现")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setAutoClose(True)
            progress_dialog.setAutoReset(True)
            
            # 创建拓扑发现线程
            self.discovery_thread = TopologyDiscoveryThread()
            
            # 连接信号
            self.discovery_thread.progress_update.connect(progress_dialog.setLabelText)
            self.discovery_thread.discovery_complete.connect(self.update_topology)
            progress_dialog.canceled.connect(self.discovery_thread.stop)
            
            # 启动线程
            self.discovery_thread.start()
            progress_dialog.exec_()

        except Exception as e:
            self.logger.error(f"拓扑发现失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"拓扑发现失败: {str(e)}")

    def update_topology(self, topology_data):
        """更新拓扑图"""
        try:
            if not topology_data['devices']:
                QMessageBox.warning(self, "警告", "未发现任何设备")
                return
                
            self.devices = topology_data['devices']
            self.links = topology_data['links']
            
            # 更新按钮状态
            self.refresh_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            
            # 绘制拓扑
            self.draw_topology()
            
            # 显示成功消息
            QMessageBox.information(self, "成功", 
                f"拓扑发现完成\n发现 {len(self.devices)} 个设备\n发现 {len(self.links)} 条链接")
            
        except Exception as e:
            self.logger.error(f"更新拓扑失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"更新拓扑失败: {str(e)}")

    def draw_topology(self):
        """绘制拓扑图"""
        try:
            self.scene.clear()
            self.scene.setBackgroundBrush(QColor(30, 30, 30))

            # 创建NetworkX图
            G = nx.Graph()
            for device_id, device in self.devices.items():
                G.add_node(device_id, **device)
            for link in self.links:
                if link['source'] and link['target']:
                    G.add_edge(link['source'], link['target'])

            # 使用spring_layout布局，调整参数使节点更紧凑
            pos = nx.spring_layout(
                G,
                k=0.5,        # 减小节点间斥力
                iterations=50,
                scale=300     # 减小整体缩放
            )

            # 存储节点对象以便更新连接线
            self.node_items = {}

            # 首先创建所有节点
            for device_id, device in self.devices.items():
                if device_id in pos:
                    device_pos = pos[device_id]
                    node = DeviceNode(
                        device_pos[0],
                        device_pos[1],
                        device.get('name', device_id)
                    )
                    self.scene.addItem(node)
                    self.node_items[device_id] = node

            # 然后创建连接线
            for link in self.links:
                if link['source'] in self.node_items and link['target'] in self.node_items:
                    source_node = self.node_items[link['source']]
                    target_node = self.node_items[link['target']]
                    
                    # 创建连接线
                    line = QGraphicsLineItem()
                    pen = QPen(QColor("#4A9EFF"), 2)
                    pen.setCapStyle(Qt.RoundCap)
                    line.setPen(pen)
                    
                    # 更新连接线位置
                    source_pos = source_node.pos()
                    target_pos = target_node.pos()
                    line.setLine(
                        source_pos.x(), source_pos.y(),
                        target_pos.x(), target_pos.y()
                    )
                    
                    # 添加接口标签
                    if 'local_interface' in link and 'remote_interface' in link:
                        mid_x = (source_pos.x() + target_pos.x()) / 2
                        mid_y = (source_pos.y() + target_pos.y()) / 2
                        label = self.scene.addText(
                            f"{link['local_interface']}\n{link['remote_interface']}"
                        )
                        label.setDefaultTextColor(QColor("#FFFFFF"))
                        label.setPos(
                            mid_x - label.boundingRect().width() / 2,
                            mid_y - label.boundingRect().height() / 2
                        )
                    
                    self.scene.addItem(line)

            # 调整视图
            self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            
        except Exception as e:
            self.logger.error(f"绘制拓扑失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"绘制拓扑失败: {str(e)}")

    def export_topology(self):
        """导出拓扑图"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出拓扑图",
            "",
            "PNG图片 (*.png);;SVG图片 (*.svg)"
        )
        if not file_name:
            return

        try:
            image = QImage(self.scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
            image.fill(Qt.transparent)

            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.scene.render(painter)
            painter.end()

            image.save(file_name)
            QMessageBox.information(self, "成功", "拓扑图导出成功")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")

    def discover_lldp_topology(self):
        """通过LLDP自动发现拓扑"""
        try:
            # 获取设备表中的所有设备
            main_window = self.parent().parent()
            device_table = main_window.findChild(DeviceTableWidget)
            if not device_table or device_table.table.rowCount() == 0:
                QMessageBox.warning(self, "警告", "没有可用的设备")
                return
            
            devices = []
            for row in range(device_table.table.rowCount()):
                devices.append({
                    'ip': device_table.table.item(row, 0).text().strip(),
                    'username': device_table.table.item(row, 1).text().strip(),
                    'password': device_table.table.item(row, 2).text().strip(),
                    'port': device_table.table.item(row, 3).text().strip() or "22"
                })

            # 创建进度对话框
            progress = QProgressDialog("正在通过LLDP发现拓扑...", "取消", 0, len(devices), self)
            progress.setWindowTitle("LLDP拓扑发现")
            progress.setWindowModality(Qt.WindowModal)
            
            # 创建线程池
            with ThreadPoolExecutor(max_workers=min(len(devices), 10)) as executor:
                # 存储所有任务的Future对象
                future_to_device = {
                    executor.submit(self._discover_device_topology, device): device
                    for device in devices
                }
                
                # 收集拓扑信息
                merged_topology = {'devices': {}, 'connections': []}
                completed = 0
                
                # 处理完成的任务
                for future in as_completed(future_to_device):
                    if progress.wasCanceled():
                        executor.shutdown(wait=False)
                        break
                        
                    device = future_to_device[future]
                    completed += 1
                    progress.setValue(completed)
                    progress.setLabelText(f"正在处理设备 {device['ip']} 的LLDP信息...")
                    
                    try:
                        device_topology = future.result()
                        if device_topology:
                            # 合并设备信息
                            for device_name, device_info in device_topology['devices'].items():
                                clean_name = device_name.strip('<>')
                                if clean_name not in merged_topology['devices']:
                                    device_info['name'] = clean_name
                                    merged_topology['devices'][clean_name] = device_info
                                else:
                                    if 'interfaces' in device_info:
                                        if 'interfaces' not in merged_topology['devices'][clean_name]:
                                            merged_topology['devices'][clean_name]['interfaces'] = {}
                                        merged_topology['devices'][clean_name]['interfaces'].update(
                                            device_info['interfaces']
                                        )
                            
                            # 添加连接信息
                            for conn in device_topology['connections']:
                                source = conn['source'].strip('<>')
                                target = conn['target'].strip('<>')
                                merged_topology['connections'].append({
                                    'source': source,
                                    'target': target,
                                    'local_interface': conn.get('source_interface', ''),
                                    'remote_interface': conn.get('target_interface', '')
                                })
                    except Exception as e:
                        self.logger.error(f"处理设备 {device['ip']} 失败: {str(e)}")
                        continue

            progress.setValue(len(devices))

            # 转换为绘图格式并显示
            if merged_topology['devices']:
                self._process_topology_data(merged_topology)
                self.draw_web_topology()
                QMessageBox.information(self, "成功", 
                    f"LLDP拓扑发现完成\n发现 {len(self.devices)} 个设备\n发现 {len(self.links)} 条链接")
            else:
                QMessageBox.warning(self, "警告", "未发现任何LLDP邻居关系")

        except Exception as e:
            self.logger.error(f"LLDP拓扑发现失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"LLDP拓扑发现失败: {str(e)}")

    def _discover_device_topology(self, device):
        """在单独的线程中发现单个设备的拓扑"""
        try:
            ssh = SSHManager(
                device['ip'],
                device['username'],
                device['password'],
                port=int(device.get('port', 22))
            )
            
            if ssh.connect():
                lldp = LLDPDiscovery(ssh)
                topology = lldp.parse_lldp_topology()
                ssh.close()
                return topology
            return None
            
        except Exception as e:
            self.logger.error(f"设备 {device['ip']} 拓扑发现失败: {str(e)}")
            return None

    def _process_topology_data(self, merged_topology):
        """处理拓扑数据"""
        # 转换设备信息
        self.devices = {}
        for name, info in merged_topology['devices'].items():
            clean_name = name.strip('<>')
            self.devices[clean_name] = {
                'name': info.get('name', clean_name),
                'type': info.get('type', 'unknown'),
                'ip': info.get('management_ip', '')
            }
        
        # 转换连接信息
        self.links = []
        for conn in merged_topology['connections']:
            source = conn['source'].strip('<>')
            target = conn['target'].strip('<>')
            self.links.append({
                'source': source,
                'target': target,
                'local_interface': conn.get('source_interface', ''),
                'remote_interface': conn.get('target_interface', '')
            })

    def draw_web_topology(self):
        """生成Web版拓扑图"""
        try:
            # 数据验证
            if not self.devices:
                raise ValueError("没有设备数据")

            print("原始数据:")
            print("Devices:", json.dumps(self.devices, indent=2))
            print("Links:", json.dumps(self.links, indent=2))

            # 创建NetworkX图
            G = nx.Graph()
            
            # 添加节点
            for device_id, device in self.devices.items():
                G.add_node(device_id, **device)
            
            # 添加边
            for link in self.links:
                if link.get('source') and link.get('target'):
                    G.add_edge(
                        link['source'],
                        link['target'],
                        local_interface=link.get('local_interface', ''),
                        remote_interface=link.get('remote_interface', '')
                    )

            print("NetworkX图信息:")
            print("Nodes:", list(G.nodes()))
            print("Edges:", list(G.edges()))
            
            # 使用spring_layout布局，调整参数使节点分布更合理
            pos = nx.spring_layout(
                G,
                k=0.5,  # 减小节点间距
                iterations=50,  # 减少迭代次数
                seed=42  # 固定随机种子以获得稳定布局
            )
            
            # 准备Plotly数据 - 先处理边
            edge_trace = {
                'type': 'scatter',
                'x': [],
                'y': [],
                'mode': 'lines+text',  # 添加text模式以显示接口信息
                'line': {
                    'width': 4,
                    'color': '#2980B9'
                },
                'text': [],  # 接口标签
                'textposition': 'middle',  # 文本位置在线的中间
                'textfont': {
                    'size': 40,  # 增大接口信息的字体
                    'color': '#2980B9',
                    'family': 'Arial'
                },
                'hoverinfo': 'text',
                'hovertext': []
            }
            
            # 添加边的数据
            for edge in G.edges(data=True):
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_trace['x'].extend([x0, x1, None])
                edge_trace['y'].extend([y0, y1, None])
                # 添加接口信息作为文本标签
                interface_text = f"{edge[2].get('local_interface', '')}\n{edge[2].get('remote_interface', '')}"
                edge_trace['text'].extend([interface_text, "", ""])  # 在线的中间显示接口信息
                edge_trace['hovertext'].append(
                    f"连接: {edge[2].get('local_interface', '')} - {edge[2].get('remote_interface', '')}"
                )

            # 准备节点数据
            node_trace = {
                'type': 'scatter',
                'x': [],
                'y': [],
                'mode': 'markers+text',
                'marker': {
                    'size': 100,  # 显著增大节点大小
                    'color': '#3498DB',
                    'line': {
                        'width': 4,
                        'color': '#2980B9'
                    },
                    'symbol': 'square',  # 使用方形节点
                },
                'text': [],
                'textposition': 'bottom center',
                'textfont': {
                    'size': 80,  # 显著增大文字大小
                    'color': '#2c3e50',
                    'family': 'Arial Black'
                },
                'hoverinfo': 'text',
                'hovertext': []
            }
            
            # 添加节点数据
            for node in G.nodes(data=True):
                x, y = pos[node[0]]
                node_trace['x'].append(x)
                node_trace['y'].append(y)
                device_info = node[1]
                node_name = device_info.get('name', node[0])
                node_trace['text'].append(node_name)
                node_trace['hovertext'].append(
                    f"设备名称: {node_name}\n"
                    f"类型: {device_info.get('type', '未知')}\n"
                    f"IP: {device_info.get('ip', '未知')}"
                )
            
            # 生成Plotly数据 - 确保边在节点下面
            plotly_data = [edge_trace, node_trace]
            
            # 打印转换后的数据
            print("Plotly数据:")
            print("Node trace:", json.dumps(node_trace, indent=2))
            print("Edge trace:", json.dumps(edge_trace, indent=2))
            
            # 生成HTML内容
            html_content = HTML_TEMPLATE.replace('{plotly_data}', json.dumps(plotly_data, ensure_ascii=False))
            
            # 保存并打开HTML文件
            temp_file = os.path.join(os.path.expanduser('~'), 'topology.html')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 打印生成的HTML内容的一部分（用于调试）
            print("\nHTML预览:")
            print(html_content[:1000])
            
            # 在默认浏览器中打开
            webbrowser.open(f'file://{temp_file}')
            
        except Exception as e:
            self.logger.error(f"生成Web拓扑图失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"生成Web拓扑图失败: {str(e)}")
            return False
        
        return True

class TopologyView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setInteractive(True)
        self.scale(1, 1)
        
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # 保存当前场景位置
        old_pos = self.mapToScene(event.pos())

        # 缩放
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)

        # 调整场景位置
        new_pos = self.mapToScene(event.pos())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

class DeviceNode(QGraphicsItem):
    def __init__(self, x, y, name, device_type="switch"):
        super().__init__()
        self.name = name
        self.device_type = device_type
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
    def boundingRect(self):
        return QRectF(-50, -30, 100, 60)
        
    def paint(self, painter, option, widget):
        # 绘制节点背景
        rect = self.boundingRect()
        painter.setBrush(QBrush(QColor("#2C3E50")))
        painter.setPen(QPen(QColor("#3498DB"), 2))
        painter.drawRoundedRect(rect, 10, 10)
        
        # 绘制设备名称
        painter.setPen(QPen(QColor("#FFFFFF")))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.name)

class DeviceTableWidget(QWidget):
    device_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("添加设备")
        self.remove_btn = QPushButton("删除设备")
        self.import_btn = QPushButton("导入设备")
        self.export_btn = QPushButton("导出设备")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 设备表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["IP地址", "用户名", "密码", "端口"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        # 连接信号
        self.add_btn.clicked.connect(self.add_device)
        self.remove_btn.clicked.connect(self.remove_device)
        self.import_btn.clicked.connect(self.import_devices)
        self.export_btn.clicked.connect(self.export_devices)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

    def add_device(self):
        """添加空行并创建空的单元格项"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(4):
            self.table.setItem(row, col, QTableWidgetItem(""))

    def remove_device(self):
        """删除选中的设备"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def import_devices(self):
        """导入设备列表"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "导入设备列表",
            "",
            "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if not file_name:
            return

        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 清空现有设备列表
            if lines and QMessageBox.question(
                self,
                "确认导入",
                "是否清空现有设备列表？",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self.table.setRowCount(0)

            # 导入新设备
            for line in lines:
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                
                try:
                    # 分割并清理数据
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 4:
                        ip, username, password, port = parts[:4]
                        
                        # 检查IP地址格式
                        if not self.is_valid_ip(ip):
                            raise ValueError(f"无效的IP地址: {ip}")
                        
                        # 添加到表格
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        self.table.setItem(row, 0, QTableWidgetItem(ip))
                        self.table.setItem(row, 1, QTableWidgetItem(username))
                        self.table.setItem(row, 2, QTableWidgetItem(password))
                        self.table.setItem(row, 3, QTableWidgetItem(port))
                except Exception as e:
                    QMessageBox.warning(self, "导入错误", f"导入行 '{line}' 失败: {str(e)}")

            QMessageBox.information(self, "导入完成", f"成功导入 {self.table.rowCount()} 个设备")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入设备列表失败: {str(e)}")

    def export_devices(self):
        """导出设备列表"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "没有设备可以导出")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出设备列表",
            "",
            "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if not file_name:
            return

        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                for row in range(self.table.rowCount()):
                    ip = self.table.item(row, 0).text()
                    username = self.table.item(row, 1).text()
                    password = self.table.item(row, 2).text()
                    port = self.table.item(row, 3).text()
                    f.write(f"{ip},{username},{password},{port}\n")

            QMessageBox.information(self, "导出完成", f"成功导出 {self.table.rowCount()} 个设备")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出设备列表失败: {str(e)}")

    def is_valid_ip(self, ip):
        """验证IP地址格式"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            return all(0 <= int(part) <= 255 for part in parts)
        except:
            return False

    def on_selection_changed(self):
        """处理设备选择变化"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            # 检查所有必需的单元格是否都有值
            items = [self.table.item(current_row, col) for col in range(4)]
            if all(item and item.text().strip() for item in items):
                device = {
                    'ip': items[0].text().strip(),
                    'username': items[1].text().strip(),
                    'password': items[2].text().strip(),
                    'port': items[3].text().strip()
                }
                self.device_selected.emit(device)

class CommandEditorWidget(QWidget):
    execution_started = pyqtSignal()
    execution_finished = pyqtSignal(bool, str)
    command_output = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.execution_thread = None

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 设备选择区域
        device_layout = QHBoxLayout()
        self.device_label = QLabel("当前设备:")
        self.device_info = QLabel("未选择")
        self.select_device_btn = QPushButton("选择设备")
        device_layout.addWidget(self.device_label)
        device_layout.addWidget(self.device_info)
        device_layout.addWidget(self.select_device_btn)
        device_layout.addStretch()
        layout.addLayout(device_layout)
        
        # 命令编辑区
        self.editor = QTextEdit()
        layout.addWidget(self.editor)

        # 输出显示区
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("执行命令")
        self.load_btn = QPushButton("加载命令")
        self.save_btn = QPushButton("保存命令")
        self.cancel_btn = QPushButton("取消执行")
        self.cancel_btn.setEnabled(False)
        
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        # 连接信号
        self.execute_btn.clicked.connect(self.execute_commands)
        self.cancel_btn.clicked.connect(self.cancel_execution)
        self.load_btn.clicked.connect(self.load_commands)
        self.save_btn.clicked.connect(self.save_commands)
        self.select_device_btn.clicked.connect(self.select_device)
        self.command_output.connect(self.update_output)

        # 初始状态
        self.execute_btn.setEnabled(False)

    def select_device(self):
        """选择设备对话框"""
        dialog = DeviceSelectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_devices = dialog.get_selected_devices()
            if selected_devices:
                # 只取第一个设备（单选模式）
                self.set_device(selected_devices[0])
            else:
                QMessageBox.warning(self, "警告", "请选择一个设备")

    def set_device(self, device):
        """设置当前设备"""
        self.current_device = device
        self.device_info.setText(f"{device['ip']} ({device['username']})")
        self.execute_btn.setEnabled(True)

    def execute_commands(self):
        """执行命令"""
        dialog = DeviceSelectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_devices = dialog.get_selected_devices()
            if not selected_devices:
                QMessageBox.warning(self, "警告", "请选择至少一个设备")
                return

            try:
                commands = [cmd.strip() for cmd in self.editor.toPlainText().split('\n') if cmd.strip()]
                if not commands:
                    QMessageBox.warning(self, "警告", "请输入要执行的命令")
                    return

                self.execution_started.emit()
                self.execute_btn.setEnabled(False)
                self.cancel_btn.setEnabled(True)
                self.output_text.clear()

                # 创建多个执行线程
                self.execution_threads = []
                for device in selected_devices:
                    thread = CommandExecutionThread(
                        device,
                        commands,
                        self.command_output,
                        self.execution_finished
                    )
                    thread.finished.connect(self.on_thread_finished)
                    self.execution_threads.append(thread)
                    thread.start()

            except Exception as e:
                self.execution_finished.emit(False, f"执行出错: {str(e)}")
                self.execute_btn.setEnabled(True)
                self.cancel_btn.setEnabled(False)

    def cancel_execution(self):
        """取消所有执行"""
        if hasattr(self, 'execution_threads'):
            for thread in self.execution_threads:
                if thread.isRunning():
                    thread.stop()
                    thread.wait()
            self.execution_finished.emit(False, "用户取消执行")
            self.execute_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def on_thread_finished(self):
        """单个线程完成的处理"""
        if hasattr(self, 'execution_threads'):
            all_finished = all(not thread.isRunning() for thread in self.execution_threads)
            if all_finished:
                self.execute_btn.setEnabled(True)
                self.cancel_btn.setEnabled(False)
                self.execution_threads = []

    def update_output(self, text):
        """更新输出显示"""
        self.output_text.append(text)
        # 滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def load_commands(self):
        """加载命令文件"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "加载命令文件",
            "",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    self.editor.setPlainText(f.read())
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载文件失败: {str(e)}")

    def save_commands(self):
        """保存命令到文件"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "保存命令文件",
            "",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存文件失败: {str(e)}")

class CommandExecutionThread(QThread):
    def __init__(self, device, commands, output_signal, finished_signal):
        super().__init__()
        self.device = device
        self.commands = commands
        self.output_signal = output_signal
        self.finished_signal = finished_signal
        self._stop = False

    def run(self):
        executor = CommandExecutor()
        try:
            def progress_callback(completed, total):
                self.output_signal.emit(f"执行进度: {completed}/{total}")

            executor.set_progress_callback(progress_callback)
            
            result = executor.batch_execute(
                [self.device],
                {self.device['ip']: self.commands}
            )
            
            device_result = result.get(self.device['ip'], {})
            if device_result.get('status') == 'success':
                # 显示每个命令的输出
                for cmd, output in device_result.get('commands', {}).items():
                    self.output_signal.emit(f"\n执行命令: {cmd}")
                    self.output_signal.emit(output)
                self.finished_signal.emit(True, "命令执行成功")
            else:
                error = device_result.get('error', '未知错误')
                self.finished_signal.emit(False, f"执行失败: {error}")
                
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def stop(self):
        """停止执行"""
        self._stop = True

class FileTransferWidget(QWidget):
    transfer_started = pyqtSignal()
    transfer_finished = pyqtSignal(bool, str)
    transfer_progress = pyqtSignal(str, int, int)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setup_ui()
        self.transfer_threads = []

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 设备选择区域
        device_layout = QHBoxLayout()
        self.device_info = QLabel("目标设备: 未选择")
        self.select_device_btn = QPushButton("选择设备")
        device_layout.addWidget(self.device_info)
        device_layout.addWidget(self.select_device_btn)
        device_layout.addStretch()
        layout.addLayout(device_layout)
        
        # 传输方向选择
        direction_layout = QHBoxLayout()
        self.upload_radio = QRadioButton("上传到设备")
        self.download_radio = QRadioButton("从设备下载")
        self.upload_radio.setChecked(True)
        direction_layout.addWidget(self.upload_radio)
        direction_layout.addWidget(self.download_radio)
        layout.addLayout(direction_layout)
        
        # 本地文件列表(上传用)
        self.local_files_group = QWidget()
        local_layout = QVBoxLayout(self.local_files_group)
        self.file_list = QListWidget()
        self.add_btn = QPushButton("添加文件")
        self.remove_btn = QPushButton("删除文件")
        local_btn_layout = QHBoxLayout()
        local_btn_layout.addWidget(self.add_btn)
        local_btn_layout.addWidget(self.remove_btn)
        local_layout.addWidget(QLabel("本地文件:"))
        local_layout.addWidget(self.file_list)
        local_layout.addLayout(local_btn_layout)
        layout.addWidget(self.local_files_group)
        
        # 远程文件浏览器(下载用)
        self.remote_files_group = QWidget()
        remote_layout = QVBoxLayout(self.remote_files_group)
        self.path_label = QLabel("当前路径: /")
        self.remote_files_list = QListWidget()
        self.refresh_btn = QPushButton("刷新")
        self.parent_dir_btn = QPushButton("上级目录")
        remote_btn_layout = QHBoxLayout()
        remote_btn_layout.addWidget(self.parent_dir_btn)
        remote_btn_layout.addWidget(self.refresh_btn)
        remote_layout.addWidget(self.path_label)
        remote_layout.addWidget(self.remote_files_list)
        remote_layout.addLayout(remote_btn_layout)
        layout.addWidget(self.remote_files_group)
        self.remote_files_group.hide()
        
        # 进度显示
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(100)
        layout.addWidget(self.progress_text)
        
        # 传输按钮
        btn_layout = QHBoxLayout()
        self.transfer_btn = QPushButton("开始传输")
        self.cancel_btn = QPushButton("取消传输")
        self.transfer_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.transfer_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 连接信号
        self.select_device_btn.clicked.connect(self.select_devices)
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn.clicked.connect(self.remove_files)
        self.transfer_btn.clicked.connect(self.start_transfer)
        self.cancel_btn.clicked.connect(self.cancel_transfer)
        self.refresh_btn.clicked.connect(self.refresh_remote_files)
        self.parent_dir_btn.clicked.connect(self.goto_parent_dir)
        self.upload_radio.toggled.connect(self.on_transfer_direction_changed)
        self.remote_files_list.itemDoubleClicked.connect(self.on_remote_item_double_clicked)
        
        # 初始化变量
        self.selected_devices = []
        self.current_remote_path = "/"
        self.transfer_threads = []

    def on_transfer_direction_changed(self):
        """处理传输方向改变"""
        is_download = self.download_radio.isChecked()
        self.local_files_group.setVisible(not is_download)
        self.remote_files_group.setVisible(is_download)
        
        if is_download and self.selected_devices:
            self.refresh_remote_files()

    def on_remote_item_double_clicked(self, item):
        """处理远程文件项双击事件"""
        file_info = item.data(Qt.UserRole)
        if file_info['is_dir']:
            # 如果是目录,进入该目录
            new_path = os.path.join(self.current_remote_path, file_info['filename'])
            self.browse_remote_directory(new_path)
        else:
            # 如果是文件,选择下载位置
            self.select_download_path(item)

    def browse_remote_directory(self, path: str):
        """浏览远程目录"""
        if not self.selected_devices:
            return
            
        device = self.selected_devices[0]
        try:
            ftp = FTPManager(device['ip'], device['username'], device['password'], port=int(device['port']))
            if ftp.connect():
                files = ftp.list_remote_files(path)
                if files is not None:  # 如果目录存在
                    self.current_remote_path = path
                    self.path_label.setText(f"当前路径: {path}")
                    self.refresh_remote_files()
                ftp.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"浏览目录失败: {str(e)}")

    def goto_parent_dir(self):
        """返回上级目录"""
        parent_path = os.path.dirname(self.current_remote_path)
        if parent_path != self.current_remote_path:  # 防止在根目录时继续往上
            self.browse_remote_directory(parent_path)

    def refresh_remote_files(self):
        """刷新远程文件列表"""
        if not self.selected_devices:
            QMessageBox.warning(self, "警告", "请先选择设备")
            return
            
        device = self.selected_devices[0]
        try:
            ftp = FTPManager(
                device['ip'], 
                device['username'], 
                device['password'],
                port=int(device.get('port', 22))
            )
            
            if ftp.connect():
                self.remote_files_list.clear()
                files = ftp.list_remote_files(self.current_remote_path)
                
                # 添加目录项
                for file_info in sorted(files, key=lambda x: (not x['is_dir'], x['filename'])):
                    try:
                        item = QListWidgetItem()
                        prefix = "📁 " if file_info['is_dir'] else "📄 "
                        size_str = "目录" if file_info['is_dir'] else self.format_size(file_info['size'])
                        item.setText(f"{prefix}{file_info['filename']} ({size_str}) - {file_info['mtime']}")
                        item.setData(Qt.UserRole, file_info)
                        self.remote_files_list.addItem(item)
                    except Exception as e:
                        self.logger.warning(f"添加文件项失败: {str(e)}")
                        continue
                
                ftp.close()
            else:
                QMessageBox.warning(self, "错误", "连接设备失败")
        except Exception as e:
            self.logger.error(f"获取文件列表失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"获取文件列表失败: {str(e)}")

    def select_devices(self):
        """选择目标设备"""
        dialog = DeviceSelectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_devices = dialog.get_selected_devices()
            if self.selected_devices:
                device_count = len(self.selected_devices)
                self.device_info.setText(f"已选择 {device_count} 个设备")
                self.transfer_btn.setEnabled(True)
            else:
                self.device_info.setText("未选择")
                self.transfer_btn.setEnabled(False)

    def start_transfer(self):
        """开始传输"""
        if not self.selected_devices:
            QMessageBox.warning(self, "警告", "请先选择目标设备")
            return

        if self.upload_radio.isChecked():
            # 上传模式
            if self.file_list.count() == 0:
                QMessageBox.warning(self, "警告", "请先添加要上传的文件")
                return
                
            files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        else:
            # 下载模式 - 由双击文件触发,不在这里处理
            return

        self.progress_text.clear()
        self.transfer_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # 创建传输线程
        self.transfer_threads = []
        for device in self.selected_devices:
            thread = FileTransferThread(
                device,
                files,
                self.current_remote_path
            )
            thread.progress_signal.connect(self.update_progress)
            thread.finished.connect(self.on_thread_finished)
            self.transfer_threads.append(thread)
            thread.start()

    def cancel_transfer(self):
        """取消所有传输"""
        for thread in self.transfer_threads:
            if thread.isRunning():
                thread.stop()
                thread.wait()
        self.transfer_finished.emit(False, "用户取消传输")
        self.transfer_btn.setEnabled(True)
        self.transfer_threads = []

    def on_thread_finished(self):
        """单个线程完成的处理"""
        all_finished = all(not thread.isRunning() for thread in self.transfer_threads)
        if all_finished:
            self.transfer_btn.setEnabled(True)
            self.transfer_threads = []

    def add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            "所有文件 (*.*)"
        )
        for file in files:
            if file not in [self.file_list.item(i).text() for i in range(self.file_list.count())]:
                self.file_list.addItem(file)

    def remove_files(self):
        """删除选中的文件"""
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def select_download_path(self, item):
        """选择下载文件保存位置"""
        file_info = item.data(Qt.UserRole)
        if file_info['is_dir']:
            return
            
        filename = file_info['filename']
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存位置",
            filename,
            "所有文件 (*.*)"
        )
        
        if save_path:
            self.start_download(filename, save_path)

    def start_download(self, remote_file: str, local_file: str):
        """开始下载文件"""
        if not self.selected_devices:
            return
            
        device = self.selected_devices[0]
        
        # 创建进度对话框
        progress = QProgressDialog(f"正在下载 {remote_file}...", "取消", 0, 100, self)
        progress.setWindowTitle("文件下载")
        progress.setWindowModality(Qt.WindowModal)
        
        # 创建下载线程
        self.download_thread = FileTransferThread(
            device=device,
            files=[],  # 下载模式不需要files参数
            remote_path=self.current_remote_path,
            remote_file=remote_file,
            local_file=local_file,
            is_download=True
        )
        
        def update_progress(msg, current, total):
            if total > 0:
                progress.setValue(int(current * 100 / total))
            self.update_progress(msg)
        
        # 连接信号
        self.download_thread.progress_signal.connect(update_progress)
        self.download_thread.finished.connect(progress.close)
        
        # 启动下载
        self.download_thread.start()
        progress.exec_()

    @staticmethod
    def format_size(size: int) -> str:
        """格式化文件大小"""
        try:
            if size is None:
                return "未知大小"
            
            size = float(size)  # 确保size是数字
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f}{unit}"
                size /= 1024
            return f"{size:.1f}TB"
        except (TypeError, ValueError):
            return "未知大小"

    def update_progress(self, message, current=None, total=None):
        """更新进度显示"""
        self.progress_text.append(message)
        # 滚动到底部
        scrollbar = self.progress_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class FileTransferThread(QThread):
    progress_signal = pyqtSignal(str, int, int)
    
    def __init__(self, device: Dict, files: List[str], remote_path: str = "/", 
                 remote_file: str = None, local_file: str = None, is_download: bool = False):
        super().__init__()
        self.device = device
        self.files = files
        self.remote_path = remote_path
        self.remote_file = remote_file
        self.local_file = local_file
        self.is_download = is_download
        self._stop = False

    def run(self):
        try:
            ftp = FTPManager(
                self.device['ip'], 
                self.device['username'], 
                self.device['password'],
                port=int(self.device.get('port', 22))
            )
            
            def progress_callback(filename, current, total):
                if current is not None and total is not None:  # 添加空值检查
                    self.progress_signal.emit(
                        f"{'下载' if self.is_download else '上传'} {filename}: {current}/{total} 字节",
                        current,
                        total
                    )

            ftp.set_progress_callback(progress_callback)
            
            if ftp.connect():
                if self.is_download:
                    # 下载单个文件
                    remote_path = os.path.join(self.remote_path, self.remote_file)
                    if ftp.download_file(remote_path, self.local_file):
                        self.progress_signal.emit(
                            f"文件下载成功: {self.remote_file}",
                            100,
                            100
                        )
                    else:
                        self.progress_signal.emit(
                            f"文件下载失败: {self.remote_file}",
                            0,
                            100
                        )
                else:
                    # 上传多个文件
                    for file_path in self.files:
                        if self._stop:
                            break
                            
                        remote_file = os.path.join(self.remote_path, os.path.basename(file_path))
                        self.progress_signal.emit(
                            f"正在上传: {os.path.basename(file_path)}",
                            0,
                            100
                        )
                        
                        if ftp.upload_file(file_path, remote_file):
                            self.progress_signal.emit(
                                f"文件上传成功: {os.path.basename(file_path)}",
                                100,
                                100
                            )
                        else:
                            self.progress_signal.emit(
                                f"文件上传失败: {os.path.basename(file_path)}",
                                0,
                                100
                            )
                
                ftp.close()
            else:
                self.progress_signal.emit(
                    f"连接设备失败: {self.device['ip']}",
                    0,
                    100
                )
                
        except Exception as e:
            self.progress_signal.emit(
                f"传输错误: {str(e)}",
                0,
                100
            )

    def stop(self):
        """停止传输"""
        self._stop = True

# 还需要添加 LogWidget 类
class LogWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 日志显示区
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 清除按钮
        self.clear_btn = QPushButton("清除日志")
        layout.addWidget(self.clear_btn)

        # 连接信号
        self.clear_btn.clicked.connect(self.clear_log)

    def append_log(self, message):
        self.log_text.append(message)

    def clear_log(self):
        self.log_text.clear()

# 添加设备选择对话框
class DeviceSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_devices = []
        self.setup_ui()
        self.load_devices()

    def setup_ui(self):
        self.setWindowTitle("选择设备")
        self.setModal(True)
        layout = QVBoxLayout(self)

        # 设备表格
        self.table = QTableWidget()
        self.table.setColumnCount(2)  # 只显示选择和IP地址两列
        self.table.setHorizontalHeaderLabels(["选择", "IP地址"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.MultiSelection)  # 多选模式
        layout.addWidget(self.table)

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.deselect_all_btn = QPushButton("取消全选")
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 连接信号
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.table.itemChanged.connect(self.on_item_changed)

    def load_devices(self):
        """从主窗口加载设备列表"""
        try:
            main_window = self.parent().parent().parent()
            device_table = main_window.findChild(DeviceTableWidget)
            if device_table and device_table.table.rowCount() > 0:
                # 清空当前表格
                self.table.setRowCount(0)
                
                # 复制设备列表
                for row in range(device_table.table.rowCount()):
                    self.table.insertRow(row)
                    
                    # 添加勾选框
                    checkbox = QTableWidgetItem()
                    checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    checkbox.setCheckState(Qt.Unchecked)
                    self.table.setItem(row, 0, checkbox)
                    
                    # 添加IP地址
                    ip_item = device_table.table.item(row, 0)
                    if ip_item:
                        new_item = QTableWidgetItem(ip_item.text())
                        new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        self.table.setItem(row, 1, new_item)
                        
                        # 存储完整的设备信息
                        username = device_table.table.item(row, 1).text()
                        password = device_table.table.item(row, 2).text()
                        port = device_table.table.item(row, 3).text() or "22"  # 获取端口,默认22
                        new_item.setData(Qt.UserRole, {
                            'username': username,
                            'password': password,
                            'port': port
                        })
            else:
                QMessageBox.warning(self, "警告", "没有可选择的设备")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载设备列表失败: {str(e)}")

    def get_selected_devices(self):
        """获取选中的设备列表"""
        devices = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                ip_item = self.table.item(row, 1)
                if ip_item:
                    device_data = ip_item.data(Qt.UserRole)
                    devices.append({
                        'ip': ip_item.text().strip(),
                        'username': device_data['username'],
                        'password': device_data['password'],
                        'port': device_data['port']
                    })
        return devices

    def select_all(self):
        """全选所有设备"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def deselect_all(self):
        """取消全选"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def on_item_changed(self, item):
        """处理勾选状态变化"""
        if item.column() == 0:  # 只处理勾选列
            row = item.row()
            if item.checkState() == Qt.Checked:
                self.table.selectRow(row)
            else:
                self.table.clearSelection() 