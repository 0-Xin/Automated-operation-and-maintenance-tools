from PIL import Image, ImageDraw

# 创建一个256x256的图像
img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 绘制一个简单的网络图标
draw.ellipse((50, 50, 206, 206), fill='#4A9EFF')
draw.rectangle((78, 78, 178, 178), fill='white')

# 保存为ICO文件
img.save('icon.ico') 