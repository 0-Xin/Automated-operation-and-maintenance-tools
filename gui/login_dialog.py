from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
import random
import json
import os
import time

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login Verification")
        self.setWindowFlags(Qt.WindowCloseButtonHint)  # 只显示关闭按钮
        self.setup_ui()
        self.check_permanent_auth()  # 只检查永久授权状态

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("网络自动化工具       作者：LXX")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        
        # 机器码显示/输入
        machine_code_layout = QHBoxLayout()
        machine_code_label = QLabel("机器码:")
        self.machine_code_display = QLineEdit()
        self.machine_code_display.setMaxLength(6)  # 限制最大长度为6位
        self.machine_code_display.setPlaceholderText("请输入6位数字机器码")
        # 要求必须输入6位数字
        self.machine_code_display.setValidator(QRegExpValidator(QRegExp("[0-9]{6}")))
        machine_code_layout.addWidget(machine_code_label)
        machine_code_layout.addWidget(self.machine_code_display)
        layout.addLayout(machine_code_layout)
        
        # 授权码输入
        auth_code_layout = QHBoxLayout()
        auth_code_label = QLabel("授权码:")
        self.auth_code_input = QLineEdit()
        self.auth_code_input.setEchoMode(QLineEdit.Password)  # 密码模式
        auth_code_layout.addWidget(auth_code_label)
        auth_code_layout.addWidget(self.auth_code_input)
        layout.addLayout(auth_code_layout)
        
        # 永久授权码输入
        permanent_code_layout = QHBoxLayout()
        permanent_code_label = QLabel("永久授权码:")
        self.permanent_code_input = QLineEdit()
        self.permanent_code_input.setEchoMode(QLineEdit.Password)  # 密码模式
        permanent_code_layout.addWidget(permanent_code_label)
        permanent_code_layout.addWidget(self.permanent_code_input)
        layout.addLayout(permanent_code_layout)
        
        # 登录按钮
        button_layout = QHBoxLayout()
        self.login_btn = QPushButton("普通登录")
        self.permanent_login_btn = QPushButton("永久授权")
        self.login_btn.clicked.connect(self.verify_login)
        self.permanent_login_btn.clicked.connect(self.verify_permanent_auth)
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.permanent_login_btn)
        layout.addLayout(button_layout)

        # 设置样式
        self.setStyleSheet("""
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

    def check_permanent_auth(self):
        """检查是否已永久授权"""
        config_file = "login_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    # 只在永久授权时加载保存的机器码
                    if data.get('permanent_auth', False):
                        self.accept()  # 如果已永久授权，直接通过
                    # 总是清空机器码，让用户手动输入
                    self.machine_code_display.clear()
            except:
                pass

    def verify_login(self):
        """验证登录"""
        # 先验证机器码
        machine_code = self.machine_code_display.text().strip()
        if len(machine_code) != 6 or not machine_code.isdigit():
            QMessageBox.warning(self, "错误", "请输入6位数字机器码！")
            return
            
        input_code = self.auth_code_input.text().strip()
        
        # 计算机器码各位数字之和，然后乘以99
        machine_code_sum = sum(int(digit) for digit in machine_code)
        correct_code = str(machine_code_sum * 99)
        
        if input_code == correct_code:
            self.save_machine_code(machine_code)  # 保存机器码
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "授权码错误！\n请联系作者获取授权码")

    def save_machine_code(self, machine_code: str):
        """保存机器码"""
        try:
            with open("login_config.json", 'w') as f:
                json.dump({
                    'machine_code': machine_code,
                    'permanent_auth': False
                }, f)
        except Exception as e:
            self.logger.error(f"保存机器码失败: {str(e)}")

    def save_permanent_auth(self):
        """保存永久授权信息"""
        try:
            with open("login_config.json", 'w') as f:
                json.dump({
                    'permanent_auth': True
                }, f)
        except Exception as e:
            self.logger.error(f"保存永久授权信息失败: {str(e)}") 

    def verify_permanent_auth(self):
        """验证永久授权码"""
        # 先验证机器码
        machine_code = self.machine_code_display.text().strip()
        if len(machine_code) != 6 or not machine_code.isdigit():
            QMessageBox.warning(self, "错误", "请输入6位数字机器码！")
            return
            
        input_code = self.permanent_code_input.text().strip()
        if input_code == "2725034308lxx":
            self.save_permanent_auth()
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "永久授权码错误！\n请联系作者获取永久授权码") 