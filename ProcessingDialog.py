# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QSlider, QCheckBox, QComboBox, QDialog, QSizeGrip)
from PySide6.QtCore import (Qt)

from C import _get_combobox_style, _get_slider_style, _get_groupbox_style
from ImageProcessor import ImageProcessor

class ProcessingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setMinimumWidth(64)
        self.size_grip = QSizeGrip(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        # 图像处理组
        processing_group = QGroupBox("🎨 图像处理")
        processing_layout = QVBoxLayout()
        processing_layout.setSpacing(8)
        # ========== 差分模式==========
        processing_layout.addWidget(QLabel("差分模式:"))
        self.diff_combo = QComboBox()
        diff_items = ["关闭", "打开", "校准文件"]
        self.diff_combo.addItems(diff_items)
        self.diff_combo.setCurrentText("校准文件")
        self.diff_combo.setStyleSheet(_get_combobox_style())
        processing_layout.addWidget(self.diff_combo)
        # 插值方法
        processing_layout.addWidget(QLabel("插值方法:"))
        self.interpolation_combo = QComboBox()
        interpolation_items = ["无"] + list(ImageProcessor.INTERPOLATION_MAP.keys())
        self.interpolation_combo.addItems(interpolation_items)
        self.interpolation_combo.setCurrentText("无")
        self.interpolation_combo.setStyleSheet(_get_combobox_style())
        processing_layout.addWidget(self.interpolation_combo)
        # 对比度
        self.contrast_slider = QSlider(Qt.Horizontal, minimum=10, maximum=300, value=100)
        self.contrast_slider.setStyleSheet(_get_slider_style())
        self.contrast_value_label = QLabel("1.0x")
        processing_layout.addLayout(
            self._create_slider_layout("对比度:", self.contrast_slider, self.contrast_value_label))
        # 亮度
        self.brightness_slider = QSlider(Qt.Horizontal, minimum=-100, maximum=100, value=0)
        self.brightness_slider.setStyleSheet(_get_slider_style())
        self.brightness_value_label = QLabel("0")
        processing_layout.addLayout(
            self._create_slider_layout("亮度:", self.brightness_slider, self.brightness_value_label))
        processing_layout.addWidget(QLabel("伪彩色:"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(list(ImageProcessor.COLORMAP_MAP.keys()))
        self.colormap_combo.setCurrentText("JET")
        self.colormap_combo.setStyleSheet(_get_combobox_style())
        processing_layout.addWidget(self.colormap_combo)
        # Gamma校正
        self.gamma_slider = QSlider(Qt.Horizontal, minimum=10, maximum=300, value=100)
        self.gamma_slider.setStyleSheet(_get_slider_style())
        self.gamma_value_label = QLabel("1.0")
        processing_layout.addLayout(self._create_slider_layout("Gamma校正:", self.gamma_slider, self.gamma_value_label))
        # 锐化强度
        self.sharpen_slider = QSlider(Qt.Horizontal, minimum=0, maximum=50, value=0)
        self.sharpen_slider.setStyleSheet(_get_slider_style())
        self.sharpen_value_label = QLabel("0.0")
        processing_layout.addLayout(
            self._create_slider_layout("锐化强度:", self.sharpen_slider, self.sharpen_value_label))
        # 高斯模糊
        self.gaussian_blur_slider = QSlider(Qt.Horizontal, minimum=0, maximum=100, value=0)
        self.gaussian_blur_slider.setStyleSheet(_get_slider_style())
        self.gaussian_blur_value_label = QLabel("0.0")
        processing_layout.addLayout(
            self._create_slider_layout("高斯模糊:", self.gaussian_blur_slider, self.gaussian_blur_value_label))
        # 双边滤波
        self.bilateral_filter_slider = QSlider(Qt.Horizontal, minimum=0, maximum=15, value=0)
        self.bilateral_filter_slider.setStyleSheet(_get_slider_style())
        self.bilateral_filter_value_label = QLabel("0")
        processing_layout.addLayout(
            self._create_slider_layout("双边滤波:", self.bilateral_filter_slider, self.bilateral_filter_value_label))
        # 中值滤波
        median_layout = QHBoxLayout()
        median_layout.addWidget(QLabel("中值滤波:"))
        median_layout.addStretch()
        self.median_check = QCheckBox()
        self.median_check.setChecked(True)
        median_layout.addWidget(self.median_check)
        processing_layout.addLayout(median_layout)
        processing_layout.addWidget(QLabel("边缘检测:"))
        self.edge_detection_combo = QComboBox()
        self.edge_detection_combo.addItems(list(ImageProcessor.EDGE_DETECTION_MAP.keys()))
        self.edge_detection_combo.setCurrentText("无")
        self.edge_detection_combo.setStyleSheet(_get_combobox_style())
        processing_layout.addWidget(self.edge_detection_combo)
        # 累积帧数
        self.accumulate_slider = QSlider(Qt.Horizontal, minimum=1, maximum=144, value=1)
        self.accumulate_slider.setStyleSheet(_get_slider_style())
        self.accumulate_value_label = QLabel("1")
        processing_layout.addLayout(
            self._create_slider_layout("累积帧数:", self.accumulate_slider, self.accumulate_value_label))
        processing_layout.addStretch()
        processing_group.setLayout(processing_layout)
        processing_group.setStyleSheet(_get_groupbox_style())
        layout.addWidget(processing_group)

        # ==================== 高级处理组 ====================
        advanced_group = QGroupBox("🔧 高级处理")
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(8)

        # 启用开关
        enable_layout = QHBoxLayout()
        enable_layout.addWidget(QLabel("启用高级处理:"))
        enable_layout.addStretch()
        self.advanced_enable_check = QCheckBox()
        self.advanced_enable_check.setChecked(False)  # 默认不勾选
        enable_layout.addWidget(self.advanced_enable_check)
        advanced_layout.addLayout(enable_layout)
        advanced_layout.addStretch()
        advanced_group.setLayout(advanced_layout)
        advanced_group.setStyleSheet(_get_groupbox_style())
        layout.addWidget(advanced_group)
        # ==================== 新增结束 ====================

        layout.addStretch()
        # 添加大小调整手柄到右下角
        size_grip_layout = QHBoxLayout()
        size_grip_layout.addStretch()
        size_grip_layout.addWidget(self.size_grip)
        layout.addLayout(size_grip_layout)

    def _create_slider_layout(self, label_text: str, slider: QSlider, label: QLabel):
        layout = QVBoxLayout()
        layout.setSpacing(3)
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(label_text))
        header_layout.addStretch()
        header_layout.addWidget(label)
        layout.addLayout(header_layout)
        layout.addWidget(slider)
        return layout