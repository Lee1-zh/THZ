# -*- coding: utf-8 -*-
from PySide6.QtGui import (QImage, QPixmap)
import numpy as np
import cv2
import json
from pathlib import Path
from typing import Dict, Any

from C import DISPLAY_SIZE, FRAME_HEIGHT, FRAME_WIDTH, LOG_ERROR, LOG_INFO

class ImageProcessor:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        # ==================== 新增：初始化高级处理器 ====================
        self.advanced_processor = AdvancedImageProcessor(log_callback)
        # ==================== 新增结束 ====================

    COLORMAP_MAP = {
        "AUTUMN": cv2.COLORMAP_AUTUMN,
        "BONE": cv2.COLORMAP_BONE,
        "COOL": cv2.COLORMAP_COOL,
        "DEEPGREEN": cv2.COLORMAP_DEEPGREEN,
        "HOT": cv2.COLORMAP_HOT,
        "HSV": cv2.COLORMAP_HSV,
        "INFERNO": cv2.COLORMAP_INFERNO,
        "JET": cv2.COLORMAP_JET,
        "MAGMA": cv2.COLORMAP_MAGMA,
        "OCEAN": cv2.COLORMAP_OCEAN,
        "PARULA": cv2.COLORMAP_PARULA,
        "PINK": cv2.COLORMAP_PINK,
        "PLASMA": cv2.COLORMAP_PLASMA,
        "RAINBOW": cv2.COLORMAP_RAINBOW,
        "SPRING": cv2.COLORMAP_SPRING,
        "SUMMER": cv2.COLORMAP_SUMMER,
        "TURBO": cv2.COLORMAP_TURBO,
        "TWILIGHT": cv2.COLORMAP_TWILIGHT,
        "TWILIGHT_SHIFTED": cv2.COLORMAP_TWILIGHT_SHIFTED,
        "VIRIDIS": cv2.COLORMAP_VIRIDIS,
        "WINTER": cv2.COLORMAP_WINTER
    }
    INTERPOLATION_MAP = {
        "最近邻": cv2.INTER_NEAREST,
        "双线性": cv2.INTER_LINEAR,
        "双三次": cv2.INTER_CUBIC,
        "Lanczos": cv2.INTER_LANCZOS4
    }
    EDGE_DETECTION_MAP = {
        "无": None,
        "Canny": "canny",
        "Sobel": "sobel",
        "Laplacian": "laplacian"
    }

    @staticmethod
    def numpy_to_qpixmap(img_array: np.ndarray) -> QPixmap:
        return QPixmap.fromImage(
            QImage(img_array.data, img_array.shape[1], img_array.shape[0],
                   3 * img_array.shape[1], QImage.Format_RGB888).rgbSwapped()
        )

    @staticmethod
    def resize_image(data: np.ndarray, interpolation: int = cv2.INTER_CUBIC,
                     original_size: tuple = None) -> np.ndarray:
        """不插值（保持原大小）"""
        if original_size is None:
            original_size = (DISPLAY_SIZE, DISPLAY_SIZE)

        if interpolation is None:  # 无插值
            return data
        return cv2.resize(data, original_size, interpolation=interpolation)

    @staticmethod
    def adjust_gamma(image: np.ndarray, gamma: float) -> np.ndarray:
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)

    @staticmethod
    def sharpen_image(image: np.ndarray, amount: float) -> np.ndarray:
        if amount <= 0:
            return image
        blur = cv2.GaussianBlur(image, (0, 0), 3)
        sharpened = cv2.addWeighted(image, 1.0 + amount, blur, -amount, 0)
        return sharpened

    @staticmethod
    def apply_edge_detection(image: np.ndarray, method: str, low_threshold: int = 50,
                             high_threshold: int = 150) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if method == "canny":
            edges = cv2.Canny(gray, low_threshold, high_threshold)
            return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        elif method == "sobel":
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            sobel = cv2.magnitude(sobelx, sobely)
            sobel = np.uint8(np.clip(sobel, 0, 255))
            return cv2.cvtColor(sobel, cv2.COLOR_GRAY2BGR)
        elif method == "laplacian":
            laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
            laplacian = np.uint8(np.clip(np.abs(laplacian), 0, 255))
            return cv2.cvtColor(laplacian, cv2.COLOR_GRAY2BGR)
        return image

    def process_image(self, data: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        img = data.copy()
        # 差分处理优先执行
        diff_mode = params.get('diff_mode', '关闭')
        if diff_mode == '打开':
            if params.get('ref_frame') is not None:
                img = cv2.absdiff(img, params['ref_frame'])
        elif diff_mode == '校准文件':
            calibration_path = params.get('calibration_file_path')
            if calibration_path and Path(calibration_path).exists():
                try:
                    with open(calibration_path, 'r', encoding='utf-8') as f:
                        calib_data = json.load(f)
                        calib_frame = np.array(calib_data['average_data'], dtype=np.uint8)
                        calib_frame = calib_frame.reshape((FRAME_HEIGHT, FRAME_WIDTH))
                        img = cv2.absdiff(img, calib_frame)
                except Exception as e:
                    # 如果校准文件加载失败，回退到"打开"模式
                    if params.get('ref_frame') is not None:
                        img = cv2.absdiff(img, params['ref_frame'])
                    if self.log_callback:
                        self.log_callback("校准", f"校准文件加载失败: {e}", LOG_ERROR)
            else:
                # 如果没有校准文件，回退到"打开"模式
                if params.get('ref_frame') is not None:
                    img = cv2.absdiff(img, params['ref_frame'])
                if self.log_callback:
                    self.log_callback("校准", "未找到校准文件，已回退到打开模式", LOG_INFO)
        if params.get('use_median'):
            img = cv2.medianBlur(img, 3)
        if blur_sigma := params.get('gaussian_blur'):
            if blur_sigma > 0:
                img = cv2.GaussianBlur(img, (0, 0), blur_sigma)
        if bilateral_d := params.get('bilateral_filter'):
            if bilateral_d > 0:
                img = cv2.bilateralFilter(img, bilateral_d, 75, 75)
        contrast = params.get('contrast', 1.0)
        brightness = params.get('brightness', 0)
        img = np.clip(img.astype(float) * contrast + brightness, 0, 255).astype(np.uint8)
        if gamma := params.get('gamma'):
            if abs(gamma - 1.0) > 0.01:
                img = self.adjust_gamma(img, gamma)
        if sharpen := params.get('sharpen'):
            if sharpen > 0:
                img = self.sharpen_image(img, sharpen)
        if colormap := params.get('colormap'):
            img = cv2.applyColorMap(img, self.COLORMAP_MAP.get(colormap, cv2.COLORMAP_JET))
        if edge_method := params.get('edge_detection'):
            if edge_method != "无":
                img = self.apply_edge_detection(img, edge_method)
        # 处理插值方法
        interpolation_text = params.get('interpolation', "双三次")
        if interpolation_text == "无":
            interpolation = None
        else:
            interpolation = self.INTERPOLATION_MAP.get(interpolation_text, cv2.INTER_CUBIC)
        img = self.resize_image(img, interpolation=interpolation)

        # ==================== 新增：高级处理 ====================
        if params.get('advanced_enable', False):
            img = self.advanced_processor.process(img)
        # ==================== 新增结束 ====================

        return img

# ==================== 高级图像处理器类 ====================
class AdvancedImageProcessor:
    """
    高级图像处理器 - 用户自定义处理模块
    处理顺序：所有基础处理后执行

    输入要求：
    - np.ndarray, shape (H, W, 3), dtype=np.uint8, BGR格式彩色图像

    输出要求：
    - np.ndarray, shape (H, W, 3), dtype=np.uint8, BGR格式彩色图像
    - 必须保持与输入相同的尺寸和数据格式

    兼容性：
    - 必须支持任意图像尺寸（64x64, 512x512等）
    - 处理失败时应原样返回输入图像
    """

    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def process(self, image: np.ndarray) -> np.ndarray:
        """
        高级处理接口
        """
        try:
            if image is None or not isinstance(image, np.ndarray):
                return image
            # ==================== 用户自定义代码区域 ====================
            # ==================== 用户自定义代码区域 ====================

            # 默认：+1 返回
            processed = image+1

            # ==================== 用户自定义代码结束 ====================
            # ==================== 用户自定义代码结束 ====================
            return processed

        except Exception as e:
            # 错误处理：日志记录并返回原始图像
            if self.log_callback:
                self.log_callback("高级处理", f"处理失败: {e}", LOG_ERROR)
            return image