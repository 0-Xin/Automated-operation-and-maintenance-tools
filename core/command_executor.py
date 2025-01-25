import threading
from typing import List, Dict, Callable, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, wait
from .ssh_manager import SSHManager
import time

class CommandExecutor:
    def __init__(self, max_threads: int = 5):
        self.logger = logging.getLogger(__name__)
        self.results = {}
        self._lock = threading.Lock()
        self.max_threads = max_threads
        self.progress_callback = None
        self.executor = ThreadPoolExecutor(
            max_workers=max_threads,
            thread_name_prefix="CmdExec"
        )
        self.futures: List[Future] = []
        self.is_running = False
        self._task_queue = []  # 任务队列
        self._active_tasks = set()  # 活动任务集合

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """设置进度回调函数"""
        self.progress_callback = callback

    def add_task(self, device: Dict, commands: List[str]) -> None:
        """添加任务到队列"""
        self._task_queue.append((device, commands))

    def execute_device_commands(
        self,
        ip: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout: Optional[int] = None
    ) -> Dict:
        """为单个设备执行命令"""
        result = {
            'ip': ip,
            'status': 'failed',
            'commands': {},
            'error': None,
            'start_time': time.time()
        }

        try:
            # 获取或创建SSH连接
            ssh = SSHManager(ip, username, password, port=port)
            if ssh.connect():
                # 分批执行命令以避免长时间阻塞
                batch_size = 5
                for i in range(0, len(commands), batch_size):
                    batch_commands = commands[i:i + batch_size]
                    command_results = ssh.execute_commands(batch_commands)
                    result['commands'].update(command_results)
                    
                    # 检查是否需要取消执行
                    if not self.is_running:
                        break
                
                result['status'] = 'success'
                self.logger.info(f"设备 {ip} 命令执行完成")
            else:
                result['error'] = 'Connection failed'
                self.logger.error(f"设备 {ip} 连接失败")

        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"设备 {ip} 执行出错: {str(e)}")
        finally:
            ssh.close()
            result['end_time'] = time.time()

        with self._lock:
            self.results[ip] = result
            if self.progress_callback:
                completed = len(self.results)
                total = len(self.pending_devices)
                self.progress_callback(completed, total)

        return result

    def batch_execute(
        self,
        devices: List[Dict],
        command_map: Dict[str, List[str]],
        timeout: Optional[int] = None
    ) -> Dict:
        """批量执行命令"""
        if self.is_running:
            raise RuntimeError("已有命令正在执行")

        self.is_running = True
        self.results.clear()
        self.pending_devices = devices
        self.futures.clear()
        self._task_queue.clear()
        self._active_tasks.clear()

        try:
            # 将所有任务添加到队列
            for device in devices:
                ip = device['ip']
                commands = command_map.get(ip, [])
                if commands:
                    self.add_task(device, commands)

            # 创建任务执行器
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                while self._task_queue or self._active_tasks:
                    # 检查是否需要取消执行
                    if not self.is_running:
                        break
                        
                    # 提交新任务
                    while len(self._active_tasks) < self.max_threads and self._task_queue:
                        device, commands = self._task_queue.pop(0)
                        future = executor.submit(
                            self.execute_device_commands,
                            device['ip'],
                            device['username'],
                            device['password'],
                            commands,
                            device.get('port', 22),
                            timeout
                        )
                        self._active_tasks.add(future)
                    
                    # 处理完成的任务
                    done, _ = wait(self._active_tasks, timeout=0.1)
                    for future in done:
                        try:
                            result = future.result()
                            self.results[result['ip']] = result
                        except Exception as e:
                            self.logger.error(f"任务执行失败: {str(e)}")
                        finally:
                            self._active_tasks.remove(future)

        except Exception as e:
            self.logger.error(f"批量执行过程中发生错误: {str(e)}")
        finally:
            self.is_running = False
            self._print_statistics()
            # 清理连接池
            SSHManager.clear_connection_pool()

        return self.results

    def cancel_all(self) -> None:
        """取消所有正在执行的任务"""
        if self.is_running:
            self.is_running = False
            self._task_queue.clear()
            for future in self._active_tasks:
                future.cancel()
            self._active_tasks.clear()
            self.logger.info("已取消所有正在执行的任务")

    def _print_statistics(self) -> None:
        """打印执行统计信息"""
        total = len(self.results)
        success = sum(1 for r in self.results.values() if r['status'] == 'success')
        failed = total - success
        
        # 计算总执行时间
        total_time = sum(
            r.get('end_time', 0) - r.get('start_time', 0)
            for r in self.results.values()
        )
        avg_time = total_time / total if total > 0 else 0
        
        self.logger.info("执行统计:")
        self.logger.info(f"总计设备: {total}")
        self.logger.info(f"成功: {success}")
        self.logger.info(f"失败: {failed}")
        self.logger.info(f"平均执行时间: {avg_time:.2f}秒")
        
        if failed > 0:
            self.logger.info("失败设备列表:")
            for ip, result in self.results.items():
                if result['status'] == 'failed':
                    self.logger.info(f"- {ip}: {result.get('error', '未知错误')}")

    def get_progress(self) -> tuple:
        """获取执行进度"""
        total = len(self.pending_devices)
        completed = len(self.results)
        return completed, total 