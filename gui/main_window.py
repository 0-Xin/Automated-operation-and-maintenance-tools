from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QPushButton, QLabel, QFileDialog, 
                            QMessageBox, QProgressBar, QStyleFactory, QDialog, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp
from PyQt5.QtGui import QPalette, QColor, QBrush, QPainter, QRegExpValidator
from PyQt5.QtGui import QPixmap, QImage
from .widgets import (DeviceTableWidget, CommandEditorWidget, 
                     FileTransferWidget, LogWidget, TopologyWidget)
from core.command_executor import CommandExecutor
from utils.config import ConfigManager
import logging
import json

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("网络自动化工具       作者：LXX")
        self.is_permanent_auth = self.check_permanent_auth()
        self.set_background()
        self.setup_ui()
        self.setup_style()

    def check_permanent_auth(self) -> bool:
        """检查是否是永久授权用户"""
        try:
            with open("login_config.json", 'r') as f:
                data = json.load(f)
                return data.get('permanent_auth', False)
        except:
            return False

    def set_background(self):
        """设置背景图片"""
        try:
            # 加载背景图片
            background = QImage("sta/background.jpg")  # 请确保图片路径正确
            # 创建半透明效果
            painter = QPainter(background)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.fillRect(background.rect(), QColor(0, 0, 0, 180))  # 180是透明度(0-255)
            painter.end()
            
            # 设置为背景
            palette = self.palette()
            palette.setBrush(QPalette.Window, QBrush(QPixmap.fromImage(background)))
            self.setPalette(palette)
            
            # 允许背景显示
            self.setAutoFillBackground(True)
        except Exception as e:
            self.logger.error(f"设置背景图片失败: {str(e)}")

    def setup_style(self):
        """设置窗口样式"""
        # 修改样式表，确保控件背景半透明
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
            QWidget {
                background-color: transparent;
                color: #E6E6E6;
                font-family: "Microsoft YaHei", "Segoe UI";
            }
            QTabWidget::pane {
                border: 1px solid #3D4450;
                background-color: rgba(45, 49, 57, 180);
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: rgba(60, 64, 72, 180);
                color: #E6E6E6;
                padding: 8px 20px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: rgba(75, 79, 87, 180);
                border-bottom: 2px solid #4A9EFF;
            }
            QPushButton {
                background-color: rgba(74, 158, 255, 0.8);
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: rgba(74, 158, 255, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(64, 148, 245, 0.9);
            }
            QPushButton:disabled {
                background-color: rgba(128, 128, 128, 0.5);
            }
            QTextEdit {
                background-color: rgba(30, 34, 42, 0.95);
                border: 1px solid #3D4450;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #4A9EFF;
            }
            QTableWidget {
                background-color: rgba(30, 34, 42, 0.95);
                border: 1px solid #3D4450;
                border-radius: 5px;
                gridline-color: #3D4450;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: rgba(74, 158, 255, 0.3);
            }
            QHeaderView::section {
                background-color: rgba(60, 64, 72, 0.95);
                color: #E6E6E6;
                padding: 5px;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background-color: rgba(45, 49, 57, 0.95);
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(74, 158, 255, 0.7);
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(74, 158, 255, 0.8);
            }
            QStatusBar {
                background-color: rgba(40, 44, 52, 0.95);
                color: #E6E6E6;
            }
            QMessageBox {
                background-color: rgba(40, 44, 52, 0.95);
            }
            QLabel {
                color: #E6E6E6;
            }
        """)

    def setup_ui(self):
        """设置主窗口UI"""
        self.setMinimumSize(800, 600)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建选项卡
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # 设备管理选项卡
        self.device_tab = QWidget()
        self.device_table = DeviceTableWidget()
        device_layout = QVBoxLayout(self.device_tab)
        device_layout.addWidget(self.device_table)
        tab_widget.addTab(self.device_tab, "设备管理")

        # 命令执行选项卡
        self.command_tab = QWidget()
        self.command_editor = CommandEditorWidget()
        command_layout = QVBoxLayout(self.command_tab)
        command_layout.addWidget(self.command_editor)
        tab_widget.addTab(self.command_tab, "命令执行")

        # 文件传输选项卡
        self.transfer_tab = QWidget()
        self.file_transfer = FileTransferWidget()
        transfer_layout = QVBoxLayout(self.transfer_tab)
        transfer_layout.addWidget(self.file_transfer)
        tab_widget.addTab(self.transfer_tab, "文件传输")

        # 拓扑视图选项卡
        self.topology_tab = QWidget()
        self.topology_view = TopologyWidget()
        topology_layout = QVBoxLayout(self.topology_tab)
        topology_layout.addWidget(self.topology_view)
        tab_widget.addTab(self.topology_tab, "网络拓扑")

        # 日志显示
        self.log_widget = LogWidget()
        layout.addWidget(self.log_widget)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 连接信号
        self.connect_signals()

        # 添加修改机器码菜单（仅永久授权用户可见）
        if self.is_permanent_auth:
            menu_bar = self.menuBar()
            settings_menu = menu_bar.addMenu("设置")
            change_machine_code_action = settings_menu.addAction("修改机器码")
            change_machine_code_action.triggered.connect(self.show_change_machine_code_dialog)

    def connect_signals(self):
        """连接信号和槽"""
        self.device_table.device_selected.connect(self.command_editor.set_device)
        self.command_editor.execution_started.connect(self.on_execution_started)
        self.command_editor.execution_finished.connect(self.on_execution_finished)
        self.file_transfer.transfer_started.connect(self.on_transfer_started)
        self.file_transfer.transfer_finished.connect(self.on_transfer_finished)

    def on_execution_started(self):
        """命令执行开始"""
        self.statusBar().showMessage("正在执行命令...")

    def on_execution_finished(self, success: bool, message: str):
        """命令执行完成"""
        if success:
            self.statusBar().showMessage("命令执行完成")
        else:
            self.statusBar().showMessage(f"命令执行失败: {message}")
            QMessageBox.warning(self, "错误", message)

    def on_transfer_started(self):
        """文件传输开始"""
        self.statusBar().showMessage("正在传输文件...")

    def on_transfer_finished(self, success: bool, message: str):
        """文件传输完成"""
        if success:
            self.statusBar().showMessage("文件传输完成")
        else:
            self.statusBar().showMessage(f"文件传输失败: {message}")
            QMessageBox.warning(self, "错误", message)

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.config.save_config()
        event.accept() 

    def show_change_machine_code_dialog(self):
        """显示修改机器码对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("修改机器码")
        layout = QVBoxLayout(dialog)
        
        # 新机器码输入
        input_layout = QHBoxLayout()
        label = QLabel("新机器码:")
        machine_code_input = QLineEdit()
        machine_code_input.setMaxLength(6)
        machine_code_input.setPlaceholderText("请输入6位数字机器码")
        machine_code_input.setValidator(QRegExpValidator(QRegExp("[0-9]{6}")))
        
        # 读取当前机器码
        try:
            with open("login_config.json", 'r') as f:
                data = json.load(f)
                current_code = data.get('machine_code', '')
                if current_code:
                    machine_code_input.setText(current_code)
                else:
                    machine_code_input.clear()
        except:
            pass
        
        input_layout.addWidget(label)
        input_layout.addWidget(machine_code_input)
        layout.addLayout(input_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        def on_ok():
            new_code = machine_code_input.text().strip()
            if len(new_code) != 6 or not new_code.isdigit():
                QMessageBox.warning(dialog, "错误", "请输入6位数字机器码！")
                return
            try:
                with open("login_config.json", 'r') as f:
                    data = json.load(f)
                data['machine_code'] = new_code
                with open("login_config.json", 'w') as f:
                    json.dump(data, f)
                QMessageBox.information(dialog, "成功", "机器码修改成功！")
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "错误", f"修改机器码失败: {str(e)}")
        
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        
        # 设置对话框样式
        dialog.setStyleSheet("""
            QDialog {
                background-color: rgba(40, 44, 52, 0.95);
                color: #E6E6E6;
            }
            QLabel {
                color: #E6E6E6;
            }
            QLineEdit {
                background-color: rgba(30, 34, 42, 0.95);
                border: 1px solid #3D4450;
                border-radius: 3px;
                padding: 5px;
                color: #E6E6E6;
            }
            QPushButton {
                background-color: rgba(74, 158, 255, 0.8);
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: rgba(74, 158, 255, 0.9);
            }
        """)
        
        dialog.exec_() 