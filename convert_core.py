# Copyright (c) 2025 Anfer
"""
图片格式转换核心模块
==================

该模块提供了图片批量转换的核心功能，支持多种图片格式之间的转换，
包括静态图片和动态图片（GIF、WebP、TIFF）的处理。

主要功能：
- 支持多线程并发转换，提高转换效率
- 支持动态图片的特殊处理（保持动画效果或转换为静态图）
- 支持质量参数调节
- 支持EXIF信息保留
- 支持文件名冲突处理
"""

import os
import glob
from PIL import Image
import pillow_heif  # 导入pillow_heif库以支持HEIF格式
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from PyQt5.QtCore import QThread, pyqtSignal

# 注册HEIF格式支持
pillow_heif.register_heif_opener()

# 定义支持动画效果的图片格式集合
# 这些格式支持多帧动画播放
ANIMATED_FORMATS = ['GIF', 'WEBP', 'TIFF', 'HEIF']

class ConversionWorker(QThread):
    """
    图片转换工作线程类
    
    继承自QThread，负责在后台执行图片转换任务以避免界面卡顿。
    通过信号机制与主线程通信，报告进度和结果。
    """
    
    # 定义用于与主线程通信的信号
    progress_updated = pyqtSignal(int, str)  # 进度更新信号 (进度值0-100, 状态消息)
    conversion_completed = pyqtSignal(int, int, int, int)  # 转换完成信号 (成功数, 失败数, 动图数, 跳过的动图数)
    file_error = pyqtSignal(str, str)  # 文件错误信号 (文件路径, 错误消息)
    
    def __init__(self, file_list, target_format, output_dir, animation_option, overwrite, preserve_exif, quality):
        """
        初始化转换工作线程实例
        
        Args:
            file_list (list): 待转换的文件路径列表，可以包含文件和文件夹路径
            target_format (tuple): 目标格式元组 (格式名称, 扩展名)，例如 ('JPEG', '.jpg')
            output_dir (str): 输出目录路径，None表示与源文件同目录
            animation_option (int): 动图处理选项 0-转换为静态图 1-保存所有帧 2-跳过动图
            overwrite (bool): 是否覆盖同名文件
            preserve_exif (bool): 是否保留EXIF信息
            quality (int): 图片质量参数 0-100
        """
        super().__init__()
        self.file_list = file_list
        self.target_format = target_format
        self.output_dir = output_dir
        self.animation_option = animation_option
        self.overwrite = overwrite
        self.preserve_exif = preserve_exif
        self.quality = quality
        self.canceled = False
        
        # 初始化各类文件计数器
        self.success_count = 0      # 成功转换的文件数
        self.fail_count = 0         # 转换失败的文件数
        self.animated_count = 0     # 检测到的动图数
        self.skipped_animated = 0   # 跳过的动图数
        self.lock = threading.Lock()  # 用于保护计数器的线程锁
        
    def run(self):
        """
        线程主执行函数
        
        使用线程池并发处理文件转换任务，根据CPU核心数自动调整线程数量。
        优化了取消机制，使其能够更有效地停止处理。
        """
        total_files = len(self.file_list)
        
        # 重置计数器
        self.success_count = 0
        self.fail_count = 0
        self.animated_count = 0
        self.skipped_animated = 0
        
        # 创建线程池，最多使用4个线程或CPU核心数-1个线程，最少1个
        max_workers = min(4, max(1, os.cpu_count() - 1))
        
        # 存储提交的任务，以便在取消时能够尝试取消它们
        submitted_futures = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有转换任务到线程池
            future_to_index = {}
            for i, source_path in enumerate(self.file_list):
                # 检查是否已取消转换任务
                if self.canceled:
                    break
                # 提交单个文件处理任务到线程池
                future = executor.submit(self.process_file, source_path, i, total_files)
                future_to_index[future] = i
                submitted_futures.append(future)
            
            # 处理已完成的任务并更新计数器
            for future in as_completed(future_to_index):
                # 检查是否已取消转换任务
                if self.canceled:
                    # 尝试取消所有未完成的任务
                    for pending_future in future_to_index:
                        if not pending_future.done():
                            pending_future.cancel()
                    break
                
                try:
                    result = future.result()
                    if result:
                        # 线程安全地更新计数器
                        with self.lock:
                            self.success_count += result.get('success', 0)
                            self.fail_count += result.get('fail', 0)
                            self.animated_count += result.get('animated', 0)
                            self.skipped_animated += result.get('skipped', 0)
                except Exception as e:
                    # 异常处理：增加失败计数并发送错误信号
                    with self.lock:
                        self.fail_count += 1
                    self.file_error.emit("未知文件", f"处理错误: {str(e)}")
        
        # 发送转换完成信号（除非被取消）
        if not self.canceled:
            self.conversion_completed.emit(
                self.success_count, 
                self.fail_count, 
                self.animated_count, 
                self.skipped_animated
            )
        else:
            # 发送取消完成信号，让UI知道处理已停止
            self.progress_updated.emit(0, "转换已取消")
    
    def process_file(self, source_path, index, total_files):
        """
        处理单个文件的转换任务
        
        在线程池中并发执行，根据文件类型调用相应的处理方法。
        改进了取消检查点，确保任务可以及时响应取消操作。
        
        Args:
            source_path (str): 源文件路径
            index (int): 文件索引
            total_files (int): 总文件数
            
        Returns:
            dict: 包含处理结果统计的字典
                - success: 成功数
                - fail: 失败数
                - animated: 动图数
                - skipped: 跳过数
        """
        # 检查是否已取消转换任务
        if self.canceled:
            return None
            
        # 更新进度信息
        self.progress_updated.emit(
            int((index + 1) / total_files * 100), 
            f"处理中: {os.path.basename(source_path)}"
        )
        
        try:
            # 检查是否为文件夹
            if os.path.isdir(source_path):
                return self.process_directory(source_path, index, total_files)
                
            # 检查是否已取消转换任务
            if self.canceled:
                return None
                
            # 检查是否为动图
            is_animated = self.is_animated_image(source_path)
            animated_count = 0
            if is_animated:
                animated_count = 1
                self.progress_updated.emit(
                    int((index + 1) / total_files * 100), 
                    f"检测到动图: {os.path.basename(source_path)}"
                )
            
            # 检查是否已取消转换任务
            if self.canceled:
                return None
                
            # 执行图片转换
            output_path, warning = self.convert_image(
                source_path, 
                self.target_format, 
                self.output_dir,
                self.animation_option,
                self.quality
            )
            
            # 检查是否已取消转换任务
            if self.canceled:
                return None
                
            # 统计处理结果
            success_count = 0
            fail_count = 0
            skipped_count = 0
            
            if output_path:
                success_count = 1
                result_msg = "转换成功"
                if warning:
                    result_msg += f" ({warning})"
                    if "跳过" in warning:
                        skipped_count = 1
                self.progress_updated.emit(
                    int((index + 1) / total_files * 100), 
                    f"{result_msg}: {os.path.basename(output_path)}"
                )
            else:
                fail_count = 1
                if warning:
                    self.file_error.emit(source_path, warning)
                else:
                    self.file_error.emit(source_path, "转换失败")
            
            return {
                'success': success_count,
                'fail': fail_count,
                'animated': animated_count,
                'skipped': skipped_count
            }
                    
        except Exception as e:
            # 使用更具体的异常捕获，避免捕获KeyboardInterrupt等系统异常
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            self.file_error.emit(source_path, f"错误: {str(e)}")
            return {
                'success': 0,
                'fail': 1,
                'animated': 0,
                'skipped': 0
            }
    
    def process_directory(self, dir_path, index, total_files):
        """
        处理文件夹中的所有图片文件
        
        遍历指定文件夹中的所有图片文件并逐个进行转换处理。
        改进了取消检查机制和异常处理。
        
        Args:
            dir_path (str): 文件夹路径
            index (int): 文件夹索引
            total_files (int): 总文件数
            
        Returns:
            dict: 包含处理结果统计的字典
        """
        # 检查是否已取消转换任务
        if self.canceled:
            return {
                'success': 0,
                'fail': 0,
                'animated': 0,
                'skipped': 0
            }
        
        # 查找文件夹中的所有图片文件
        files = []
        try:
            for ext in Image.registered_extensions().keys():
                files.extend(glob.glob(os.path.join(dir_path, f"*{ext}")))
        except Exception as e:
            self.file_error.emit(dir_path, f"读取文件夹内容失败: {str(e)}")
            return {
                'success': 0,
                'fail': 0,
                'animated': 0,
                'skipped': 0
            }
        
        dir_file_count = len(files)
        if dir_file_count == 0:
            self.progress_updated.emit(
                int((index + 1) / total_files * 100), 
                f"文件夹中没有图片: {os.path.basename(dir_path)}"
            )
            return {
                'success': 0,
                'fail': 0,
                'animated': 0,
                'skipped': 0
            }
            
        self.progress_updated.emit(
            int((index + 1) / total_files * 100), 
            f"处理文件夹: {os.path.basename(dir_path)} ({dir_file_count} 个文件)"
        )
        
        # 创建子目录作为输出目录
        dir_output = self.output_dir if self.output_dir else dir_path
        dir_name = os.path.basename(dir_path)
        output_subdir = os.path.join(dir_output, f"{dir_name}_converted")
        try:
            os.makedirs(output_subdir, exist_ok=True)
        except Exception as e:
            self.file_error.emit(dir_path, f"创建输出目录失败: {str(e)}")
            return {
                'success': 0,
                'fail': 0,
                'animated': 0,
                'skipped': 0
            }
        
        # 顺序处理文件夹中的每个文件
        success_count = 0
        fail_count = 0
        animated_count = 0
        skipped_count = 0
        
        for i, file_path in enumerate(files):
            # 检查是否已取消转换任务
            if self.canceled:
                break
                
            try:
                # 检查是否为动图
                is_animated = self.is_animated_image(file_path)
                if is_animated:
                    animated_count += 1
                    self.progress_updated.emit(
                        int((index + 1) / total_files * 100), 
                        f"检测到动图: {os.path.basename(file_path)}"
                    )
                
                # 执行图片转换
                output_path, warning = self.convert_image(
                    file_path, 
                    self.target_format, 
                    output_subdir,
                    self.animation_option,
                    self.quality
                )
                
                # 检查是否已取消转换任务
                if self.canceled:
                    break
                
                # 统计处理结果
                if output_path:
                    success_count += 1
                    result_msg = "转换成功"
                    if warning:
                        result_msg += f" ({warning})"
                        if "跳过" in warning:
                            skipped_count += 1
                    # 更精确的进度更新
                    current_progress = int((index + 1 + (i + 1) / dir_file_count) / total_files * 100)
                    self.progress_updated.emit(
                        min(current_progress, 100), 
                        f"{result_msg}: {os.path.basename(file_path)}"
                    )
                else:
                    fail_count += 1
                    if warning:
                        self.file_error.emit(file_path, warning)
                    else:
                        self.file_error.emit(file_path, "转换失败")
                        
            except Exception as e:
                # 使用更具体的异常捕获
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                fail_count += 1
                self.file_error.emit(file_path, f"错误: {str(e)}")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'animated': animated_count,
            'skipped': skipped_count
        }
    
    def is_animated_image(self, source_path):
        """
        检查图片是否为动图
        
        通过多种方式检测图片是否包含动画帧。
        
        Args:
            source_path (str): 图片文件路径
            
        Returns:
            bool: True表示是动图，False表示不是动图
        """
        try:
            with Image.open(source_path) as img:
                # 检查是否具有动画属性
                if hasattr(img, 'is_animated') and img.is_animated:
                    return True
                
                # 特殊处理TIFF多页格式
                if img.format == 'TIFF' and hasattr(img, 'n_frames') and img.n_frames > 1:
                    return True
                    
                # 尝试读取第二帧来判断是否为动图
                try:
                    img.seek(1)
                    return True
                except EOFError:
                    return False
                finally:
                    img.seek(0)
        except:
            return False
    
    def convert_image(self, source_path, target_format, output_dir=None, animation_handling=0, quality=80):
        """
        转换图片格式并保存
        
        核心转换函数，处理各种格式转换场景，包括动图和静态图。
        
        Args:
            source_path (str): 源文件路径
            target_format (tuple): 目标格式 (格式名称, 扩展名)
            output_dir (str): 输出目录路径，默认为None表示与源文件同目录
            animation_handling (int): 动图处理选项，默认为0(转换为静态图)
            quality (int): 图片质量参数 0-100，默认为80
            
        Returns:
            tuple: (输出路径, 警告信息)
                - 输出路径为None表示转换失败
                - 警告信息描述特殊处理情况
        """
        try:
            # 处理输出目录
            if not output_dir:
                output_dir = os.path.dirname(source_path)
            
            # 创建输出目录（如果不存在）
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出路径
            filename = os.path.splitext(os.path.basename(source_path))[0]
            output_path = os.path.join(output_dir, f"{filename}{target_format[1]}")
            
            # 处理文件名冲突
            if not self.overwrite:
                counter = 1
                while os.path.exists(output_path):
                    output_path = os.path.join(output_dir, f"{filename}_{counter}{target_format[1]}")
                    counter += 1
            
            # 打开源图像
            with Image.open(source_path) as img:
                # 保留EXIF信息
                original_info = img.info.copy() if self.preserve_exif else {}
                
                # 设置保存参数（包含质量参数）
                # 过滤掉值为None的参数，避免保存时出错
                save_params = {}
                
                # 对于不同格式，采用不同的参数策略
                if target_format[0] == 'JPEG':
                    # JPEG格式只需要质量参数
                    if quality is not None:
                        save_params['quality'] = quality
                    # JPEG不需要保留某些PNG特有的参数
                elif target_format[0] == 'PNG':
                    # PNG格式使用压缩级别而不是质量参数
                    if quality is not None:
                        # 将质量百分比(0-100)映射到压缩级别(0-9)
                        compression_level = 9 - int(quality / 100 * 9)
                        save_params['compress_level'] = compression_level
                elif target_format[0] in ['WEBP', 'HEIF']:
                    # WEBP和HEIF格式的质量参数设置
                    if quality is not None:
                        save_params['quality'] = quality
                else:
                    # 其他格式保留原始信息（过滤掉None值）
                    if original_info is not None:
                        save_params = {k: v for k, v in original_info.items() if v is not None}
                
                # 检查是否为动图
                is_animated = self.is_animated_image(source_path)
                
                # 处理动图转换
                if is_animated:
                    # 如果目标格式支持动画
                    if target_format[0] in ANIMATED_FORMATS:
                        # 根据animation_handling参数决定如何处理
                        if animation_handling == 0:  # 转换为静态图（只保存第一帧）
                            img.seek(0)
                            img.save(output_path, format=target_format[0], **save_params)
                            return output_path, f"动图已转换为静态图（保存第一帧）"
                        elif animation_handling == 1:  # 保存所有帧为单独文件
                            frame_dir = os.path.join(output_dir, f"{filename}_frames")
                            os.makedirs(frame_dir, exist_ok=True)
                            
                            for frame in range(img.n_frames):
                                img.seek(frame)
                                frame_path = os.path.join(frame_dir, f"{filename}_frame{frame}{target_format[1]}")
                                img.save(frame_path, format=target_format[0], **save_params)
                            
                            return frame_dir, f"动图已拆分为 {img.n_frames} 个静态帧"
                        elif animation_handling == 2:  # 跳过动图
                            return None, "动图已跳过（用户选择跳过）"
                        else:  # 默认保持动画格式
                            # 重新打开图像以确保从第一帧开始处理
                            with Image.open(source_path) as animated_img:
                                success = self.handle_animated_conversion(animated_img, output_path, target_format, save_params)
                                if not success:
                                    return None, "动图转换失败"
                            return output_path, None
                    
                    # 目标格式不支持动画的处理方式
                    if animation_handling == 0:  # 转换为静态图（只保存第一帧）
                        img.seek(0)
                        # 特殊处理JPEG格式（不支持透明度和动画）
                        if target_format[0] == 'JPEG':
                            # 处理P模式到JPEG的转换
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            # 处理RGBA/LA到RGB的转换（JPEG不支持透明度）
                            if img.mode in ('RGBA', 'LA'):
                                # 创建白色背景
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'RGBA':
                                    background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                                else:
                                    background.paste(img)
                                img = background
                            elif img.mode != 'RGB':
                                # 确保JPEG图像为RGB模式
                                img = img.convert('RGB')
                        img.save(output_path, format=target_format[0], **save_params)
                        return output_path, f"动图已转换为静态图（保存第一帧）"
                    
                    elif animation_handling == 1:  # 保存所有帧为单独文件
                        frame_dir = os.path.join(output_dir, f"{filename}_frames")
                        os.makedirs(frame_dir, exist_ok=True)
                        
                        for frame in range(img.n_frames):
                            img.seek(frame)
                            # 特殊处理JPEG格式（不支持透明度和动画）
                            frame_img = img.copy()
                            if target_format[0] == 'JPEG':
                                # 处理P模式到JPEG的转换
                                if frame_img.mode == 'P':
                                    frame_img = frame_img.convert('RGBA')
                                # 处理RGBA/LA到RGB的转换（JPEG不支持透明度）
                                if frame_img.mode in ('RGBA', 'LA'):
                                    # 创建白色背景
                                    background = Image.new('RGB', frame_img.size, (255, 255, 255))
                                    if frame_img.mode == 'RGBA':
                                        background.paste(frame_img, mask=frame_img.split()[-1])  # 使用alpha通道作为mask
                                    else:
                                        background.paste(frame_img)
                                    frame_img = background
                                elif frame_img.mode != 'RGB':
                                    # 确保JPEG图像为RGB模式
                                    frame_img = frame_img.convert('RGB')
                            frame_path = os.path.join(frame_dir, f"{filename}_frame{frame}{target_format[1]}")
                            frame_img.save(frame_path, format=target_format[0], **save_params)
                        
                        return frame_dir, f"动图已拆分为 {img.n_frames} 个静态帧"
                    
                    elif animation_handling == 2:  # 跳过动图
                        return None, "动图已跳过（目标格式不支持动画）"
                    
                    else:  # 默认处理方式
                        img.seek(0)
                        # 特殊处理JPEG格式（不支持透明度和动画）
                        if target_format[0] == 'JPEG':
                            # 处理P模式到JPEG的转换
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            # 处理RGBA/LA到RGB的转换（JPEG不支持透明度）
                            if img.mode in ('RGBA', 'LA'):
                                # 创建白色背景
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'RGBA':
                                    background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                                else:
                                    background.paste(img)
                                img = background
                            elif img.mode != 'RGB':
                                # 确保JPEG图像为RGB模式
                                img = img.convert('RGB')
                        img.save(output_path, format=target_format[0], **save_params)
                        return output_path, f"动图已转换为静态图（保存第一帧）"
                
                # 静态图像处理
                # 特殊处理RGBA到JPEG的转换（JPEG不支持透明度）
                if target_format[0] == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
                    # 创建白色背景
                    if img.mode == 'P':
                        # 处理调色板模式
                        img = img.convert('RGBA')
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                    else:
                        background.paste(img)
                    img = background
                elif target_format[0] == 'JPEG' and img.mode != 'RGB':
                    # 确保JPEG图像为RGB模式
                    img = img.convert('RGB')
                
                img.save(output_path, format=target_format[0], **save_params)
                return output_path, None
        
        except Exception as e:
            return None, f"转换失败: {str(e)}"
    
    def handle_animated_conversion(self, img, output_path, target_format, save_params):
        """
        处理动图转换（优化性能和动画保存）
        
        高效处理动图转换，确保动画信息正确保存，并优化性能减少卡顿。
        改进了错误处理和内存管理，添加了取消检查点。
        
        Args:
            img (PIL.Image): PIL图像对象
            output_path (str): 输出文件路径
            target_format (tuple): 目标格式
            save_params (dict): 保存参数
            
        Returns:
            bool: 转换是否成功
        """
        try:
            # 初始化帧数据存储
            frames = []        # 存储所有帧
            durations = []     # 存储每帧持续时间
            loop = 0           # 循环次数
            disposal_methods = []  # 帧处置方法
            
            # 添加TIFF格式支持
            is_tiff = img.format == 'TIFF'
            
            # 提取所有帧数据 - 简化处理逻辑以提高性能
            for frame in range(img.n_frames):
                # 检查是否已取消转换任务
                if hasattr(self, 'canceled') and self.canceled:
                    return False
                    
                img.seek(frame)
                
                # 直接转换并保存帧，避免复杂的透明度处理
                try:
                    # 简单地转换为RGBA模式，让PIL自动处理透明度
                    frame_copy = img.copy()
                    # 特别处理P模式图像
                    if frame_copy.mode == 'P':
                        frame_copy = frame_copy.convert('RGBA')
                    else:
                        frame_copy = frame_copy.convert('RGBA')
                    frames.append(frame_copy)
                except Exception as e:
                    # 使用错误信号而不是print
                    error_msg = f"处理帧 {frame} 时出错: {str(e)}"
                    self.file_error.emit(output_path, error_msg)
                    # 如果转换失败，尝试使用更基本的方法
                    frame_copy = Image.new('RGBA', img.size)
                    frame_copy.paste(img.copy())
                    frames.append(frame_copy)
                
                # 获取帧持续时间（毫秒）
                duration = img.info.get('duration', 100)
                durations.append(duration)
                
                # 获取循环次数（支持不同格式的循环参数）
                if 'loop' in img.info:
                    loop = img.info['loop']
                elif 'n_loops' in img.info:  # WEBP格式可能使用n_loops
                    loop = img.info['n_loops']
                    
                # 获取帧的处置方法
                disposal = img.info.get('disposal', 0)
                disposal_methods.append(disposal)
            
            # 确保至少有两帧才能形成动画
            if len(frames) < 2:
                self.file_error.emit(output_path, "警告: 动图只有一帧，无法形成动画效果")
                return False
            
            # 为不同格式设置正确的保存参数
            # 特殊处理JPEG格式（不支持透明度和动画）
            if target_format[0] == 'JPEG':
                # JPEG不支持动画，只保存第一帧并处理透明度
                first_frame = frames[0] if frames else None
                if first_frame:
                    # 处理RGBA到RGB的转换（JPEG不支持透明度）
                    if first_frame.mode in ('RGBA', 'LA'):
                        # 创建白色背景
                        background = Image.new('RGB', first_frame.size, (255, 255, 255))
                        if first_frame.mode == 'RGBA':
                            background.paste(first_frame, mask=first_frame.split()[-1])  # 使用alpha通道作为mask
                        else:
                            background.paste(first_frame)
                        first_frame = background
                    elif first_frame.mode == 'P':
                        # 处理调色板模式
                        first_frame = first_frame.convert('RGB')
                    
                    # JPEG格式保存参数
                    jpeg_save_params = {
                        'format': 'JPEG',
                    }
                    
                    # 合并用户指定的保存参数（但排除会引起冲突的参数）
                    conflict_params = ['background', 'transparency', 'loop', 'duration', 'disposal', 'format', 'save_all', 'append_images']
                    jpeg_params = {k: v for k, v in save_params.items() if k not in conflict_params}
                    jpeg_save_params.update(jpeg_params)
                    
                    first_frame.save(output_path, **jpeg_save_params)
                    return True
                else:
                    return False
            elif target_format[0] == 'GIF':
                # 处理GIF格式 - 确保没有残影
                # 为每一帧创建干净的背景，避免帧累积
                processed_frames = []
                for i, frame in enumerate(frames):
                    # 检查是否已取消转换任务
                    if hasattr(self, 'canceled') and self.canceled:
                        return False
                        
                    # 创建新的空白帧作为基础
                    clean_frame = Image.new('RGBA', frame.size, (0, 0, 0, 0))
                    # 将当前帧绘制到空白帧上
                    clean_frame.paste(frame, (0, 0), frame)
                    processed_frames.append(clean_frame)
                
                # GIF格式保存参数
                animated_save_params = {
                    'format': 'GIF',
                    'save_all': True,
                    'append_images': processed_frames[1:],
                    'duration': durations,
                    'loop': loop if loop is not None else 0,
                    'disposal': 2,  # 使用2表示每一帧后恢复背景色
                    'transparency': 0,
                    'optimize': False  # 禁用优化以确保动画正确
                }
                
                # 为GIF优化 - 使用统一调色板但避免过度处理
                try:
                    # 简单转换为P模式
                    for i in range(len(processed_frames)):
                        processed_frames[i] = processed_frames[i].convert('P', palette=Image.ADAPTIVE, colors=256)
                except Exception as e:
                    error_msg = f"GIF调色板处理失败: {str(e)}"
                    self.file_error.emit(output_path, error_msg)
                    # 失败时保持RGBA模式
                    
                frames_to_save = processed_frames
                    
            elif target_format[0] == 'WEBP':
                # 为WEBP统一处理逻辑，与GIF格式保持一致
                processed_frames = []
                for i, frame in enumerate(frames):
                    # 检查是否已取消转换任务
                    if hasattr(self, 'canceled') and self.canceled:
                        return False
                        
                    # 创建新的空白帧作为基础
                    clean_frame = Image.new('RGBA', frame.size, (0, 0, 0, 0))
                    # 将当前帧绘制到空白帧上
                    clean_frame.paste(frame, (0, 0), frame)
                    processed_frames.append(clean_frame)
                
                # WEBP格式保存参数
                animated_save_params = {
                    'format': 'WEBP',
                    'save_all': True,
                    'append_images': processed_frames[1:],
                    'duration': durations,
                    'loop': loop if loop is not None else 0,
                    'method': 0,  # 使用最简单的压缩方法
                    'quality': save_params.get('quality', 80),  # 使用用户指定的质量
                    'lossless': False
                }
                
                # 确保WEBP使用RGBA模式
                for i in range(len(processed_frames)):
                    processed_frames[i] = processed_frames[i].convert('RGBA')
                
                frames_to_save = processed_frames
            
            elif target_format[0] == 'TIFF':
                # 添加对TIFF多页格式的支持 - 不限制输入格式
                processed_frames = []
                for i, frame in enumerate(frames):
                    # 检查是否已取消转换任务
                    if hasattr(self, 'canceled') and self.canceled:
                        return False
                        
                    # TIFF格式可以直接保存RGBA图像
                    processed_frames.append(frame.copy())
                
                # TIFF格式保存参数
                animated_save_params = {
                    'format': 'TIFF',
                    'save_all': True,
                    'append_images': processed_frames[1:],
                    'compression': 'None'  # 使用无压缩以确保兼容性
                }
                
                # 合并TIFF特有参数
                if 'compression' in img.info and img.info['compression'] != 'None':
                    try:
                        animated_save_params['compression'] = img.info['compression']
                    except:
                        # 如果压缩类型不支持，保持无压缩
                        pass
                
                frames_to_save = processed_frames
            
            elif target_format[0] == 'HEIF':
                # 添加对HEIF格式的支持
                processed_frames = []
                for i, frame in enumerate(frames):
                    # 检查是否已取消转换任务
                    if hasattr(self, 'canceled') and self.canceled:
                        return False
                        
                    # HEIF格式可以直接保存RGBA图像
                    processed_frames.append(frame.copy())
                
                # HEIF格式保存参数
                animated_save_params = {
                    'format': 'HEIF',
                    'save_all': True,
                    'append_images': processed_frames[1:],
                    'quality': save_params.get('quality', 80)
                }
                
                frames_to_save = processed_frames
            
            # 清理可能引起冲突的参数
            conflict_params = ['background', 'transparency', 'loop', 'duration', 'disposal', 'format', 'save_all', 'append_images']
            for param in conflict_params:
                if param in save_params:
                    del save_params[param]
                
            # 合并用户指定的保存参数
            animated_save_params.update(save_params)
            
            # 检查是否已取消转换任务
            if hasattr(self, 'canceled') and self.canceled:
                return False
                
            # 直接保存动图
            frames_to_save[0].save(output_path, **animated_save_params)
            
            # 验证保存结果
            try:
                with Image.open(output_path) as saved_img:
                    if hasattr(saved_img, 'is_animated') and saved_img.is_animated:
                        # 使用progress_updated信号而不是print
                        self.progress_updated.emit(0, f"成功保存动画: {os.path.basename(output_path)}, 帧数: {saved_img.n_frames}")
                        return True
                    elif saved_img.format == 'TIFF' and hasattr(saved_img, 'n_frames') and saved_img.n_frames > 1:
                        # TIFF格式特殊验证
                        self.progress_updated.emit(0, f"成功保存TIFF多页图像: {os.path.basename(output_path)}, 页数: {saved_img.n_frames}")
                        return True
                    else:
                        warning_msg = f"保存的文件可能不是动画: {os.path.basename(output_path)}"
                        self.file_error.emit(output_path, warning_msg)
                        # 尝试使用备用方法保存
                        return self._fallback_animated_save(frames, durations, loop, output_path, target_format[0])
            except Exception as e:
                error_msg = f"无法验证保存的文件: {os.path.basename(output_path)}, 错误: {str(e)}"
                self.file_error.emit(output_path, error_msg)
                # 尝试备用保存方法
                return self._fallback_animated_save(frames, durations, loop, output_path, target_format[0])
                
        except Exception as e:
            # 使用更具体的异常捕获，并通过信号报告错误
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            error_msg = f"动图转换错误: {str(e)}"
            self.file_error.emit(output_path, error_msg)
            return False
    
    def _fallback_animated_save(self, frames, durations, loop, output_path, format_name):
        """
        备用的动图保存方法
        
        当主要保存方法失败时，使用更简单的参数尝试保存。
        改进了错误处理，添加了取消检查点。
        
        Args:
            frames: 帧列表
            durations: 持续时间列表
            loop: 循环次数
            output_path: 输出路径
            format_name: 格式名称
            
        Returns:
            bool: 是否成功
        """
        try:
            # 使用progress_updated信号而不是print
            self.progress_updated.emit(0, f"尝试使用备用方法保存{format_name}动画...")
            
            # 创建干净的帧集合
            clean_frames = []
            for i, frame in enumerate(frames):
                # 检查是否已取消转换任务
                if hasattr(self, 'canceled') and self.canceled:
                    return False
                    
                clean_frame = Image.new('RGBA', frame.size, (0, 0, 0, 0))
                clean_frame.paste(frame, (0, 0), frame)
                clean_frames.append(clean_frame)
            
            # 使用最基本的保存参数
            if format_name == 'GIF':
                # 为GIF转换为P模式
                for i in range(len(clean_frames)):
                    clean_frames[i] = clean_frames[i].convert('P', palette=Image.ADAPTIVE)
                
                clean_frames[0].save(
                    output_path,
                    format='GIF',
                    save_all=True,
                    append_images=clean_frames[1:],
                    duration=durations,
                    loop=0,  # 强制无限循环
                    disposal=2,  # 确保没有残影
                    optimize=False
                )
            elif format_name == 'TIFF':
                # 添加对TIFF格式的备用保存支持
                clean_frames[0].save(
                    output_path,
                    format='TIFF',
                    save_all=True,
                    append_images=clean_frames[1:]
                )
            elif format_name == 'HEIF':
                # 添加对HEIF格式的备用保存支持
                clean_frames[0].save(
                    output_path,
                    format='HEIF',
                    save_all=True,
                    append_images=clean_frames[1:],
                    quality=80
                )
            else:  # WEBP
                # 直接保存为RGBA模式的WEBP
                clean_frames[0].save(
                    output_path,
                    format='WEBP',
                    save_all=True,
                    append_images=clean_frames[1:],
                    duration=durations,
                    loop=0,  # 强制无限循环
                    method=0,
                    quality=80,
                    lossless=False
                )
            
            # 再次验证
            with Image.open(output_path) as saved_img:
                if hasattr(saved_img, 'is_animated') and saved_img.is_animated:
                    self.progress_updated.emit(0, f"备用方法成功保存动画: {os.path.basename(output_path)}, 帧数: {saved_img.n_frames}")
                    return True
                elif saved_img.format == 'TIFF' and hasattr(saved_img, 'n_frames') and saved_img.n_frames > 1:
                    # TIFF格式特殊验证
                    self.progress_updated.emit(0, f"备用方法成功保存TIFF多页图像: {os.path.basename(output_path)}, 页数: {saved_img.n_frames}")
                    return True
                else:
                    self.file_error.emit(output_path, "备用方法也失败: 保存的文件不是动图或多页图像")
                    return False
                    
        except Exception as e:
            # 使用更具体的异常捕获，并通过信号报告错误
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            self.file_error.emit(output_path, f"备用保存方法失败: {str(e)}")
            return False
    
    def cancel(self):
        """
        取消转换任务
        
        设置取消标志，使正在进行的转换任务能够及时停止。
        增强了取消机制，确保线程能够正确响应取消请求。
        """
        self.canceled = True
        # 发送取消通知信号
        self.progress_updated.emit(0, "转换任务正在取消...")
