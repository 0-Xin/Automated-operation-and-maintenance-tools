import paramiko
import time
import logging
from typing import List, Dict, Optional
import socket
from paramiko.ssh_exception import SSHException, AuthenticationException
import threading

class SSHManager:
    _connection_pool = {}  # 类级别的连接池
    _pool_lock = threading.Lock()  # 连接池锁
    
    def __init__(self, ip: str, username: str, password: str, port: int = 22, timeout: int = 10):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.ssh = None
        self.shell = None
        self.logger = logging.getLogger(__name__)
        self.prompt_patterns = [r'>$', r'#$', r'\]$']  # 命令提示符模式
        self.last_output = ""
        self._connection_key = f"{username}@{ip}:{port}"

    def _wait_for_prompt(self, timeout: int = 10) -> bool:
        """等待命令提示符"""
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < timeout:
            if self.shell.recv_ready():
                chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
                buffer += chunk
                
                # 检查是否出现提示符（更宽松的匹配）
                if any(char in buffer for char in ['>', '#', ']', '$']):
                    self.last_output = buffer
                    return True
                
                # 检查是否需要确认
                if any(prompt in buffer.upper() for prompt in ['[Y/N]', '[YES/NO]', 'CONTINUE?']):
                    self.logger.info(f"检测到确认提示，自动发送 'Y'")
                    self.shell.send('Y\n')
                    time.sleep(0.5)  # 等待响应
                    
            time.sleep(0.1)
        
        self.last_output = buffer
        return False

    def connect(self) -> bool:
        """建立SSH连接，优先从连接池获取"""
        with self._pool_lock:
            # 检查连接池中是否有可用连接
            if self._connection_key in self._connection_pool:
                try:
                    self.ssh, self.shell = self._connection_pool[self._connection_key]
                    # 测试连接是否还有效
                    self.shell.send('\n')
                    if self._wait_for_prompt(timeout=2):
                        self.logger.info(f"从连接池获取连接: {self.ip}")
                        return True
                except:
                    # 连接失效，从池中移除
                    self._connection_pool.pop(self._connection_key, None)
                    self.ssh = None
                    self.shell = None

        # 创建新连接
        retry_count = 3
        retry_delay = 2

        for attempt in range(retry_count):
            try:
                if self.ssh:
                    self.close()

                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # 设置连接超时
                socket.setdefaulttimeout(self.timeout)
                
                # 使用异步方式连接
                transport = self.ssh.get_transport()
                if transport:
                    transport.set_keepalive(60)  # 启用心跳
                
                self.ssh.connect(
                    self.ip,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False,
                    banner_timeout=10
                )

                self.shell = self.ssh.invoke_shell(
                    term='vt100',
                    width=160,
                    height=48
                )
                self.shell.settimeout(self.timeout)
                
                # 等待初始提示符
                if self._wait_for_prompt(timeout=5):
                    # 将有效连接添加到连接池
                    with self._pool_lock:
                        self._connection_pool[self._connection_key] = (self.ssh, self.shell)
                    return True
                else:
                    raise Exception("等待提示符超时")

            except AuthenticationException:
                self.logger.error(f"设备 {self.ip} 认证失败")
                break
                
            except (SSHException, socket.timeout) as e:
                self.logger.error(f"SSH连接错误 {self.ip}: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    
            except Exception as e:
                self.logger.error(f"连接设备 {self.ip} 失败: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    
            finally:
                if not self.shell and self.ssh:
                    self.close()

        return False

    def execute_command(self, command: str, wait_time: Optional[int] = None) -> str:
        """执行单个命令"""
        try:
            if not self.shell:
                raise Exception("SSH连接未建立")
            
            self.logger.debug(f"正在执行命令: {command}")
            
            # 清空缓冲区
            while self.shell.recv_ready():
                self.shell.recv(65535)
            
            # 发送命令
            self.shell.send(command + '\n')
            
            # 华为设备特殊处理
            if command.lower() == 'sy' or command.lower() == 'system-view':
                time.sleep(2)  # 等待系统视图切换
                # 发送回车确认进入系统视图
                self.shell.send('\n')
                time.sleep(1)
            
            # 特殊命令处理
            if command.lower().startswith(('sys', 'system-view')):
                wait_time = wait_time or 5
            elif any(cmd in command.lower() for cmd in ['reset', 'reboot', 'save']):
                wait_time = wait_time or 10
            else:
                wait_time = wait_time or 3
            
            # 收集输出
            output = ""
            start_time = time.time()
            no_output_count = 0
            
            while time.time() - start_time < wait_time:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
                    output += chunk
                    no_output_count = 0  # 重置无输出计数
                    
                    # 检查是否需要确认
                    if '[Y/N]' in chunk or '[yes/no]' in chunk:
                        self.logger.info(f"检测到确认提示，自动发送 'Y'")
                        time.sleep(0.5)
                        self.shell.send('Y\n')
                        time.sleep(1)
                        continue
                    
                    # 检查是否出现提示符
                    if '>' in chunk or '#' in chunk or ']' in chunk:
                        return output.strip()
                else:
                    no_output_count += 1
                    if no_output_count > 30:  # 如果连续3秒没有输出
                        break
                    time.sleep(0.1)
            
            # 命令可能没有明显的提示符返回，返回收集到的所有输出
            if output:
                return output.strip()
            
            self.logger.warning(f"命令 {command} 没有返回任何输出")
            return "命令执行无响应"
            
        except Exception as e:
            error_msg = f"执行命令失败: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

    def execute_commands(self, commands: List[str]) -> Dict[str, str]:
        """执行多个命令"""
        results = {}
        in_system_view = False
        
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
                
            self.logger.info(f"在设备 {self.ip} 上执行命令: {cmd}")
            
            # 系统视图状态跟踪
            if cmd.lower() in ['sy', 'system-view']:
                in_system_view = True
            elif cmd.lower() == 'quit' and in_system_view:
                in_system_view = False
            
            # 执行命令
            output = self.execute_command(cmd)
            results[cmd] = output
            
            # 检查命令执行结果
            lower_output = output.lower()
            if any(error in lower_output for error in ['error', 'failed', 'invalid', '无响应']):
                self.logger.warning(f"命令可能执行失败: {cmd}")
                self.logger.warning(f"输出: {output}")
            
            # 命令后等待
            if cmd.lower() in ['sy', 'system-view']:
                time.sleep(2)
            elif 'save' in cmd.lower():
                time.sleep(5)
            elif in_system_view:
                time.sleep(1)  # 系统视图下的命令多等待一下
            else:
                time.sleep(0.5)
                
        return results

    def close(self):
        """关闭SSH连接"""
        with self._pool_lock:
            if self._connection_key in self._connection_pool:
                self._connection_pool.pop(self._connection_key)
        
        if self.shell:
            try:
                self.shell.close()
            except:
                pass
            self.shell = None
            
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
            self.ssh = None
            
        self.logger.info(f"关闭与设备 {self.ip} 的连接")

    @classmethod
    def clear_connection_pool(cls):
        """清理连接池中的所有连接"""
        with cls._pool_lock:
            for ssh, shell in cls._connection_pool.values():
                try:
                    if shell:
                        shell.close()
                    if ssh:
                        ssh.close()
                except:
                    pass
            cls._connection_pool.clear() 