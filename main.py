import sys
import warnings
from gui.main_window import MainWindow
from gui.login_dialog import LoginDialog
from utils.logger import setup_logger
from PyQt5.QtWidgets import QApplication

def main():
    # 设置日志
    logger = setup_logger()
    logger.info("启动网络自动化配置工具")

    # 忽略警告
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    # 创建QT应用
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格，更现代的外观
    
    # 显示登录对话框
    login_dialog = LoginDialog()
    if login_dialog.exec_() != LoginDialog.Accepted:
        sys.exit(0)
    
    # 创建主窗口
    window = MainWindow()
    window.setWindowTitle("网络自动化工具       作者：LXX")
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 