# Copyright (c) 2025 Anfer
"""
资源路径管理模块
==============

该模块提供统一的资源路径获取功能，支持开发环境和PyInstaller打包后的运行环境。
确保程序能够正确找到所需的资源文件（如图标、配置文件等）。
"""

import sys
import os

def resource_path(relative_path):
    """
    获取资源文件的绝对路径
    
    自动识别运行环境（开发环境或PyInstaller打包环境），返回正确的资源路径。
    解决PyInstaller打包后资源文件找不到的问题。
    
    Args:
        relative_path (str): 资源文件相对于项目根目录的相对路径
        
    Returns:
        str: 资源文件的绝对路径
        
    Example:
        icon_path = resource_path('assets/logo.ico')
    """
    # 判断是否为PyInstaller打包环境
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境下的当前目录
        base_path = os.path.abspath(".")
    
    # 拼接完整路径并返回
    return os.path.join(base_path, relative_path)