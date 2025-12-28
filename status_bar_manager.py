# Copyright (c) 2025 Anfer
"""
状态栏管理模块
============

该模块提供统一的状态栏消息管理功能，支持不同类型的消息显示
（信息、警告、错误、成功、进度等），并可设置消息显示时长。
支持中英文互译功能。
"""

from PyQt5.QtCore import QTimer

class StatusBarManager:
    """
    状态栏管理器类
    
    统一管理应用程序的状态栏显示，提供一致的用户反馈体验。
    支持多种消息类型和自动恢复默认状态功能。
    支持中英文互译功能。
    """
    
    def __init__(self, status_label, translations=None):
        """
        初始化状态栏管理器
        
        Args:
            status_label (QLabel): 用于显示状态的QLabel控件
            translations (dict, optional): 翻译字典，包含中英文对照
        """
        self.status_label = status_label
        self.translations = translations or {"zh": {}, "en": {}}
        self.current_language = "zh"  # 默认为中文
        self.default_message = "信息: 就绪"  # 默认状态消息
        self.default_style = "color: #ffffff; padding: 5px;"  # 默认样式（白色，适应深色主题）
        self.show_default()  # 显示默认状态
        
    def set_translations(self, translations, current_language="zh"):
        """
        设置翻译字典和当前语言
        
        Args:
            translations (dict): 翻译字典，包含中英文对照
            current_language (str): 当前语言，"zh" 或 "en"
        """
        self.translations = translations
        self.current_language = current_language
        # 更新默认消息
        self.default_message = self.tr("ready")
        self.show_default()
        
    def tr(self, key):
        """
        翻译文本
        
        根据当前语言设置获取对应的翻译文本。
        
        Args:
            key (str): 翻译键名
            
        Returns:
            str: 对应语言的翻译文本
        """
        return self.translations.get(self.current_language, {}).get(key, key)
        
    def switch_language(self):
        """
        切换语言
        
        在中文和英文之间切换显示语言。
        """
        self.current_language = "en" if self.current_language == "zh" else "zh"
        # 更新默认消息
        self.default_message = self.tr("ready")
        self.show_default()
        
    def show_default(self):
        """
        显示默认状态消息
        
        将状态栏恢复为默认消息和默认样式。
        """
        self.status_label.setText(self.default_message)
        self.status_label.setStyleSheet(self.default_style)
    
    def show_message(self, message, timeout=None):
        """
        显示状态消息
        
        Args:
            message (str): 要显示的消息内容
            timeout (int, optional): 消息显示的超时时间（毫秒）
                                   超时后自动恢复默认消息
        """
        self.status_label.setText(message)
        if timeout:
            # 使用 QTimer 实现超时恢复默认消息
            timer = QTimer()
            timer.timeout.connect(self.show_default)
            timer.setSingleShot(True)  # 单次触发
            timer.start(timeout)
    
    def show_info(self, message):
        """
        显示普通信息消息
        
        Args:
            message (str): 信息内容
        """
        self.status_label.setStyleSheet("color: #ffffff; padding: 5px;")  # 使用白色样式
        prefix = self.tr("info_prefix")
        self.show_message(f"{prefix}: {message}" if prefix else message)
    
    def show_warning(self, message):
        """
        显示警告消息
        
        Args:
            message (str): 警告内容
        """
        # 设置黄色警告样式，提高在黑色背景上的可见度
        self.status_label.setStyleSheet("color: #f1c40f; padding: 5px;")
        prefix = self.tr("warning_prefix")
        self.show_message(f"{prefix}: {message}" if prefix else message)
    
    def show_error(self, message):
        """
        显示错误消息
        
        Args:
            message (str): 错误内容
        """
        # 设置鲜红色错误样式，提高在黑色背景上的可见度
        self.status_label.setStyleSheet("color: #e74c3c; padding: 5px;")
        prefix = self.tr("error_prefix")
        self.show_message(f"{prefix}: {message}" if prefix else message)
    
    def show_success(self, message):
        """
        显示成功消息
        
        Args:
            message (str): 成功内容
        """
        # 设置亮绿色成功样式，提高在黑色背景上的可见度
        self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
        prefix = self.tr("success_prefix")
        self.show_message(f"{prefix}: {message}" if prefix else message)
    
    def show_progress(self, message):
        """
        显示进度消息
        
        Args:
            message (str): 进度信息内容
        """
        self.status_label.setStyleSheet("color: #ffffff; padding: 5px;")  # 使用白色样式
        prefix = self.tr("progress_prefix")
        self.show_message(f"{prefix}: {message}" if prefix else message)