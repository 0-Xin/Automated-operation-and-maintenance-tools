import paramiko
import os
import logging
from typing import List, Dict, Optional, Callable
import threading
from concurrent.futures import ThreadPoolExecutor
import socket
import time
import stat

class FTPManager:
    def __init__(
        self,
        ip: str,
        username: str,
        password: str,
        timeout: int = 30,
        port: int = 22  # 改为 SFTP 默认端口
    ):
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.port = port
        self.ssh = None
        self.sftp = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.progress_callback = None

    def set_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """设置进度回调函数"""
        self.progress_callback = callback

    def connect(self) -> bool:
        """建立SFTP连接"""
        retry_count = 3
        for attempt in range(retry_count):
            try:
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                self.logger.info(f"正在尝试连接设备 {self.ip} (尝试 {attempt + 1}/{retry_count})")
                
                self.ssh.connect(
                    hostname=self.ip,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False
                )

                self.sftp = self.ssh.open_sftp()
                self.sftp.get_channel().settimeout(self.timeout)
                
                self.logger.info(f"SFTP连接成功: {self.ip}")
                return True
                
            except paramiko.AuthenticationException:
                self.logger.error(f"SFTP认证失败 {self.ip}: 用户名或密码错误")
                break
                
            except socket.timeout:
                self.logger.error(f"SFTP连接超时 {self.ip}")
                if attempt < retry_count - 1:
                    continue
                    
            except Exception as e:
                self.logger.error(f"SFTP连接失败 {self.ip}: {str(e)}")
                if attempt < retry_count - 1:
                    continue
                    
            finally:
                if not self.sftp and self.ssh:
                    self.close()
                    
        return False

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """上传文件"""
        if not os.path.exists(local_path):
            self.logger.error(f"本地文件不存在: {local_path}")
            return False

        try:
            file_size = os.path.getsize(local_path)
            uploaded_size = [0]  # 使用列表以便在回调中修改

            def callback(sent, total):
                uploaded_size[0] = sent
                if self.progress_callback:
                    self.progress_callback(
                        os.path.basename(local_path),
                        sent,
                        total
                    )

            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    self.sftp.stat(remote_dir)
                except:
                    # 创建远程目录
                    self.sftp.mkdir(remote_dir)

            # 上传文件
            self.sftp.put(
                local_path,
                remote_path,
                callback=callback,
                confirm=True
            )
                
            self.logger.info(f"文件上传成功: {local_path} -> {remote_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"文件上传失败: {str(e)}")
            return False

    def download_file(self, remote_file: str, local_file: str) -> bool:
        """从设备下载文件
        
        Args:
            remote_file: 设备上的文件路径
            local_file: 本地保存路径
            
        Returns:
            bool: 下载是否成功
        """
        try:
            if not self.sftp:
                raise Exception("SFTP连接未建立")

            # 获取远程文件大小
            file_size = self.sftp.stat(remote_file).st_size
            
            # 创建本地文件夹(如果不存在)
            os.makedirs(os.path.dirname(os.path.abspath(local_file)), exist_ok=True)
            
            # 下载文件并显示进度
            with self._lock:
                self.logger.info(f"开始下载文件: {remote_file} -> {local_file}")
                bytes_downloaded = 0
                
                def update_progress(bytes_transferred: int, _):
                    nonlocal bytes_downloaded
                    bytes_downloaded = bytes_transferred
                    if self.progress_callback:
                        self.progress_callback(remote_file, bytes_downloaded, file_size)
                
                self.sftp.get(remote_file, local_file, callback=update_progress)
                
                self.logger.info(f"文件下载成功: {remote_file} -> {local_file}")
                return True
                
        except FileNotFoundError:
            self.logger.error(f"远程文件不存在: {remote_file}")
            return False
            
        except Exception as e:
            self.logger.error(f"文件下载失败 {remote_file}: {str(e)}")
            return False

    def list_remote_files(self, remote_path: str = '.') -> List[Dict]:
        """列出远程目录下的文件
        
        Args:
            remote_path: 远程目录路径,默认为当前目录
            
        Returns:
            List[Dict]: 文件列表,每个文件包含名称、大小、修改时间等信息
        """
        try:
            if not self.sftp:
                raise Exception("SFTP连接未建立")
                
            files = []
            for entry in self.sftp.listdir_attr(remote_path):
                try:
                    file_info = {
                        'filename': entry.filename,
                        'size': entry.st_size if hasattr(entry, 'st_size') else 0,  # 添加默认值
                        'mtime': time.strftime('%Y-%m-%d %H:%M:%S', 
                                             time.localtime(entry.st_mtime if hasattr(entry, 'st_mtime') else 0)),
                        'is_dir': stat.S_ISDIR(entry.st_mode) if hasattr(entry, 'st_mode') else False
                    }
                    files.append(file_info)
                except Exception as e:
                    self.logger.warning(f"处理文件 {entry.filename} 信息失败: {str(e)}")
                    continue
                
            return files
            
        except Exception as e:
            self.logger.error(f"获取远程文件列表失败: {str(e)}")
            return []

    def close(self) -> None:
        """关闭SFTP连接"""
        if self.sftp:
            try:
                self.sftp.close()
            except:
                pass
            self.sftp = None
            
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
            self.ssh = None
            
        self.logger.info(f"关闭SFTP连接: {self.ip}") 