# Copyright (c) 2025 Anfer
"""
图片格式转换器主程序
================

这是一个基于PyQt5和Pillow的图形界面图片格式转换工具，
支持多种图片格式之间的批量转换，包括静态图片和动态图片。

主要特性：
- 支持JPEG、PNG、GIF、BMP、TIFF、WEBP、ICO等多种格式
- 支持批量文件和文件夹转换
- 支持动图处理（保持动画或转换为静态图）
- 支持质量调节和EXIF信息保留
- 支持拖拽添加文件
- 支持多线程处理，界面响应流畅
"""

import sys
import os
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QLineEdit, QProgressBar, QFileDialog,
                            QListWidget, QGroupBox, QCheckBox,
                            QButtonGroup, QRadioButton, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QIcon, QPalette, QColor, QCursor, QFontMetrics, QCursor
from PIL import Image

# 导入我们创建的模块
from convert_core import ConversionWorker
from status_bar_manager import StatusBarManager
from resource_manager import resource_path


class ClickableLabel(QLabel):
    """
    自定义可点击标签类
    
    只有点击文字区域才会触发点击事件，避免点击标签周围空白区域也触发事件的问题。
    增加了防抖动和异常处理机制，以应对高压连续点击测试场景。
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setText(text)
        # 启用鼠标跟踪以接收鼠标移动事件
        self.setMouseTracking(True)
        # 添加防抖动时间戳
        self.last_click_time = 0
        self.click_threshold = 300  # 300毫秒防抖动阈值
        
    def mousePressEvent(self, event):
        """
        重写鼠标按下事件，只在点击文字区域时触发
        增加防抖动和异常处理机制
        """
        try:
            # 获取当前时间戳
            current_time = time.time() * 1000  # 转换为毫秒
            
            # 检查是否在防抖动时间内
            if current_time - self.last_click_time < self.click_threshold:
                return  # 忽略过于频繁的点击
            
            # 检查点击位置是否在文字区域
            if self.is_point_on_text(event.pos()):
                self.last_click_time = current_time
                self.click()
                
            super().mousePressEvent(event)
        except Exception as e:
            # 捕获异常但不中断程序执行
            print(f"ClickableLabel mousePressEvent error: {e}")
            super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """
        重写鼠标移动事件，只在文字区域上方时改变光标样式
        增加异常处理机制
        """
        try:
            if self.is_point_on_text(event.pos()):
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(event)
        except Exception as e:
            # 捕获异常但不中断程序执行
            print(f"ClickableLabel mouseMoveEvent error: {e}")
            self.setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(event)
        
    def leaveEvent(self, event):
        """
        重写鼠标离开事件，恢复默认光标样式
        增加异常处理机制
        """
        try:
            self.setCursor(Qt.ArrowCursor)
            super().leaveEvent(event)
        except Exception as e:
            # 捕获异常但不中断程序执行
            print(f"ClickableLabel leaveEvent error: {e}")
            super().leaveEvent(event)
        
    def is_point_on_text(self, point):
        """
        判断点是否在文字区域上
        
        Args:
            point (QPoint): 鼠标位置点
            
        Returns:
            bool: 如果点在文字区域上则返回True，否则返回False
        """
        try:
            # 使用更简单的方法：直接检查点是否在文本内容边界内
            if not self.text():
                return False
                
            # 获取标签的字体度量
            font_metrics = QFontMetrics(self.font())
            
            # 获取文本的宽度和高度
            text_width = font_metrics.horizontalAdvance(self.text())
            text_height = font_metrics.height()
            
            # 获取标签的尺寸
            label_width = self.width()
            label_height = self.height()
            
            # 计算文本在标签中的位置（居中对齐）
            text_x = (label_width - text_width) // 2
            text_y = (label_height - text_height) // 2
            
            # 创建文本区域矩形
            text_rect = QRect(text_x, text_y, text_width, text_height)
            
            # 判断点是否在文本区域内
            return text_rect.contains(point)
        except Exception as e:
            # 发生异常时，默认返回False（不在文字区域上）
            print(f"ClickableLabel is_point_on_text error: {e}")
            return False
        
    def click(self):
        """
        点击事件处理方法，子类可以重写此方法
        """
        pass

class Chameleon(QMainWindow):
    """
    图片转换器主窗口类
    
    提供图形用户界面用于批量转换图片格式，集成所有功能模块。
    """
    
    def __init__(self):
        """
        初始化主窗口
        
        设置窗口标题、尺寸、图标和样式，并初始化UI组件。
        """
        super().__init__()
        self.setWindowTitle("Chameleon")
        self.setGeometry(100, 100, 900, 500)
        self.setWindowIcon(QIcon(resource_path('logo.ico')))
        
        # 语言设置 - 默认为中文
        self.current_language = "zh"  # zh for Chinese, en for English
        self.translations = {
            "zh": {
                "source_selection": "源文件选择",
                "add_files": "添加文件",
                "add_folder": "添加文件夹",
                "clear_list": "清空列表",
                "selected_files": "已选择 {} 个文件/文件夹",
                "conversion_settings": "转换设置",
                "target_format": "目标格式:",
                "output_directory": "输出目录:",
                "browse": "浏览",
                "default_output": "默认: 同源文件目录",
                "image_quality": "图片质量:",
                "low": "低",
                "medium": "中",
                "high": "高",
                "quality_note": "(适用于JPEG/WEBP/PNG/HEIF)",
                "animation_options": "动图处理选项",
                "animation_choices": [
                    "转换为静态图 (仅保存第一帧)",
                    "保存所有帧为单独文件",
                    "跳过所有动图文件",
                    "保持动图格式 (如果目标格式支持动画)"
                ],
                "overwrite_files": "覆盖同名文件",
                "preserve_exif": "保留EXIF信息",
                "start_conversion": "开始转换",
                "cancel": "取消",
                "ready": "信息: 就绪",
                "select_images": "选择图片文件",
                "select_folder": "选择图片文件夹",
                "select_output": "选择输出目录",
                "no_files": "请先添加要转换的文件或文件夹",
                "converting": "开始转换: {} 个文件/文件夹",
                "conversion_complete": "转换完成! 成功: {} 个, 失败: {} 个",
                "animated_files": " (动图: {} 个",
                "skipped_animated": ", 跳过: {} 个",
                "conversion_cancelled": "转换已取消",
                "file_added": "已添加文件: {}",
                "files_added": "已添加 {} 个文件",
                "folder_added": "已添加文件夹: {}",
                "list_cleared": "文件列表已清空",
                "output_set": "已设置输出目录: {}"
            },
            "en": {
                "source_selection": "Source File Selection",
                "add_files": "Add Files",
                "add_folder": "Add Folder",
                "clear_list": "Clear List",
                "selected_files": "{} files/folders selected",
                "conversion_settings": "Conversion Settings",
                "target_format": "Target Format:",
                "output_directory": "Output Directory:",
                "browse": "Browse",
                "default_output": "Default: Same as source directory",
                "image_quality": "Image Quality:",
                "low": "Low",
                "medium": "Medium",
                "high": "High",
                "quality_note": "(Applies to JPEG/WEBP/PNG/HEIF)",
                "animation_options": "Animation Processing Options",
                "animation_choices": [
                    "Convert to Static Image (Save First Frame Only)",
                    "Save All Frames as Separate Files",
                    "Skip All Animated Files",
                    "Preserve Animation Format (If Target Format Supports Animation)"
                ],
                "overwrite_files": "Overwrite Existing Files",
                "preserve_exif": "Preserve EXIF Information",
                "start_conversion": "Start Conversion",
                "cancel": "Cancel",
                "ready": "Info: Ready",
                "select_images": "Select Image Files",
                "select_folder": "Select Image Folder",
                "select_output": "Select Output Directory",
                "no_files": "Please add files or folders to convert first",
                "converting": "Starting conversion: {} files/folders",
                "conversion_complete": "Conversion completed! Success: {}, Failed: {}",
                "animated_files": " (Animated: {}",
                "skipped_animated": ", Skipped: {}",
                "conversion_cancelled": "Conversion cancelled",
                "file_added": "File added: {}",
                "files_added": "{} files added",
                "folder_added": "Folder added: {}",
                "list_cleared": "File list cleared",
                "output_set": "Output directory set: {}"
            }
        }
        
        # 设置界面样式 - 深色高对比度主题，使用圆润的细体字体
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                font-size: 9pt;
            }
            QGroupBox {
                border: 1px solid #3498db;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: normal;
                color: #ffffff;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #3498db;
                font-weight: normal;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: normal;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
            QListWidget, QTextEdit, QLineEdit, QComboBox {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #3498db;
                border-radius: 4px;
                padding: 5px;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                font-weight: normal;
            }
            QProgressBar {
                border: 1px solid #3498db;
                border-radius: 4px;
                text-align: center;
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
            QLabel {
                color: #ffffff;
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                font-weight: normal;
            }
            QCheckBox, QRadioButton {
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                font-weight: normal;
            }
        """)
        
        self.conversion_thread = None
        self.status_bar_manager = None  # 状态栏管理器实例
        self.title_label = None  # 标题标签引用，用于语言切换
        self.init_ui()  # 初始化用户界面
        
    def switch_language(self):
        """
        切换界面语言
        
        在中文和英文之间切换界面显示语言，但保持"Chameleon"项目名不变。
        """
        # 切换语言
        self.current_language = "en" if self.current_language == "zh" else "zh"
        
        # 更新窗口标题（保持"Chameleon"不变）
        self.setWindowTitle("Chameleon")
        
        # 更新标题标签（保持"Chameleon"不变）
        if self.title_label:
            self.title_label.setText("Chameleon")
        
        # 更新各个UI元素的文本
        # 源文件选择区域
        self.source_group.setTitle(self.tr("source_selection"))
        self.add_files_btn.setText(self.tr("add_files"))
        self.add_folder_btn.setText(self.tr("add_folder"))
        self.clear_files_btn.setText(self.tr("clear_list"))
        self.update_file_count()  # 更新文件计数显示
        
        # 转换设置区域
        self.settings_group.setTitle(self.tr("conversion_settings"))
        self.format_label.setText(self.tr("target_format"))
        self.output_label.setText(self.tr("output_directory"))
        self.browse_btn.setText(self.tr("browse"))
        self.output_edit.setPlaceholderText(self.tr("default_output"))
        self.quality_label.setText(self.tr("image_quality"))
        self.low_quality_radio.setText(self.tr("low"))
        self.medium_quality_radio.setText(self.tr("medium"))
        self.high_quality_radio.setText(self.tr("high"))
        self.quality_note.setText(self.tr("quality_note"))
        self.animation_group.setTitle(self.tr("animation_options"))
        
        # 更新动图处理选项
        self.animation_combo.clear()
        for choice in self.translations[self.current_language]["animation_choices"]:
            self.animation_combo.addItem(choice)
            
        # 其他选项
        self.overwrite_check.setText(self.tr("overwrite_files"))
        self.preserve_exif_check.setText(self.tr("preserve_exif"))
        
        # 控制按钮
        self.convert_btn.setText(self.tr("start_conversion"))
        self.cancel_btn.setText(self.tr("cancel"))
        
        # 状态栏
        if self.status_bar_manager:
            self.status_bar_manager.current_language = self.current_language
            self.status_bar_manager.default_message = self.tr("ready")
            self.status_bar_manager.show_default()
            
    def tr(self, key):
        """
        翻译文本
        
        根据当前语言设置获取对应的翻译文本。
        
        Args:
            key (str): 翻译键名
            
        Returns:
            str: 对应语言的翻译文本
        """
        return self.translations[self.current_language].get(key, key)
        
    def init_ui(self):
        """
        初始化用户界面
        
        创建并布局所有UI组件，包括文件选择区、转换设置区、控制按钮区等。
        """
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 启用拖拽功能
        self.setAcceptDrops(True)
        
        # 标题
        self.title_label = ClickableLabel("Chameleon")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #3498db; margin: 15px 0; font-size: 20px; font-weight: normal; font-family: 'Microsoft YaHei UI', '微软雅黑', 'Segoe UI', sans-serif;")
        # 重写click方法实现语言切换
        self.title_label.click = lambda: self.switch_language()
        main_layout.addWidget(self.title_label)
        
        # 源文件选择区域
        self.source_group = QGroupBox(self.tr("source_selection"))
        source_layout = QVBoxLayout()
        
        # 文件列表区域
        file_list_layout = QHBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        # 移除固定最小高度，让布局自然调整以与按钮底部对齐
        file_list_layout.addWidget(self.file_list)
        
        # 文件操作按钮
        file_btn_layout = QVBoxLayout()
        self.add_files_btn = QPushButton(self.tr("add_files"))
        self.add_files_btn.clicked.connect(self.add_files)
        
        self.add_folder_btn = QPushButton(self.tr("add_folder"))
        self.add_folder_btn.clicked.connect(self.add_folder)
        
        self.clear_files_btn = QPushButton(self.tr("clear_list"))
        self.clear_files_btn.clicked.connect(self.clear_files)
        self.clear_files_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; 
                background-color: #ffffff; 
                color: #3498db; 
                border: none; 
                font-weight: normal; 
                font-family: 'Microsoft YaHei UI', '微软雅黑', 'Segoe UI', sans-serif;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f0f8ff;
            }
            QPushButton:pressed {
                background-color: #d0e1f9;
            }
        """)
        
        file_btn_layout.addWidget(self.add_files_btn)
        file_btn_layout.addWidget(self.add_folder_btn)
        file_btn_layout.addWidget(self.clear_files_btn)
        file_btn_layout.addStretch()
        
        file_list_layout.addLayout(file_btn_layout)
        source_layout.addLayout(file_list_layout)
        
        # 文件计数
        self.file_count_label = QLabel(self.tr("selected_files").format(0))
        self.file_count_label.setAlignment(Qt.AlignRight)
        source_layout.addWidget(self.file_count_label)
        
        self.source_group.setLayout(source_layout)
        main_layout.addWidget(self.source_group)
        
        # 转换设置区域
        self.settings_group = QGroupBox(self.tr("conversion_settings"))
        settings_layout = QVBoxLayout()
        
        # 目标格式选择
        format_layout = QHBoxLayout()
        self.format_label = QLabel(self.tr("target_format"))
        format_layout.addWidget(self.format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG (.jpg)", "PNG (.png)", "GIF (.gif)", 
                                  "BMP (.bmp)", "TIFF (.tif)", "WEBP (.webp)", "ICO (.ico)", 
                                  "HEIF (.heic)"])
        self.format_combo.setCurrentIndex(1)  # 默认选择PNG
        format_layout.addWidget(self.format_combo)
        
        self.format_combo.currentIndexChanged.connect(self.toggle_custom_format)
        settings_layout.addLayout(format_layout)
        
        # 输出目录设置
        output_layout = QHBoxLayout()
        self.output_label = QLabel(self.tr("output_directory"))
        output_layout.addWidget(self.output_label)
        
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(self.tr("default_output"))
        output_layout.addWidget(self.output_edit)
        
        self.browse_btn = QPushButton(self.tr("browse"))
        self.browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(output_layout)
        
        # 图片质量设置
        quality_layout = QHBoxLayout()
        self.quality_label = QLabel(self.tr("image_quality"))
        quality_layout.addWidget(self.quality_label)
        
        # 创建质量选项按钮组
        self.quality_group = QButtonGroup(self)
        
        # 低质量选项
        self.low_quality_radio = QRadioButton(self.tr("low"))
        self.low_quality_radio.setChecked(False)
        self.quality_group.addButton(self.low_quality_radio, 50)
        quality_layout.addWidget(self.low_quality_radio)
        
        # 中等质量选项（默认）
        self.medium_quality_radio = QRadioButton(self.tr("medium"))
        self.medium_quality_radio.setChecked(True)
        self.quality_group.addButton(self.medium_quality_radio, 85)
        quality_layout.addWidget(self.medium_quality_radio)
        
        # 高质量选项
        self.high_quality_radio = QRadioButton(self.tr("high"))
        self.high_quality_radio.setChecked(False)
        self.quality_group.addButton(self.high_quality_radio, 100)
        quality_layout.addWidget(self.high_quality_radio)
        
        # 质量设置说明标签
        self.quality_note = QLabel(self.tr("quality_note"))
        self.quality_note.setStyleSheet("color: #95a5a6;")
        quality_layout.addWidget(self.quality_note)
        
        quality_layout.addStretch()
        settings_layout.addLayout(quality_layout)
        
        # 动画处理选项
        self.animation_group = QGroupBox(self.tr("animation_options"))
        animation_layout = QVBoxLayout()
        
        self.animation_combo = QComboBox()
        for choice in self.translations[self.current_language]["animation_choices"]:
            self.animation_combo.addItem(choice)
        animation_layout.addWidget(self.animation_combo)
        
        self.animation_group.setLayout(animation_layout)
        settings_layout.addWidget(self.animation_group)
        
        # 覆盖选项
        overwrite_layout = QHBoxLayout()
        self.overwrite_check = QCheckBox(self.tr("overwrite_files"))
        self.overwrite_check.setChecked(False)
        overwrite_layout.addWidget(self.overwrite_check)
        
        self.preserve_exif_check = QCheckBox(self.tr("preserve_exif"))
        self.preserve_exif_check.setChecked(True)
        overwrite_layout.addWidget(self.preserve_exif_check)
        settings_layout.addLayout(overwrite_layout)
        
        self.settings_group.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group)
        
        # 转换控制区域
        control_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        control_layout.addWidget(self.progress_bar, 4)
        
        self.convert_btn = QPushButton(self.tr("start_conversion"))
        self.convert_btn.setMinimumHeight(40)
        self.convert_btn.setStyleSheet("font-size: 14px; font-weight: normal; font-family: 'Microsoft YaHei UI', '微软雅黑', 'Segoe UI', sans-serif;")
        self.convert_btn.clicked.connect(self.start_conversion)
        control_layout.addWidget(self.convert_btn, 1)
        
        self.cancel_btn = QPushButton(self.tr("cancel"))
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; 
                background-color: #ffffff; 
                color: #3498db; 
                border: none; 
                font-weight: normal; 
                font-family: 'Microsoft YaHei UI', '微软雅黑', 'Segoe UI', sans-serif;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f0f8ff;
            }
            QPushButton:pressed {
                background-color: #d0e1f9;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #aaaaaa;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        self.cancel_btn.setEnabled(False)
        control_layout.addWidget(self.cancel_btn, 1)
        
        main_layout.addLayout(control_layout)
        
        # 状态栏
        self.status_label = QLabel(self.tr("ready"))
        self.status_label.setStyleSheet("color: #bdc3c7; padding: 5px; font-family: 'Microsoft YaHei UI', '微软雅黑', 'Segoe UI', sans-serif;")
        main_layout.addWidget(self.status_label)
        
        # 初始化状态栏管理器
        # 定义状态栏翻译字典
        status_translations = {
            "zh": {
                "ready": "信息: 就绪",
                "info_prefix": "信息",
                "warning_prefix": "警告",
                "error_prefix": "错误",
                "success_prefix": "成功",
                "progress_prefix": "进度"
            },
            "en": {
                "ready": "Info: Ready",
                "info_prefix": "Info",
                "warning_prefix": "Warning",
                "error_prefix": "Error",
                "success_prefix": "Success",
                "progress_prefix": "Progress"
            }
        }
        self.status_bar_manager = StatusBarManager(self.status_label, status_translations)
        self.status_bar_manager.current_language = self.current_language
        
    def toggle_custom_format(self, index):
        """
        切换动图处理选项的可见性
        
        根据选择的格式决定是否显示动图处理选项。
        
        Args:
            index (int): 格式选择下拉框的索引
        """
        # 根据选择的格式决定是否显示动图处理选项
        # 当目标格式支持动画时，可以选择保持动画格式
        # 当目标格式不支持动画时，需要显示动图处理选项（用户需要选择如何处理动图）
        animated_formats = ["GIF (.gif)", "WEBP (.webp)", "TIFF (.tif)", "HEIF (.heic)"]
        selected_format = self.format_combo.currentText()
        
        if selected_format in animated_formats:
            # 如果目标格式支持动画，显示动图处理选项并默认选择"保持动图格式"
            self.animation_group.setVisible(True)
            self.animation_combo.setCurrentIndex(3)  # 选择"保持动图格式"选项
        else:
            # 如果目标格式不支持动画，显示动图处理选项并默认选择"转换为静态图"
            self.animation_group.setVisible(True)
            self.animation_combo.setCurrentIndex(0)  # 选择"转换为静态图"选项
        
    def add_files(self):
        """
        添加文件到列表
        
        打开文件选择对话框，允许用户选择多个图片文件添加到转换列表。
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp *.ico *.heif *.heic);;所有文件 (*.*)"
        )
        
        if file_paths:
            self.file_list.addItems(file_paths)
            self.update_file_count()
            # 使用状态栏管理器更新状态
            if len(file_paths) == 1:
                self.status_bar_manager.show_info(f"已添加文件: {os.path.basename(file_paths[0])}")
            else:
                self.status_bar_manager.show_info(f"已添加 {len(file_paths)} 个文件")
    
    def add_folder(self):
        """
        添加文件夹到列表
        
        打开文件夹选择对话框，允许用户选择包含图片的文件夹添加到转换列表。
        """
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        
        if folder:
            self.file_list.addItem(folder)
            self.update_file_count()
            # 使用状态栏管理器更新状态
            self.status_bar_manager.show_info(f"已添加文件夹: {os.path.basename(folder)}")
    
    def clear_files(self):
        """
        清空文件列表
        
        移除转换列表中的所有文件和文件夹。
        """
        self.file_list.clear()
        self.update_file_count()
        # 使用状态栏管理器更新状态
        self.status_bar_manager.show_info("文件列表已清空")
        
    def dragEnterEvent(self, event):
        """
        接受文件拖拽事件
        
        允许用户通过拖拽方式添加文件到程序。
        
        Args:
            event (QDragEnterEvent): 拖拽进入事件
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        """
        处理文件拖放
        
        处理用户拖放到程序窗口的文件和文件夹。
        
        Args:
            event (QDropEvent): 拖放事件
        """
        urls = event.mimeData().urls()
        file_paths = []
        
        for url in urls:
            # 获取本地文件路径
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                # 如果是文件，检查是否为图片
                ext = os.path.splitext(file_path)[1].lower()
                if ext in Image.registered_extensions():
                    file_paths.append(file_path)
            elif os.path.isdir(file_path):
                # 如果是文件夹，直接添加
                self.file_list.addItem(file_path)
                self.update_file_count()
                self.status_bar_manager.show_info(f"已添加文件夹: {os.path.basename(file_path)}")
                return
                
        if file_paths:
            # 添加文件到列表
            self.file_list.addItems(file_paths)
            self.update_file_count()
            self.status_bar_manager.show_info(f"已添加 {len(file_paths)} 个文件")
    
    def browse_output(self):
        """
        浏览并选择输出目录
        
        打开文件夹选择对话框，允许用户指定转换后文件的输出目录。
        """
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.output_edit.setText(folder)
            # 使用状态栏管理器更新状态
            self.status_bar_manager.show_info(f"已设置输出目录: {os.path.basename(folder)}")
    
    def update_file_count(self):
        """
        更新文件计数显示
        
        更新界面上显示的文件和文件夹总数。
        """
        count = self.file_list.count()
        self.file_count_label.setText(self.tr("selected_files").format(count))
    
    def start_conversion(self):
        """
        开始转换任务
        
        收集用户设置的转换参数，创建并启动后台转换线程。
        """
        # 获取要转换的文件列表
        if self.file_list.count() == 0:
            self.status_bar_manager.show_warning("请先添加要转换的文件或文件夹")
            return
        
        # 获取目标格式
        format_text = self.format_combo.currentText()
        format_name = format_text.split(" ")[0]
        # 映射格式到扩展名 - 格式名在前，扩展名在后
        format_map = {
            "JPEG": ("JPEG", ".jpg"),
            "PNG": ("PNG", ".png"),
            "GIF": ("GIF", ".gif"),
            "BMP": ("BMP", ".bmp"),
            "TIFF": ("TIFF", ".tif"),
            "WEBP": ("WEBP", ".webp"),
            "ICO": ("ICO", ".ico"),
            "HEIF": ("HEIF", ".heic")
        }
        target_format = format_map[format_name]
        
        # 获取输出目录
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            output_dir = None
        
        # 获取动画处理选项
        animation_option = self.animation_combo.currentIndex() if self.animation_group.isVisible() else None
        
        # 获取其他选项
        overwrite = self.overwrite_check.isChecked()
        preserve_exif = self.preserve_exif_check.isChecked()
        
        # 获取质量参数（从单选按钮组）
        quality = self.quality_group.checkedId()
        if quality < 0:  # 如果没有选中任何按钮
            quality = 85  # 默认中等质量
        
        # 准备文件列表
        file_list = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        
        # 使用状态栏管理器更新状态
        self.status_bar_manager.show_info(f"开始转换: {len(file_list)} 个文件/文件夹")
        
        # 禁用UI控件
        self.convert_btn.setEnabled(False)
        self.add_files_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)
        self.clear_files_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # 创建并启动工作线程
        self.conversion_thread = ConversionWorker(
            file_list,
            target_format,
            output_dir,
            animation_option,
            overwrite,
            preserve_exif,
            quality
        )
        
        # 连接信号
        self.conversion_thread.progress_updated.connect(self.update_progress)
        self.conversion_thread.conversion_completed.connect(self.conversion_finished)
        self.conversion_thread.file_error.connect(self.handle_file_error)
        
        # 启动线程
        self.conversion_thread.start()
    
    def cancel_conversion(self):
        """
        取消转换任务
        
        停止正在进行的转换任务并恢复UI控件状态。
        """
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.cancel()
            self.status_bar_manager.show_info("转换已取消")
            self.convert_btn.setEnabled(True)
            self.add_files_btn.setEnabled(True)
            self.add_folder_btn.setEnabled(True)
            self.clear_files_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
    
    def update_progress(self, value, message):
        """
        更新进度条和状态信息
        
        Args:
            value (int): 进度值 (0-100)
            message (str): 状态消息
        """
        self.progress_bar.setValue(value)
        # 使用状态栏管理器更新状态
        self.status_bar_manager.show_progress(message)
    
    def handle_file_error(self, file_path, error):
        """
        处理文件处理错误
        
        Args:
            file_path (str): 出错的文件路径
            error (str): 错误信息
        """
        # 使用状态栏管理器更新状态
        self.status_bar_manager.show_error(f"{os.path.basename(file_path)} - {error}")
    
    def conversion_finished(self, success_count, fail_count, animated_count, skipped_animated):
        """
        转换任务完成处理
        
        Args:
            success_count (int): 成功转换的文件数
            fail_count (int): 转换失败的文件数
            animated_count (int): 检测到的动图数
            skipped_animated (int): 跳过的动图数
        """
        # 启用UI控件
        self.convert_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.clear_files_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # 构建详细的完成消息
        message = f"转换完成! 成功: {success_count} 个, 失败: {fail_count} 个"
        
        if animated_count > 0:
            message += f" (动图: {animated_count} 个"
            if skipped_animated > 0:
                message += f", 跳过: {skipped_animated} 个"
            message += ")"
        
        # 使用状态栏管理器更新状态
        if fail_count > 0:
            self.status_bar_manager.show_error(message)
        else:
            self.status_bar_manager.show_success(message)
        
        # 重置进度条
        self.progress_bar.setValue(0)


if __name__ == "__main__":
    """
    程序入口点
    
    创建Qt应用程序实例，设置界面样式，并启动主窗口。
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置应用程序图标（解决PyInstaller打包后窗口无图标问题）
    app.setWindowIcon(QIcon(resource_path('logo.ico')))

    # 设置应用样式 - 深色高对比度主题
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(0, 0, 0))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(26, 26, 26))
    palette.setColor(QPalette.AlternateBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(52, 152, 219))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    window = Chameleon()
    window.show()
    sys.exit(app.exec_())