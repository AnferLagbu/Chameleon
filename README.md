# Chameleon
## 🖼️ 一个简单易用的图片格式转换工具 / A Simple & Easy-to-Use Image Format Conversion Tool
> 最初我只是想把一些WEBP动图转换成GIF表情包，但网上提供的大多都是收费服务，且不可部署到本地。所以我决定自己写一个，这就是此项目的由来。
> Initially, I just wanted to convert some WEBP animated images into GIF emoticons, but most services provided online were paid and could not be deployed locally. So I decided to write my own, which is how this project came into being.

## 🎯 我为什么做这个工具？ / Why Did I Create This Tool?
作为一个学生，经常需要在不同平台之间传输和使用图片，特别是聊天时用的表情包。但很多时候我们会遇到这样的问题：
As a student, I often need to transfer and use images across different platforms, especially memes for chatting. But we frequently encounter these issues:
- 下载的动图是WEBP格式，QQ/微信不支持 / Downloaded animated images are in WEBP format, which is not supported by QQ/WeChat
- 想要压缩图片节省空间 / Want to compress images to save storage space
- 需要批量处理大量图片 / Need to batch process a large number of images

所以我就做了这个小工具，希望能帮助到有同样困扰的人。
So I created this small tool, hoping to help others who face the same troubles.

## ✨ 主要功能 / Key Features
- **格式转换**：支持 JPG、PNG、GIF、BMP、TIFF、WEBP、ICO 等常见格式互转
  **Format Conversion**: Supports mutual conversion between common formats such as JPG, PNG, GIF, BMP, TIFF, WEBP, ICO
- **动图处理**：/ Animated Image Processing:
  - 把动图转成静态图（只保留第一帧）/ Convert animated images to static images (retain only the first frame)
  - 把动图拆分成多张静态图 / Split animated images into multiple static frames
  - 跳过动图不转换 / Skip animated images without conversion
- **批量处理**：可以一次转换多个文件或者整个文件夹
  **Batch Processing**: Convert multiple files or entire folders at once
- **质量调节**：支持调整图片质量来控制文件大小
  **Quality Adjustment**: Adjust image quality to control file size
- **简单界面**：图形化界面，点点鼠标就能用
  **User-Friendly Interface**: Graphical interface, easy to use with just a few clicks

## 🚀 快速开始 / Quick Start
### 方法一：直接运行（推荐）/ Method 1: Run Directly (Recommended)
如果你下载的是发行版，直接双击它就可以打开程序了。
If you downloaded the release version, double-click it to launch the program directly.

### 方法二：从源码运行 / Method 2: Run from Source Code
如果你想要自己修改代码或者学习，可以按以下步骤操作：
If you want to modify the code yourself or learn, follow these steps:
1. 确保电脑安装了 Python（建议 3.6 以上版本）/ Ensure Python is installed on your computer (version 3.6 or higher is recommended)
2. 安装依赖库：/ Install dependency libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. 运行程序：/ Run the program:
   ```bash
   python main.py
   ```

## 📦 项目打包 / Project Packaging
如果你想将 Chameleon 打包成独立的可执行文件，可以使用 PyInstaller 工具。
If you want to package Chameleon into a standalone executable file, you can use the PyInstaller tool.

### 安装 PyInstaller / Install PyInstaller
```bash
pip install pyinstaller
```

### 打包命令 / Packaging Commands
1. 使用PyInstaller直接打包（推荐）:/ Package directly with PyInstaller (Recommended):
   ```bash
   pyinstaller --noconfirm --onefile --windowed --icon="logo.ico" --name="Chameleon" --add-data="logo.ico;." main.py
   ```
2. 使用现有的spec文件打包:/ Package with the existing spec file:
   ```bash
   pyinstaller Chameleon.spec
   ```
3. 更详细的打包命令:/ More detailed packaging command:
   ```bash
   pyinstaller --noconfirm --onefile --windowed --icon="logo.ico" --name="Chameleon" --add-data="logo.ico;." main.py
   ```

### 参数说明 / Parameter Explanation
- `--noconfirm`: 覆盖现有文件时不询问确认 / Overwrite existing files without confirmation
- `--onefile`: 打包成单个可执行文件 / Package into a single executable file
- `--windowed`: 不显示控制台窗口 / Do not display the console window
- `--icon="logo.ico"`: 设置可执行文件的图标 / Set the icon for the executable file
- `--name="Chameleon"`: 设置生成的可执行文件名称 / Set the name of the generated executable file
- `--add-data="logo.ico;."`: 将logo.ico文件包含到打包文件中 / Include the logo.ico file in the packaged files

打包完成后，可执行文件将位于 `dist` 文件夹中。
After packaging is complete, the executable file will be located in the `dist` folder.

## 📖 使用教程 / User Guide
### 语言切换 / Language Switching
- 点击顶部的"Chameleon"标题可以在中英文界面之间切换 / Click the "Chameleon" title at the top to switch between Chinese and English interfaces

### 添加图片 / Add Images
- 点击"添加文件"选择单个或多个图片 / Click "Add Files" to select one or multiple images
- 点击"添加文件夹"选择整个文件夹 / Click "Add Folder" to select an entire folder
- 或者直接把文件拖拽到程序窗口里 / Or directly drag and drop files into the program window

### 选择转换格式 / Select Target Format
- 在"目标格式"下拉菜单中选择你想要的格式 / Select your desired format from the "Target Format" dropdown menu
- 比如把WEBP转成GIF就可以选"GIF(.gif)" / For example, select "GIF(.gif)" to convert WEBP to GIF

### 设置输出位置 / Set Output Location
- 可以选择转换后的文件保存在哪里 / You can choose where to save the converted files
- 不设置的话默认保存在原文件旁边 / If not set, files will be saved next to the original files by default

### 调整质量 / Adjust Quality
- 对于 JPG/WEBP/PNG 格式可以调节质量 / Quality adjustment is available for JPG/WEBP/PNG formats
- "中"档位通常就够用了 / The "Medium" level is usually sufficient

### 处理动图 / Handle Animated Images
- 如果转换的目标格式不支持动画（比如JPG）/ If the target format does not support animation (e.g., JPG)
- 可以选择怎么处理动图：/ You can choose how to handle animated images:
  - 转成静态图（只保留第一帧）/ Convert to static image (retain only the first frame)
  - 拆分成多张图 / Split into multiple images
  - 跳过不转换 / Skip conversion

### 开始转换 / Start Conversion
- 点击"开始转换"按钮 / Click the "Start Conversion" button
- 等待转换完成即可 / Wait for the conversion to finish

## 📄 关于开源 / About Open Source
这个项目完全免费并且开源，你可以随意使用、修改和分享。如果觉得好用，欢迎推荐给其他有需要的人！
This project is completely free and open source. You can use, modify, and share it freely. If you find it useful, feel free to recommend it to others in need!

## 👨‍💻 作者 / Author
Anfer ([GitHub](https://github.com/Ancante/))
