# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QApplication)
from PySide6.QtCore import (Qt)
from PySide6.QtGui import (QPixmap, QPainter, QIcon, QFont)
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import re
# -------------------- 常量 --------------------
FRAME_WIDTH = 64
FRAME_HEIGHT = 64
DISPLAY_SIZE = 512
TCP_TIMEOUT_MS = 7000
MAX_RECORDED_FRAMES = 99
DEFAULT_FRAME_COUNT = 60
CONTROL_BAR_HEIGHT = 70
FADE_DURATION = 5
AUTO_CONNECT_DELAY_MS = 100
LISTEN_PORT = 50000
LOGO_PATH = r"C:\logo.png"
LOG_DEBUG, LOG_INFO, LOG_WARNING, LOG_ERROR = 0, 1, 2, 3
LOG_CONFIG = (2, 2, 2, 2)
LOG_LEVEL_MAP = {
    LOG_DEBUG: ("DEBUG", "#808080"),
    LOG_INFO: ("INFO", "#0066cc"),
    LOG_WARNING: ("WARNING", "#ff9800"),
    LOG_ERROR: ("ERROR", "#f44336")
}
# 坐标维度常量
COORD_DIMENSION = 12  # 12维坐标 (x,y,z,roll,pitch,yaw,vx,vy,vz,vroll,vpitch,vyaw)
# 会话文件常量
SESSION_PARAMS_FILE = "processing_params.json"
# -------------------- 自动切换阈值常量 --------------------
AUTO_SWITCH_THRESHOLD_MS = 100.0
FPS_DIFF_THRESHOLD = 5.0

def create_icon(text: str, color):
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setFont(QFont("Segoe UI Emoji", 10))
    painter.setPen(color)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)

# ------------辅助函数---------------
def sanitize_path(path: str) -> str:
    return re.sub(r'[<>"|?*\x00-\x1F]', '_', path)

def create_session_folder(coords: np.ndarray, base_path: Path, params: Dict[str, Any]) -> Path:
    """创建会话文件夹，返回完整路径"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    coords_clean = "nocoords"
    if coords is not None and len(coords) >= 4:
        try:
            x, y, z = coords[0], coords[1], coords[2]
            coords_clean = f"x{x:.1f}_y{y:.1f}_z{z:.1f}"
        except Exception:
            pass
    folder_name = f"{coords_clean}_{timestamp}"
    session_path = base_path / folder_name
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path

def create_save_session_folder(coords: np.ndarray, base_path: Path) -> Path:
    """创建保存会话时的文件夹，包含第一帧坐标信息"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    coords_str = "nocoords"
    if coords is not None and len(coords) >= 3:
        try:
            x, y, z = coords[0], coords[1], coords[2]
            coords_str = f"x{x:.1f}_y{y:.1f}_z{z:.1f}"
        except Exception:
            pass
    folder_name = f"session_{coords_str}-{timestamp}"
    session_path = base_path / folder_name
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path

def _get_button_style():
    palette = QApplication.palette()
    highlight_color = palette.highlight().color().name()
    return f"""
        QPushButton {{ font-size: 14px; font-weight: bold; padding: 8px 12px; background-color: #f5f5f5; color: #333333; border: 1px solid #d0d0d0; border-radius: 4px; }}
        QPushButton:hover {{ background-color: #e0e0e0; border-color: #999999; }}
        QPushButton:checked {{ background-color: {highlight_color}; color: white; border-color: {highlight_color}; }}
        QPushButton:checked:hover {{ background-color: {highlight_color}; border-color: {highlight_color}; opacity: 0.9; }}
        QPushButton:pressed {{ padding: 9px 11px 7px 13px; }}
        QPushButton:disabled {{ background-color: #e0e0e0; color: #999999; border-color: #d0d0d0; }}
    """

def _get_slider_style():
    palette = QApplication.palette()
    highlight_color = palette.highlight().color().name()
    return f"""
        QSlider {{ height: 20px; background: transparent; }}
        QSlider::groove:horizontal {{ height: 6px; background: #e0d0d0; border-radius: 3px; }}
        QSlider::handle:horizontal {{ width: 16px; height: 16px; background: #ffffff; border: 1px solid #cccccc; border-radius: 8px; margin: -5px 0; }}
        QSlider::handle:horizontal:hover {{ background: #f0f0f0; border-color: #999999; }}
        QSlider::sub-page:horizontal {{ background: {highlight_color}; border-radius: 3px; }}
    """

def _get_groupbox_style():
    return """
        QGroupBox {
            font-weight: bold;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #333333;
        }
    """

def _get_lineedit_style():
    return """
        QLineEdit { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; background: #ffffff; }
        QLineEdit:focus { border-color: #4d90fe; }
    """

def _get_textedit_style():
    return """
        QTextEdit { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; background: #ffffff; font-size: 12px; }
        QTextEdit:focus { border-color: #4d90fe; }
    """

def _get_spinbox_style():
    return """
        QSpinBox { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; background: #ffffff; }
    """

def _get_combobox_style():
    return """
        QComboBox { 
            padding: 6px; 
            border: 1px solid #d0d0d0; 
            border-radius: 4px; 
            background: #ffffff; 
            min-width: 120px;
            color: #333333;
        }
        QComboBox:focus { 
            border-color: #4d90fe; 
        }
        QComboBox::drop-down { 
            border: none; 
            padding-right: 4px; 
        }
        /* 下拉箭头图标 */
        QComboBox::down-arrow {
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iIzY2NjY2NiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+Cg==);
            width: 12px;
            height: 8px;
        }
        /* 下拉列表容器 - 添加半透明效果 */
        QComboBox QAbstractItemView {
            background-color: rgba(255, 255, 255, 0.95);  /* 95%不透明度的白色背景 */
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 2px;
            selection-background-color: #4d90fe;
            selection-color: #ffffff;
            outline: none;  /* 移除选中时的虚线框 */
        }
        /* 每个选项的样式 */
        QComboBox QAbstractItemView::item {
            padding: 8px 12px;
            border-radius: 3px;
            color: #333333;
            background-color: transparent;
            min-height: 32px;
        }
        /* 鼠标悬停时的样式 - 使用半透明背景 */
        QComboBox QAbstractItemView::item:hover {
            background-color: rgba(77, 144, 254, 0.15);  /* 15%不透明度的蓝色 */
            color: #333333;
        }
        /* 选中项的样式 */
        QComboBox QAbstractItemView::item:selected {
            background-color: #4d90fe;
            color: #ffffff;
        }
        /* 禁用状态的样式 */
        QComboBox:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
    """



def create_circle_icon(color):
    """创建圆形图标"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    return QIcon(pixmap)

def create_square_icon(color):
    """创建方形停止图标"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawRect(2, 2, 12, 12)
    painter.end()
    return QIcon(pixmap)