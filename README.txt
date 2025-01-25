网络拓扑发现工具 v1.0.0
=====================

功能特点：
1. 自动发现网络设备
2. 生成网络拓扑图
3. 支持跨网段发现
4. 设备配置管理
5. 文件传输功能

使用说明：
1. 双击 NetworkTopologyTool.exe 运行程序
2. 在"网络拓扑"标签页点击"开始发现"
3. 等待扫描完成后查看拓扑图
4. 可以导出拓扑图或设备列表

注意事项：
1. 需要管理员权限运行
2. 首次运行可能被防火墙拦截
3. 扫描可能需要几分钟时间 


打包命令：pyinstaller --noconfirm --onefile --windowed --icon=app.ico --add-data "gui;gui" --add-data "core;core" --hidden-import=paramiko --hidden-import=networkx --hidden-import=plotly --name="网络自动化运维工具" main.py   


打包完成后，exe文件会在 dist 目录下。这个exe文件可以在没有Python环境的Windows系统上直接运行。
注意事项：
确保在项目根目录下运行此命令
如果没有图标文件，可以去掉 --icon=app.ico 参数
如果需要显示控制台窗口（用于调试），可以去掉 --windowed 参数
4. 如果遇到缺少依赖的问题，可以根据错误提示添加更多的 --hidden-import 参数