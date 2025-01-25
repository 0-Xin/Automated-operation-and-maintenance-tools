import logging
import os
from datetime import datetime

def setup_logger():
    """配置日志"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 创建logs目录（如果不存在）
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - LXX - %(message)s',  # 添加LXX标识
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # 文件处理器
    log_file = os.path.join('logs', f'lxx_{datetime.now().strftime("%Y%m%d")}.log')  # 添加lxx前缀
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - LXX - %(message)s',  # 添加LXX标识
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger 