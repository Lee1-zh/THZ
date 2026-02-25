# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QTextEdit,
                               QFileDialog, QStatusBar, QToolButton, QLabel, QSizePolicy)
from PySide6.QtCore import (Qt, QTimer, Slot, QSettings, QByteArray)
from PySide6.QtGui import (QAction, QKeySequence, QCloseEvent, QTextCursor, QColor, QPixmap)
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import ipaddress
from typing import Optional, List, Dict, Any
import time
import gc
import psutil

from C import sanitize_path, LOG_ERROR, LOG_INFO, COORD_DIMENSION, DISPLAY_SIZE, AUTO_CONNECT_DELAY_MS, \
    _get_groupbox_style, create_circle_icon, _get_button_style, LOG_LEVEL_MAP, \
    create_square_icon, AUTO_SWITCH_THRESHOLD_MS, \
    FPS_DIFF_THRESHOLD, DEFAULT_FRAME_COUNT, LISTEN_PORT, LOG_WARNING, LOG_DEBUG, LOG_CONFIG
from ConnectionDialog import ConnectionDialog
from CoorDroneWidget import DroneWidget, CoordinatePredictor
from FrameBuffer import FrameBuffer
from HelpDialog import HelpDialog
from ImageProcessor import ImageProcessor
from OperationManualDialog import OperationManualDialog
from PlaybackController import PlaybackController
from ProcessingDialog import ProcessingDialog
from ScalableImageLabel import ScalableImageLabel
from SessionManager import SessionManager
from TcpServer import TcpServer
from DataSaver import DataSaver


# -------------------- 主窗口 --------------------
class TerahertzDetectorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("T-Waves Inspector™ - 风电叶片太赫兹智能检测系统 v1.0.0")
        self.tcp_server = TcpServer(log_callback=self._log)
        self.image_processor = ImageProcessor(log_callback=self._log)
        # ========== 第1步：先创建settings ==========
        self.settings = QSettings("T-Waves", "THZDetector")
        # ========== 第2步：初始化其他组件 ==========
        # 初始化对话框
        self.frame_buffer = FrameBuffer()
        self.data_saver: Optional[DataSaver] = None
        self.session_manager = SessionManager(self)  # 新增：会话管理器
        # 当前帧
        self.current_frame: Optional[np.ndarray] = None
        self.recorded_frames: List[np.ndarray] = []
        self.is_recording = False
        self.reference_frame_for_playback: Optional[np.ndarray] = None
        self.is_playback_mode = False
        # 坐标相关
        self.current_coordinate = np.zeros(COORD_DIMENSION)
        self.push_fps = 30.0  # 推送端FPS
        # 用于检测坐标重复
        self.last_received_coord = np.zeros(6)
        self.coord_repeat_count = 0
        self.session_started = False
        self.waiting_for_first_coordinate = False
        self.first_frame_data = None
        # ========== 创建带回调的卡尔曼滤波器 ==========
        initial_fps = self.settings.value("processing/initial_fps", 30.0, type=float)
        self.coordinate_predictor = CoordinatePredictor(initial_fps=initial_fps)
        self.coordinate_predictor.log_callback = lambda msg: self._log("滤波", msg, LOG_INFO)
        # 会话创建标志位
        self.first_frame_received = False
        self.pending_session_start = False
        self.pending_session_params = None
        # 移除：自动重连相关定时器
        # 标记是否为手动断开
        self.is_manual_disconnect = False
        # 自动重连相关
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_real_fps)
        self.fps_cnt = 0
        self.t_start = 0
        # 新增：连接质量相关
        self._current_delay_ms = 0.0  # 当前TCP延迟（毫秒）
        self._measured_fps = 0.0  # 实际测量的FPS
        # 新增：校准模式相关
        self.is_calibration_mode = False
        self.calibration_file_path = None
        # ==================== 第3步：创建对话框（传入self引用） ====================
        self.connection_dialog = ConnectionDialog(self, main_window=self)
        self.processing_dialog = ProcessingDialog(self)
        # ==================== 初始化操作说明和帮助对话框 ====================
        self.operation_manual_dialog = OperationManualDialog(self)
        self.help_dialog = HelpDialog(self)
        self._setup_ui()
        self._setup_menu()
        self._setup_status()
        self._connect_signals()
        self.load_settings()
        self.playback_controller = PlaybackController(self.image_label, self.drone_widget, self)
        # 新增：软件启动时自动点击监听（延迟执行，确保UI完全初始化）
        QTimer.singleShot(AUTO_CONNECT_DELAY_MS, self._auto_start_listening)
        # 连接对话框信号
        self.connection_dialog.browse_btn.clicked.connect(self.on_browse_path)
        self.processing_dialog.interpolation_combo.currentTextChanged.connect(self.update_image_display)
        self.processing_dialog.contrast_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.brightness_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.colormap_combo.currentTextChanged.connect(self.update_image_display)
        self.processing_dialog.gamma_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.sharpen_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.gaussian_blur_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.bilateral_filter_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.median_check.stateChanged.connect(self.update_image_display)
        self.processing_dialog.edge_detection_combo.currentTextChanged.connect(self.update_image_display)
        self.processing_dialog.diff_combo.currentTextChanged.connect(self.update_image_display)
        self.processing_dialog.accumulate_slider.valueChanged.connect(self.update_image_display)
        self.processing_dialog.advanced_enable_check.stateChanged.connect(self.update_image_display)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 左打开按钮
        self.left_open_btn = QToolButton()
        # 从配置加载箭头状态，默认向右（对话框关闭）
        left_arrow_default = Qt.ArrowType(self.settings.value("ui/left_btn_arrow", Qt.RightArrow))
        self.left_open_btn.setArrowType(left_arrow_default)
        self.left_open_btn.setFixedWidth(15)
        self.left_open_btn.setFixedHeight(300)
        self.left_open_btn.setStyleSheet("""
            QToolButton {
                background-color: #f5f5f5;
                border: none;
                border-right: 1px solid #d0d0d0;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.left_open_btn.clicked.connect(self._toggle_connection_dialog)
        main_layout.addWidget(self.left_open_btn, 0, Qt.AlignBottom)
        # 中间内容区域
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(12)
        center_layout.setContentsMargins(0, 0, 0, 0)
        # 上半部分：只有图像显示
        self.display_group = self._create_group("🖼️ 实时成像显示", self._display_layout, QSizePolicy.Expanding,
                                                QSizePolicy.Expanding)
        center_layout.addWidget(self.display_group)
        # 下半部分：采集控制与状态（包含无人机动画）
        self.control_group = self._create_group("🎛️ 采集控制与状态", self._control_layout, QSizePolicy.Expanding,
                                                QSizePolicy.Preferred)
        self.control_group.setMinimumWidth(512)  # 设置最小宽度512
        center_layout.addWidget(self.control_group)
        main_layout.addWidget(center_widget, 1)
        # 右打开按钮
        self.right_open_btn = QToolButton()
        # 从配置加载箭头状态，默认向左（对话框关闭）
        right_arrow_default = Qt.ArrowType(self.settings.value("ui/right_btn_arrow", Qt.LeftArrow))
        self.right_open_btn.setArrowType(right_arrow_default)
        self.right_open_btn.setFixedWidth(15)
        self.right_open_btn.setFixedHeight(300)
        self.right_open_btn.setStyleSheet("""
            QToolButton {
                background-color: #f5f5f5;
                border: none;
                border-left: 1px solid #d0d0d0;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.right_open_btn.clicked.connect(self._toggle_processing_dialog)
        main_layout.addWidget(self.right_open_btn, 0, Qt.AlignBottom)

    def _create_group(self, title: str, layout_func, h_policy=QSizePolicy.Preferred, v_policy=QSizePolicy.Expanding):
        group = QGroupBox(title)
        group.setSizePolicy(h_policy, v_policy)
        group.setLayout(layout_func())
        group.setStyleSheet(_get_groupbox_style())
        return group

    def _toggle_connection_dialog(self):
        """切换连接对话框"""
        if self.connection_dialog.isVisible():
            self.connection_dialog.hide()
            self.left_open_btn.setArrowType(Qt.LeftArrow)
            self.settings.setValue("ui/left_btn_arrow", Qt.LeftArrow)
        else:
            self._position_dialog(self.connection_dialog, "left")  # 先定位
            self.connection_dialog.show()  # 再显示
            self.connection_dialog.raise_()
            self.connection_dialog.activateWindow()
            self.left_open_btn.setArrowType(Qt.RightArrow)
            self.settings.setValue("ui/left_btn_arrow", Qt.RightArrow)

    def _toggle_processing_dialog(self):
        """切换处理对话框"""
        if self.processing_dialog.isVisible():
            self.processing_dialog.hide()
            self.right_open_btn.setArrowType(Qt.RightArrow)
            self.settings.setValue("ui/right_btn_arrow", Qt.RightArrow)
        else:
            self._position_dialog(self.processing_dialog, "right")  # 先定位
            self.processing_dialog.show()  # 再显示
            self.processing_dialog.raise_()
            self.connection_dialog.activateWindow()
            self.right_open_btn.setArrowType(Qt.LeftArrow)
            self.settings.setValue("ui/right_btn_arrow", Qt.LeftArrow)

    def _position_dialog(self, dialog, side):
        """定位对话框到主窗口左右两侧，上边对齐图像显示区域"""
        # 确保对话框已显示且宽度有效
        if not dialog.isVisible():
            dialog.show()  # 先显示以获取正确尺寸
        main_rect = self.geometry()
        # 获取显示区域在屏幕中的位置
        display_global_pos = self.display_group.mapToGlobal(self.display_group.pos())
        display_top = display_global_pos.y()
        # 获取对话框的实际宽度
        dialog_width = dialog.width()
        if dialog_width <= 0:
            dialog_width = 128  # 设置一个合理的默认宽度
        # 微小间隔
        margin = 2
        # 计算x位置
        if side == "left":
            x = main_rect.x() - dialog_width - margin
        else:  # right
            x = main_rect.x() + main_rect.width() + margin
        # y位置对齐显示区域顶部
        y = display_top
        # 设置对话框位置（高度自适应，不手动设置）
        dialog.move(x, y)

    def resizeEvent(self, event):
        """主窗口大小改变时，重新定位对话框"""
        super().resizeEvent(event)
        # 重新定位对话框
        if self.connection_dialog.isVisible():
            self._position_dialog(self.connection_dialog, "left")
        if self.processing_dialog.isVisible():
            self._position_dialog(self.processing_dialog, "right")

    def moveEvent(self, event):
        """主窗口移动时，重新定位对话框"""
        super().moveEvent(event)
        if self.connection_dialog.isVisible():
            self._position_dialog(self.connection_dialog, "left")
        if self.processing_dialog.isVisible():
            self._position_dialog(self.processing_dialog, "right")

    def _display_layout(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.image_label = ScalableImageLabel()
        self.image_label.setText("<span style='color:#999999; font-size:14px;'>等待采集...</span>")
        layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        return layout

    def _control_layout(self):
        """集成无人机动画的控制布局"""
        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)
        # 左侧：控制按钮和状态信息（垂直对齐）
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        # =============== 第一列：开始采集按钮 ===============
        # 开始采集按钮
        self.record_btn = QPushButton(" 开始采集")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(115, 52)
        self.record_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
        self.record_btn.clicked.connect(self.on_record_clicked)
        self.record_btn.setStyleSheet(_get_button_style())
        left_layout.addWidget(self.record_btn)
        # 采集状态（对齐开始采集按钮）
        self.record_status_label = QLabel("○ 待机")
        self.record_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        # 添加左边距使文本与按钮文字对齐
        status_margin = QHBoxLayout()
        status_margin.addSpacing(10)  # 根据按钮内边距调整
        status_margin.addWidget(self.record_status_label)
        status_margin.addStretch()
        left_layout.addLayout(status_margin)
        # 帧计数（对齐开始采集按钮）
        frame_count_layout = QHBoxLayout()
        frame_count_layout.addSpacing(10)  # 与采集状态保持一致
        frame_count_layout.addWidget(QLabel("帧计数:"))
        self.frame_counter_label = QLabel("0/0")
        self.frame_counter_label.setStyleSheet("font-weight: bold; color: #333333;")
        frame_count_layout.addWidget(self.frame_counter_label)
        frame_count_layout.addStretch()
        left_layout.addLayout(frame_count_layout)
        # 添加伸缩空间填充剩余区域
        left_layout.addStretch()
        # =============== 第二列：监听按钮及状态 ===============
        right_control_layout = QVBoxLayout()
        right_control_layout.setSpacing(8)
        # 监听按钮
        self.connect_btn = QPushButton(" 开始监听")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setFixedSize(100, 52)
        self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.connect_btn.setStyleSheet(_get_button_style())
        right_control_layout.addWidget(self.connect_btn)
        # 监听状态（对齐监听按钮）
        self.status_label = QLabel("○ 未监听")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        # 添加左边距使文本与按钮文字对齐
        status_margin2 = QHBoxLayout()
        status_margin2.addSpacing(10)  # 根据按钮内边距调整
        status_margin2.addWidget(self.status_label)
        status_margin2.addStretch()
        right_control_layout.addLayout(status_margin2)
        # FPS+延迟（对齐监听按钮）
        fps_layout = QHBoxLayout()
        fps_layout.addSpacing(10)  # 与监听状态保持一致
        self.current_fps_label = QLabel("0fps 0ms")
        self.current_fps_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        fps_layout.addWidget(self.current_fps_label)
        fps_layout.addStretch()
        right_control_layout.addLayout(fps_layout)
        # 添加伸缩空间填充剩余区域
        right_control_layout.addStretch()
        # =============== 将两列添加到主布局 ===============
        control_buttons_layout = QHBoxLayout()
        control_buttons_layout.addLayout(left_layout)
        control_buttons_layout.addLayout(right_control_layout)
        control_buttons_layout.addStretch()  # 填充中间空隙
        main_layout.addLayout(control_buttons_layout, 1)  # 控制区域占1份
        # 右侧：无人机动画（增大占比）
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        # 创建水平布局，包含状态标签和无人机动画（紧贴着）
        drone_layout = QHBoxLayout()
        drone_layout.setSpacing(0)  # 间距设为0，实现紧贴
        drone_layout.setContentsMargins(0, 0, 0, 0)
        # 无人机状态标签（垂直，背景透明）
        self.drone_status_label = QLabel("🚁\n无\n人\n机\n实\n时\n状\n态")
        self.drone_status_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #00ff00;
                font-family: monospace;
                font-size: 10px;
                padding: 4px;
                border-radius: 3px;
            }
        """)
        self.drone_status_label.setAlignment(Qt.AlignCenter)
        self.drone_status_label.setWordWrap(True)
        self.drone_status_label.setFixedWidth(20)
        self.drone_status_label.setMinimumHeight(110)  # 高度改为110
        # 无人机动画控件
        self.drone_widget = DroneWidget()
        self.drone_widget.setMinimumSize(220, 110)  # 高度改为110
        # 添加到布局（标签在左，动画在右，紧贴）
        drone_layout.addWidget(self.drone_status_label)
        drone_layout.addWidget(self.drone_widget, 1)  # 伸缩因子让无人机控件占满剩余空间
        right_layout.addLayout(drone_layout)
        main_layout.addLayout(right_layout, 2)  # 无人机动画占2份
        return main_layout

    def _toggle_kalman_mode(self, checked):
        """切换卡尔曼滤波器FPS模式"""
        mode = checked
        self.coordinate_predictor.set_fps(self.push_fps, use_fixed=mode)
        mode_str = "理论时序" if mode else "测量时序"
        self.connection_dialog.kalman_mode_btn.setText(mode_str)  # 更新对话框按钮
        self._log("设置", f"卡尔曼滤波器模式切换为: {mode_str}", LOG_INFO)
        self.settings.setValue("processing/kalman_fixed_mode", mode)

    def _toggle_auto_switch(self, checked):
        """切换自动模式"""
        status = "开启" if checked else "关闭"
        self._log("设置", f"卡尔曼滤波器自动切换模式 {status}", LOG_INFO)
        self.settings.setValue("processing/kalman_auto_switch", checked)

    def _toggle_calibration_mode(self, checked):
        """切换校准模式"""
        self.is_calibration_mode = checked
        status = "开启" if checked else "关闭"
        self._log("校准", f"校准模式 {status}", LOG_INFO)
        self.settings.setValue("calibration_mode", checked)
        # 更新按钮文本
        if checked:
            self.record_btn.setText(" 开始校准")
        else:
            self.record_btn.setText(" 开始采集")

    def _setup_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background-color: #f5f5f5; border-bottom: 1px solid #d0d0d0; }
            QMenuBar::item { padding: 6px 12px; background-color: transparent; }
            QMenuBar::item:selected { background-color: #e0e0e0; }
            QMenu { background-color: #ffffff; border: 1px solid #d0d0d0; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background-color: #4d90fe; color: white; }
        """)
        file_menu = menubar.addMenu("文件")
        # 修改：将"打开图像"改为"打开会话"
        file_menu.addAction(QAction("打开会话", self, shortcut=QKeySequence("Ctrl+O"), triggered=self.on_open_session))
        file_menu.addAction(QAction("保存会话", self, shortcut=QKeySequence("Ctrl+S"), triggered=self.on_save_session))
        file_menu.addSeparator()
        file_menu.addAction(QAction("重启", self, shortcut=QKeySequence("Ctrl+R"), triggered=self.restart_application))
        file_menu.addAction(QAction("退出", self, shortcut=QKeySequence("Ctrl+Q"), triggered=self.close))
        settings_menu = menubar.addMenu("设置")
        # 移除主题风格和快捷键，改为恢复默认、加载配置、导出配置
        settings_menu.addAction(
            QAction("恢复默认", self, shortcut=QKeySequence("Ctrl+D"), triggered=self.on_restore_defaults))
        settings_menu.addAction(
            QAction("加载配置", self, shortcut=QKeySequence("Ctrl+L"), triggered=self.on_load_config))
        settings_menu.addAction(
            QAction("导出配置", self, shortcut=QKeySequence("Ctrl+E"), triggered=self.on_export_config))
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction(QAction("操作说明", self, shortcut=QKeySequence("F1"), triggered=self.on_user_manual))
        help_menu.addAction(QAction("关于与支持", self, shortcut=QKeySequence("F2"), triggered=self.on_help_dialog))

    def _setup_status(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar { background-color: #f5f5f5; border-top: 1px solid #d0d0d0; }
        """)
        # 日志部件 - 移除最大高度限制，允许自动扩展
        self.log_widget = QTextEdit(readOnly=True)
        self.log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_widget.setStyleSheet("""
            QTextEdit { background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px; font-family: monospace; font-size: 12px; }
        """)
        # 自动滚动到最底部
        self.log_scroll_timer = QTimer(self)
        self.log_scroll_timer.timeout.connect(self._scroll_log_to_bottom)
        self.log_scroll_timer.start(100)  # 每100ms检查一次
        self.status_bar.addPermanentWidget(self.log_widget, 1)
        self.setStatusBar(self.status_bar)

    def _scroll_log_to_bottom(self):
        """智能自动滚动：仅在用户处于底部时保持自动滚动"""
        vertical_scroll_bar = self.log_widget.verticalScrollBar()
        if vertical_scroll_bar:
            # 检查是否已经在底部（或接近底部，20像素容忍值）
            # 如果用户手动滚动到上方，则暂停自动滚动
            current_value = vertical_scroll_bar.value()
            max_value = vertical_scroll_bar.maximum()
            # 只有在接近底部时才自动滚动
            if max_value - current_value <= 7:
                vertical_scroll_bar.setValue(max_value)

    def _connect_signals(self):
        self.tcp_server.dataReceived.connect(self._handle_frame)
        self.tcp_server.coordinateReceived.connect(self._handle_coordinate)
        self.tcp_server.connectionChanged.connect(self.on_connection_changed)
        self.tcp_server.connectionError.connect(self.on_connection_error)
        # 新增：连接质量信号
        self.tcp_server.connectionQuality.connect(self._update_connection_quality)

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 延迟恢复对话框状态，确保主窗口已完全显示
        QTimer.singleShot(100, self._restore_dialog_visibility)

    def _restore_dialog_visibility(self):
        """恢复对话框可见性"""
        try:
            # 恢复大小
            if geom := self.settings.value("window/connection_dialog_geometry"):
                self.connection_dialog.restoreGeometry(geom)
            if geom := self.settings.value("window/processing_dialog_geometry"):
                self.processing_dialog.restoreGeometry(geom)
            # 恢复可见性（默认为打开）
            if self.settings.value("window/connection_dialog_visible", True, type=bool):
                self._toggle_connection_dialog()
            if self.settings.value("window/processing_dialog_visible", True, type=bool):
                self._toggle_processing_dialog()
            # 恢复操作说明和帮助对话框可见性（默认为关闭）
            if self.settings.value("window/operation_manual_dialog_visible", False, type=bool):
                self.operation_manual_dialog.show()
            if self.settings.value("window/help_dialog_visible", False, type=bool):
                self.help_dialog.show()
        except Exception as e:
            self._log("设置", f"恢复对话框状态失败: {e}", LOG_ERROR)

    def load_settings(self):
        try:
            if ip := self.settings.value("connection/ip"):
                self.connection_dialog.ip_edit.setText(ip)
            if port := self.settings.value("connection/data_port"):
                self.connection_dialog.port_edit.setText(port)
            if frame_count := self.settings.value("acquisition/frame_count", type=int):
                self.connection_dialog.frame_count_spin.setValue(frame_count)
            if save_path := self.settings.value("acquisition/save_path"):
                self.connection_dialog.path_edit.setText(save_path)
            self.connection_dialog.auto_save_check.setChecked(
                self.settings.value("acquisition/auto_save", True, type=bool))
            # 移除：恢复自动重启监听设置
            # 恢复校准模式
            self.is_calibration_mode = self.settings.value("calibration_mode", False, type=bool)
            self.connection_dialog.calibration_mode_check.setChecked(self.is_calibration_mode)
            self._toggle_calibration_mode(self.is_calibration_mode)
            if interpolation := self.settings.value("processing/interpolation"):
                self.processing_dialog.interpolation_combo.setCurrentText(interpolation)
            else:
                self.processing_dialog.interpolation_combo.setCurrentText("无")  # 默认无插值
            if contrast := self.settings.value("processing/contrast", type=int):
                self.processing_dialog.contrast_slider.setValue(contrast)
            if brightness := self.settings.value("processing/brightness", type=int):
                self.processing_dialog.brightness_slider.setValue(brightness)
            if colormap := self.settings.value("processing/colormap"):
                self.processing_dialog.colormap_combo.setCurrentText(colormap)
            if gamma := self.settings.value("processing/gamma", type=int):
                self.processing_dialog.gamma_slider.setValue(gamma)
            if sharpen := self.settings.value("processing/sharpen", type=int):
                self.processing_dialog.sharpen_slider.setValue(sharpen)
            if gaussian_blur := self.settings.value("processing/gaussian_blur", type=int):
                self.processing_dialog.gaussian_blur_slider.setValue(gaussian_blur)
            if bilateral_filter := self.settings.value("processing/bilateral_filter", type=int):
                self.processing_dialog.bilateral_filter_slider.setValue(bilateral_filter)
            self.processing_dialog.median_check.setChecked(self.settings.value("processing/median", True, type=bool))
            if edge_detection := self.settings.value("processing/edge_detection"):
                self.processing_dialog.edge_detection_combo.setCurrentText(edge_detection)
            # 差分模式
            diff_mode = self.settings.value("processing/diff_mode", "校准文件")
            self.processing_dialog.diff_combo.setCurrentText(diff_mode)
            if accumulate := self.settings.value("processing/accumulate", type=int):
                self.processing_dialog.accumulate_slider.setValue(accumulate)
            if geometry := self.settings.value("window/geometry"):
                self.restoreGeometry(geometry)
            if state := self.settings.value("window/state"):
                if not isinstance(state, QByteArray):
                    state = QByteArray(state)
                self.restoreState(state)
            # 恢复卡尔曼滤波器模式
            kalman_mode = self.settings.value("processing/kalman_fixed_mode", True, type=bool)
            self.connection_dialog.kalman_mode_btn.setChecked(kalman_mode)  # 更新对话框按钮
            self.coordinate_predictor.use_fixed_fps = kalman_mode
            # 恢复自动切换状态（默认为关闭）
            auto_switch = self.settings.value("processing/kalman_auto_switch", False, type=bool)
            self.connection_dialog.auto_switch_check.setChecked(auto_switch)
            # 恢复按钮箭头状态
            left_arrow = Qt.ArrowType(self.settings.value("ui/left_btn_arrow", Qt.RightArrow))
            self.left_open_btn.setArrowType(left_arrow)
            right_arrow = Qt.ArrowType(self.settings.value("ui/right_btn_arrow", Qt.LeftArrow))
            self.right_open_btn.setArrowType(right_arrow)
            if initial_fps := self.settings.value("processing/initial_fps", type=float):
                self.coordinate_predictor.set_fps(initial_fps)
            self._update_all_value_labels()
            self.update_image_display()
            self._log("设置", "所有配置已加载", LOG_INFO)

            # ==================== 新增：加载高级处理参数 ====================
            # 高级处理启用状态
            advanced_enabled = self.settings.value("processing/advanced_enable", False, type=bool)
            self.processing_dialog.advanced_enable_check.setChecked(advanced_enabled)
            # ==================== 新增结束 ====================

        except Exception as e:
            self._log("设置", f"加载设置时出错: {e}", LOG_ERROR)

    def save_settings(self):
        try:
            self.settings.setValue("connection/ip", self.connection_dialog.ip_edit.text())
            self.settings.setValue("connection/data_port", self.connection_dialog.port_edit.text())
            # 移除：保存自动重启监听设置
            self.settings.setValue("acquisition/frame_count", self.connection_dialog.frame_count_spin.value())
            self.settings.setValue("acquisition/save_path", self.connection_dialog.path_edit.toPlainText())
            self.settings.setValue("acquisition/auto_save", self.connection_dialog.auto_save_check.isChecked())
            self.settings.setValue("processing/initial_fps", self.coordinate_predictor.current_fps)
            self.settings.setValue("processing/kalman_fixed_mode", self.coordinate_predictor.use_fixed_fps)
            self.settings.setValue("processing/kalman_auto_switch",
                                   self.connection_dialog.auto_switch_check.isChecked())
            self.settings.setValue("processing/interpolation", self.processing_dialog.interpolation_combo.currentText())
            self.settings.setValue("processing/contrast", self.processing_dialog.contrast_slider.value())
            self.settings.setValue("processing/brightness", self.processing_dialog.brightness_slider.value())
            self.settings.setValue("processing/colormap", self.processing_dialog.colormap_combo.currentText())
            self.settings.setValue("processing/gamma", self.processing_dialog.gamma_slider.value())
            self.settings.setValue("processing/sharpen", self.processing_dialog.sharpen_slider.value())
            self.settings.setValue("processing/gaussian_blur", self.processing_dialog.gaussian_blur_slider.value())
            self.settings.setValue("processing/bilateral_filter",
                                   self.processing_dialog.bilateral_filter_slider.value())
            self.settings.setValue("processing/median", self.processing_dialog.median_check.isChecked())
            self.settings.setValue("processing/edge_detection",
                                   self.processing_dialog.edge_detection_combo.currentText())
            # 保存差分模式
            self.settings.setValue("processing/diff_mode", self.processing_dialog.diff_combo.currentText())
            self.settings.setValue("processing/accumulate", self.processing_dialog.accumulate_slider.value())
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.setValue("window/state", self.saveState())
            # 保存对话框大小
            if self.connection_dialog.isVisible():
                self.settings.setValue("window/connection_dialog_geometry", self.connection_dialog.saveGeometry())
            if self.processing_dialog.isVisible():
                self.settings.setValue("window/processing_dialog_geometry", self.processing_dialog.saveGeometry())
            # 保存操作说明和帮助对话框状态
            if self.operation_manual_dialog.isVisible():
                self.settings.setValue("window/operation_manual_dialog_geometry",
                                       self.operation_manual_dialog.saveGeometry())
            if self.help_dialog.isVisible():
                self.settings.setValue("window/help_dialog_geometry", self.help_dialog.saveGeometry())
            self.settings.setValue("window/operation_manual_dialog_visible", self.operation_manual_dialog.isVisible())
            self.settings.setValue("window/help_dialog_visible", self.help_dialog.isVisible())
            # 保存按钮箭头状态
            self.settings.setValue("ui/left_btn_arrow", self.left_open_btn.arrowType())
            self.settings.setValue("ui/right_btn_arrow", self.right_open_btn.arrowType())
            # 保存校准模式
            self.settings.setValue("calibration_mode", self.is_calibration_mode)
            self._log("设置", "所有配置已保存", LOG_INFO)

            # ==================== 新增：保存高级处理参数 ====================
            self.settings.setValue("processing/advanced_enable",
                                   self.processing_dialog.advanced_enable_check.isChecked())
            # ==================== 新增结束 ====================

        except Exception as e:
            self._log("设置", f"保存设置时出错: {e}", LOG_ERROR)

    def _log(self, module: str, message: str, level: int = LOG_INFO):
        """
        统一日志记录方法
        通过全局变量 LOG_CONFIG 控制显示位置
        """
        level_str, color = LOG_LEVEL_MAP[level]
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        log_text = f'[{timestamp}] [{level_str}] {module}: {message}'
        # 获取对应级别的显示配置
        level_display_flag = LOG_CONFIG[level]
        # 控制台输出（后台）
        if level_display_flag in (0, 2):
            print(log_text)
        # 界面显示
        if level_display_flag in (1, 2):
            if hasattr(self, 'log_widget'):
                html = f'<span style="color:{color};">{log_text}</span>'
                self.log_widget.append(html)
        # 文件保存（默认全部保存）
        if self.data_saver and self.data_saver.current_session_path:
            self.data_saver.log(module, message, level)
        # 限制日志条目数（保留最后1000条）
        if hasattr(self, 'log_widget'):
            doc = self.log_widget.document()
            block_count = doc.blockCount()
            if block_count > 1000:
                # 删除超出的块数
                blocks_to_remove = block_count - 1000
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor, blocks_to_remove)
                cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()

    def log(self, module: str, message: str, level: str = "info"):
        level_map = {"info": LOG_INFO, "warning": LOG_WARNING, "error": LOG_ERROR}
        self._log(module, message, level_map.get(level, LOG_INFO))

    # ==================== 新增：软件启动时自动开始监听 ====================
    def _auto_start_listening(self):
        """软件启动时自动开始监听"""
        try:
            self._log("启动", "软件启动，自动开始监听...", LOG_INFO)
            # 设置按钮为选中状态
            self.connect_btn.setChecked(True)
            # 调用开始监听逻辑
            self._do_start_listening()
        except Exception as e:
            self._log("启动", f"自动启动监听失败: {e}", LOG_ERROR)
            # 如果失败，确保按钮状态正确
            self.connect_btn.setChecked(False)
            self.connect_btn.setText(" 开始监听")
            self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))

    @Slot()
    def on_connect_clicked(self):
        if self.connect_btn.isChecked():
            self._do_start_listening()
        else:
            self._do_stop_listening()

    def _do_start_listening(self):
        try:
            ip = self.connection_dialog.ip_edit.text()
            port = int(self.connection_dialog.port_edit.text())
            ipaddress.ip_address(ip)
            if port < 1 or port > 65535:
                raise ValueError("端口号必须在1-65535之间")
            self.is_manual_disconnect = False
            if self.tcp_server.server.isListening():
                self.tcp_server.stop_listening()
            if self.tcp_server.start_listening(ip, port):
                self.connect_btn.setEnabled(True)
                self.connect_btn.setText(" 停止监听")
                self.connect_btn.setIcon(create_square_icon(QColor("#f44336")))  # 方形停止图标
                self._log("监听", f"开始在 {ip}:{port} 监听", LOG_INFO)
            else:
                self.connect_btn.setChecked(False)
                self.connect_btn.setEnabled(True)
                self.connect_btn.setText(" 开始监听")
                self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
                self._log("监听", f"启动监听失败: {self.tcp_server.server.errorString()}", LOG_ERROR)
        except Exception as e:
            self._log("监听", f"参数错误: {e}", LOG_ERROR)
            self.connect_btn.setChecked(False)
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(" 开始监听")
            self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))

    def _do_stop_listening(self):
        self.is_manual_disconnect = True
        self.tcp_server.stop_listening()
        self.connect_btn.setText(" 开始监听")
        self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))  # 圆形开始图标
        # 修复监听状态不同步的问题
        self.status_label.setText("○ 未监听")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self._log("监听", "手动停止监听", LOG_INFO)

    @Slot(bool, str)
    def on_connection_changed(self, connected: bool, heartbeat_status: str = "正常"):
        """更新连接和心跳状态（合并显示）"""
        if connected:
            # 合并心跳状态到监听状态文本
            status_text = f"● 监听中"
            self.status_label.setText(status_text)
            # 根据心跳状态设置颜色
            if heartbeat_status == "正常":
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            elif heartbeat_status == "待机":
                self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
            elif heartbeat_status == "断开":
                self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        else:
            self.status_label.setText("○ 未监听")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

        if not connected:
            self.drone_widget.set_coordinate(np.zeros(COORD_DIMENSION), "", 0.0)
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(" 停止监听" if self.tcp_server.server.isListening() else " 开始监听")
        self.connect_btn.setIcon(
            create_square_icon(QColor("#f44336")) if self.tcp_server.server.isListening() else create_circle_icon(
                QColor("#4CAF50")))

        # 新增：如果正在采集时连接断开，记录状态但不停止采集
        # 当重新连接时，需要重新发送START命令
        if not connected and self.is_recording:
            self._log("采集", "警告：采集过程中连接断开，等待重新连接...", LOG_WARNING)

        # 新增：如果重新连接且正在采集中，自动重新发送START命令
        if connected and self.is_recording and not self.is_manual_disconnect:
            self._log("采集", "连接已恢复，重新发送开始采集命令...", LOG_INFO)
            QTimer.singleShot(500, self._resend_start_command)  # 延迟500ms确保连接稳定

    def _resend_start_command(self):
        """重新发送开始采集命令"""
        if self.tcp_server.client_socket and self.is_recording:
            try:
                self.tcp_server.client_socket.write(b'START')
                self.tcp_server.client_socket.flush()
                self._log("命令", "已重新发送 START", LOG_INFO)
            except Exception as e:
                self._log("命令", f"重新发送 START 失败: {e}", LOG_ERROR)

    @Slot(str)
    def on_connection_error(self, error_msg: str):
        self._log("监听", f"错误: {error_msg}", LOG_ERROR)
        if not self.connect_btn.isEnabled():
            self.connect_btn.setEnabled(True)
            self.connect_btn.setChecked(False)
            self.connect_btn.setText(" 开始监听")
            self.connect_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
            # 修复监听状态不同步的问题
            self.status_label.setText("○ 未监听")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

    # 移除：_trigger_auto_reconnect 方法
    # 移除：_attempt_reconnect 方法
    # 移除：_check_initial_listening 方法

    @Slot()
    def on_browse_path(self):
        current_path = self.connection_dialog.path_edit.toPlainText()
        if not current_path or not Path(current_path).exists():
            current_path = str(Path.cwd())
        if path := QFileDialog.getExistingDirectory(self, "选择存储路径", current_path):
            clean_path = sanitize_path(path)
            self.connection_dialog.path_edit.setText(clean_path)
            self.save_settings()
            self._log("设置", f"存储路径更新为: {clean_path}", LOG_INFO)

    @Slot()
    def on_record_clicked(self):
        # 添加错误处理，确保按钮状态一致性
        try:
            if self.record_btn.isChecked():
                # 发送开始命令
                if self.tcp_server.client_socket:
                    self.tcp_server.client_socket.write(b'START')
                    self.tcp_server.client_socket.flush()
                    self._log("命令", "已发送 START", LOG_INFO)
                # 开始采集
                self.start_recording()
                # 启动FPS计时器
                self.fps_cnt = 0
                self.t_start = time.time()
                self.fps_timer.start(1000)
            else:
                # 发送停止命令
                if self.tcp_server.client_socket:
                    self.tcp_server.client_socket.write(b'STOP')
                    self.tcp_server.client_socket.flush()
                    self._log("命令", "已发送 STOP", LOG_INFO)
                # 停止FPS计时器
                self.fps_timer.stop()
                # 停止采集
                self.stop_recording()
        except Exception as e:
            self._log("采集", f"采集操作失败: {e}", LOG_ERROR)
            # 恢复按钮状态
            self.record_btn.setChecked(False)
            if self.is_calibration_mode:
                self.record_btn.setText(" 开始校准")
            else:
                self.record_btn.setText(" 开始采集")
            self.record_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
            self.record_status_label.setText("○ 待机")
            self.record_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    # ========== 核心修复：在start_recording开头添加自动清理逻辑 ==========
    def start_recording(self):
        """开始采集 - 修复版，确保每次采集前清理内存"""

        # 清空回放控制器的历史数据（防止内存泄漏）
        if hasattr(self, 'playback_controller'):
            if hasattr(self.playback_controller, 'coords'):
                self.playback_controller.coords.clear()
            if hasattr(self.playback_controller, 'fps_values'):
                self.playback_controller.fps_values.clear()

        if not self.connection_dialog.path_edit.toPlainText():
            self._log("采集", "错误：未设置存储路径", LOG_ERROR)
            self.record_btn.setChecked(False)
            return
        clean_path = sanitize_path(self.connection_dialog.path_edit.toPlainText())
        self.connection_dialog.path_edit.setText(clean_path)
        try:
            Path(clean_path).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log("采集", f"无法创建存储目录: {e}", LOG_ERROR)
            self.record_btn.setChecked(False)
            return
        # 清空采集相关的缓冲区（不影响playback_controller中的会话数据）
        self.recorded_frames.clear()
        self.frame_buffer.clear()
        # 清除回放相关数据
        self.reference_frame_for_playback = None
        self.first_frame_data = None
        self.data_saver = None
        self.is_playback_mode = False  # 退出回放模式，进入采集模式
        # 强制垃圾回收（关键：立即释放内存）
        gc.collect()
        # 记录内存状态（调试用）
        self._log_memory("采集开始")
        # 重置状态变量
        self.frame_count = 0
        self.is_recording = True
        self.image_label.set_recording(True)
        # 重置会话标志
        self.session_started = False
        self.waiting_for_first_coordinate = True
        self.recording_start_time = time.time()
        # UI更新
        if self.is_calibration_mode:
            self.record_btn.setText(" 停止校准")
        else:
            self.record_btn.setText(" 停止采集")
        self.record_btn.setIcon(create_square_icon(QColor("#f44336")))
        self.record_status_label.setText("● 采集中")
        self.record_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self._log("采集", "开始采集，等待第一个坐标数据...", LOG_INFO)
        # 初始化帧数显示
        total_frames = self.connection_dialog.frame_count_spin.value()
        self.frame_counter_label.setText(f"0/{total_frames}")

    # ========== 新增：使用给定的坐标创建会话 ==========
    def _create_session_with_coordinate(self, coord: np.ndarray):
        """使用给定的坐标创建会话"""
        # 更新当前坐标（确保使用前6维）
        self.current_coordinate[:6] = coord
        # 创建会话
        if self.connection_dialog.auto_save_check.isChecked():
            clean_path = sanitize_path(self.connection_dialog.path_edit.toPlainText())
            self.data_saver = DataSaver(clean_path)
            # 获取当前处理参数
            processing_params = {
                'diff_mode': self.processing_dialog.diff_combo.currentText(),
                'use_median': self.processing_dialog.median_check.isChecked(),
                'contrast': self.processing_dialog.contrast_slider.value() / 100.0,
                'brightness': self.processing_dialog.brightness_slider.value(),
                'colormap': self.processing_dialog.colormap_combo.currentText(),
                'interpolation': self.processing_dialog.interpolation_combo.currentText(),
                'gamma': self.processing_dialog.gamma_slider.value() / 100.0,
                'sharpen': self.processing_dialog.sharpen_slider.value() / 10.0,
                'gaussian_blur': self.processing_dialog.gaussian_blur_slider.value() / 10.0,
                'bilateral_filter': self.processing_dialog.bilateral_filter_slider.value(),
                'edge_detection': self.processing_dialog.edge_detection_combo.currentText(),
                'accumulate': self.processing_dialog.accumulate_slider.value(),
            }
            self.data_saver.set_processing_params(processing_params)
            if not self.data_saver.start_session(self.current_coordinate, {
                'frame_count': self.connection_dialog.frame_count_spin.value()
            }):
                self._log("采集", "初始化数据保存器失败", LOG_ERROR)
                self.record_btn.setChecked(False)
                self.stop_recording()
                return
        self.session_started = True
        self.waiting_for_first_coordinate = False
        # 处理缓存的第一帧
        if self.first_frame_data is not None:
            self._log("采集",
                      f"收到有效坐标，创建会话并处理第一帧 (坐标: {coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f})",
                      LOG_INFO)
            self._process_cached_first_frame(self.first_frame_data)
            self.first_frame_data = None
        else:
            self._log("采集", f"收到有效坐标，创建会话 (坐标: {coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f})", LOG_INFO)

    # ========== 新增：处理缓存的第一帧数据 ==========
    def _process_cached_first_frame(self, data: np.ndarray):
        """处理缓存的第一帧数据"""
        self.frame_count = 1
        self.current_frame = data
        self.frame_buffer.add_frame(data)
        self.recorded_frames.append(data)
        # 进度更新
        total_frames = self.connection_dialog.frame_count_spin.value()
        self.frame_counter_label.setText(f"{self.frame_count}/{total_frames}")
        self._log("采集", f"已采集帧 {self.frame_count}/{total_frames}", LOG_INFO)
        self.update_image_display()
        self._save_current_frame()

    # ========== 核心修改2：改进stop_recording逻辑 ==========
    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.image_label.set_recording(False)
        self.record_btn.setChecked(False)
        # 在校准模式下，保存校准文件
        if self.is_calibration_mode and self.data_saver and self.recorded_frames:
            clean_path = sanitize_path(self.connection_dialog.path_edit.toPlainText())
            base_path = Path(clean_path)
            self.data_saver.save_calibration_file(self.recorded_frames, base_path)
        if self.data_saver:
            self.data_saver.end_session()
            self.data_saver = None
        self.reference_frame_for_playback = self.frame_buffer.reference_frame
        # 如果采集到了数据，自动加载到回放控制器
        if self.recorded_frames:
            # 将采集的数据加载到回放控制器
            self.playback_controller.set_session_data(
                self.recorded_frames.copy(),
                self.playback_controller.coords,  # 这些是在采集过程中添加的
                self.playback_controller.fps_values  # 这些是在采集过程中添加的
            )
            self._log_memory("采集结束")
            self._log("回放", f"录制完成，共 {len(self.recorded_frames)} 帧，可进行回放", LOG_INFO)
            self.is_playback_mode = True  # 只有采集到数据才进入回放模式
        else:
            # 如果没有采集到数据，恢复之前的回放状态（如果有的话）
            if self.playback_controller.frames:
                self.is_playback_mode = True
                self._log("回放", "采集未完成，恢复之前的会话数据", LOG_INFO)
            else:
                self.is_playback_mode = False
        # 根据校准模式状态设置正确的按钮文本
        if self.is_calibration_mode:
            self.record_btn.setText(" 开始校准")
        else:
            self.record_btn.setText(" 开始采集")
        self.record_btn.setIcon(create_circle_icon(QColor("#4CAF50")))
        self.record_status_label.setText("○ 待机")
        self.record_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    # ========== 核心修改3：改进open_session逻辑 ==========
    @Slot()
    def on_open_session(self):
        """打开会话文件夹"""
        # 如果正在采集，提示用户
        if self.is_recording:
            self._log("会话", "请先停止当前采集，再打开会话", LOG_WARNING)
            return
        session_path = QFileDialog.getExistingDirectory(
            self, "选择会话文件夹",
            self.connection_dialog.path_edit.toPlainText()
        )
        if session_path:
            success = self.session_manager.open_session(Path(session_path))
            if success:
                self.is_playback_mode = True
                # 清除当前采集数据（避免混淆）
                self.recorded_frames.clear()
                self.frame_buffer.clear()

    @Slot(np.ndarray)
    def _handle_frame(self, data: np.ndarray):
        if not self.is_recording:
            return
        self.fps_cnt += 1
        # === 新增：如果正在等待第一个坐标，缓存第一帧 ===
        if self.waiting_for_first_coordinate:
            if self.first_frame_data is None:
                self.first_frame_data = data
                self.frame_buffer.set_reference(data)
                self._log("处理", "第一帧已缓存，等待有效坐标...", LOG_INFO)
            # 不继续处理，等待坐标
            return
        # 正常处理帧
        self.frame_count += 1
        self.current_frame = data
        self.frame_buffer.add_frame(data)
        self.recorded_frames.append(data)
        # 帧数进度更新（每帧都更新）
        total_frames = self.connection_dialog.frame_count_spin.value()
        self.frame_counter_label.setText(f"{self.frame_count}/{total_frames}")
        self._log("采集", f"已采集帧 {self.frame_count}/{total_frames}", LOG_INFO)
        self.update_image_display()
        self._save_current_frame()
        if self.frame_count >= self.connection_dialog.frame_count_spin.value():
            self._log("采集", f"已达到目标帧数 {self.frame_count}，自动停止", LOG_INFO)
            self.record_btn.setChecked(False)
            self.on_record_clicked()
            return

    @Slot(np.ndarray, float, float, str)
    def _handle_coordinate(self, coord: np.ndarray, timestamp: float, fps: float, sender_ip: str):
        """处理接收到的坐标数据"""
        # 保存推送端FPS
        self.push_fps = fps
        self.coordinate_predictor.set_fps(fps)
        # 检测坐标是否重复
        coord_delta = np.abs(coord[:6] - self.last_received_coord)
        is_coord_updated = np.any(coord_delta > 1e-6)
        if not is_coord_updated:
            self.coord_repeat_count += 1
            if self.coord_repeat_count == 1:
                self._log("坐标", f"检测到坐标重复...", LOG_DEBUG)
        else:
            if self.coord_repeat_count > 0:
                self._log("坐标", f"坐标更新恢复，权重恢复正常", LOG_DEBUG)
            self.coord_repeat_count = 0

        self.last_received_coord = coord[:6].copy()
        # 更新卡尔曼滤波器
        self.coordinate_predictor.update(coord[:6], timestamp, is_coord_updated)
        full_state = self.coordinate_predictor.get_current_state()
        self.current_coordinate = full_state
        # 更新无人机3D可视化
        if hasattr(self.drone_widget, 'set_coordinate'):
            self.drone_widget.set_coordinate(self.current_coordinate, sender_ip, self.push_fps)
        # 如果开启了自动切换，根据连接质量和FPS差异决定是否切换模式
        if self.connection_dialog.auto_switch_check.isChecked():
            # 获取实际测量的FPS（基于数据接收间隔）
            if self._measured_fps > 0:
                fps_diff = abs(self._measured_fps - self.push_fps)
                # 判断条件：TCP延迟过高 或 FPS差异过大
                if self._current_delay_ms > AUTO_SWITCH_THRESHOLD_MS or fps_diff > FPS_DIFF_THRESHOLD:
                    # 连接质量差或接收端不稳定，切换到理论时序模式（信任推送端FPS）
                    if not self.coordinate_predictor.use_fixed_fps:
                        self.connection_dialog.kalman_mode_btn.setChecked(True)  # 这会触发_toggle_kalman_mode
                        self._log("自动切换",
                                  f"检测到连接问题（延迟:{self._current_delay_ms:.1f}ms, FPS差异:{fps_diff:.1f}），"
                                  f"切换到理论时序模式", LOG_WARNING)
                else:
                    # 连接质量好，允许使用测量时序模式
                    if self.coordinate_predictor.use_fixed_fps:
                        self.connection_dialog.kalman_mode_btn.setChecked(False)
                        self._log("自动切换",
                                  f"连接质量良好（延迟:{self._current_delay_ms:.1f}ms, FPS差异:{fps_diff:.1f}），"
                                  f"切换到测量时序模式", LOG_INFO)
        # ===== 会话创建逻辑（增加超时保护）=====
        if self.waiting_for_first_coordinate and self.is_recording:
            elapsed = time.time() - self.recording_start_time
            is_timeout = elapsed > 10.0  # 10秒超时阈值
            # 无条件信任第一个坐标并创建会话
            self._create_session_with_coordinate(coord[:6])
            # 日志区分正常创建与超时保护
            if is_timeout:
                self._log("采集", "⚠️ 等待坐标超时保护触发，强制创建会话", LOG_WARNING)
            else:
                self._log("采集", f"收到首帧坐标 {coord[:3]}，创建会话", LOG_INFO)
        # ===== 采集时保存坐标到回放控制器 =====
        if self.is_recording and self.session_started:
            self.playback_controller.coords.append(full_state)
            self.playback_controller.fps_values.append(fps)

    def _update_connection_quality(self, delay_ms: float):
        """更新连接质量显示"""
        self._current_delay_ms = delay_ms

    @Slot()
    def _update_real_fps(self):
        """更新实时FPS和连接质量显示"""
        elapsed = time.time() - self.t_start
        self._measured_fps = self.fps_cnt / elapsed if elapsed > 0 else 0
        # 更新显示格式：xx fps + xx ms
        display_text = f"{self._measured_fps:.1f}fps {self._current_delay_ms:.1f}ms"
        self.current_fps_label.setText(display_text)
        # 重置计数器
        self.fps_cnt = 0
        self.t_start = time.time()

    def _save_current_frame(self):
        """保存当前帧，传递完整坐标数组和推送端FPS"""
        if self.data_saver and self.current_frame is not None:
            try:
                processed = self.process_current_frame()
                # 传递完整的12维坐标数组和推送端FPS
                self.data_saver.save_frame(processed, self.current_frame, self.frame_count,
                                           self.current_coordinate, self.push_fps)
            except Exception as e:
                self._log("保存", f"保存帧失败: {e}", LOG_ERROR)

    @Slot()
    def _update_all_value_labels(self):
        self.processing_dialog.contrast_value_label.setText(
            f"{self.processing_dialog.contrast_slider.value() / 100.0:.1f}x")
        self.processing_dialog.brightness_value_label.setText(str(self.processing_dialog.brightness_slider.value()))
        self.processing_dialog.gamma_value_label.setText(f"{self.processing_dialog.gamma_slider.value() / 100.0:.1f}")
        self.processing_dialog.sharpen_value_label.setText(
            f"{self.processing_dialog.sharpen_slider.value() / 10.0:.1f}")
        self.processing_dialog.gaussian_blur_value_label.setText(
            f"{self.processing_dialog.gaussian_blur_slider.value() / 10.0:.1f}")
        self.processing_dialog.bilateral_filter_value_label.setText(
            str(self.processing_dialog.bilateral_filter_slider.value()))
        self.processing_dialog.accumulate_value_label.setText(str(self.processing_dialog.accumulate_slider.value()))

    def process_current_frame(self) -> np.ndarray:
        """处理当前帧 - 修复校准文件路径问题"""
        if self.current_frame is None:
            return np.zeros((DISPLAY_SIZE, DISPLAY_SIZE, 3), dtype=np.uint8)
        if self.is_recording:
            data = self.frame_buffer.get_accumulated_frame(self.processing_dialog.accumulate_slider.value())
        else:
            accumulate_count = self.processing_dialog.accumulate_slider.value()
            if accumulate_count > 1 and self.recorded_frames:
                current_index = self.playback_controller.current_index
                start_idx = max(0, current_index - accumulate_count + 1)
                frames_to_average = self.recorded_frames[start_idx:current_index + 1]
                if len(frames_to_average) > 0:
                    data = np.mean(frames_to_average, axis=0).astype(np.uint8)
                else:
                    data = self.current_frame
            else:
                data = self.current_frame
        # 获取差分模式
        diff_mode = self.processing_dialog.diff_combo.currentText()
        # 修复：校准文件路径改为保存在当前目录，而不是父目录
        clean_path = sanitize_path(self.connection_dialog.path_edit.toPlainText())
        base_path = Path(clean_path)
        # 修改：直接使用 base_path，而不是 base_path.parent
        self.calibration_file_path = str(base_path / f"{base_path.name}.json")
        processing_params = {
            'diff_mode': diff_mode,
            'calibration_file_path': self.calibration_file_path,
            'ref_frame': self.frame_buffer.reference_frame if self.is_recording else self.reference_frame_for_playback,
            'use_median': self.processing_dialog.median_check.isChecked(),
            'contrast': self.processing_dialog.contrast_slider.value() / 100.0,
            'brightness': self.processing_dialog.brightness_slider.value(),
            'colormap': self.processing_dialog.colormap_combo.currentText(),
            'interpolation': self.processing_dialog.interpolation_combo.currentText(),
            'gamma': self.processing_dialog.gamma_slider.value() / 100.0,
            'sharpen': self.processing_dialog.sharpen_slider.value() / 10.0,
            'gaussian_blur': self.processing_dialog.gaussian_blur_slider.value() / 10.0,
            'bilateral_filter': self.processing_dialog.bilateral_filter_slider.value(),
            'edge_detection': self.processing_dialog.edge_detection_combo.currentText(),

            # ==================== 新增：高级处理参数 ====================
            'advanced_enable': self.processing_dialog.advanced_enable_check.isChecked(),
            # ==================== 新增结束 ====================

        }
        return self.image_processor.process_image(data, processing_params)

    @Slot()
    def update_image_display(self):
        self._update_all_value_labels()
        if self.current_frame is not None:
            pixmap = self.image_processor.numpy_to_qpixmap(self.process_current_frame())
            self.image_label.setPixmap(pixmap)

    @Slot()
    def on_playback_frame(self, frame: np.ndarray):
        self.current_frame = frame
        self.update_image_display()

    # ========== 核心修改4：改进save_session逻辑 ==========
    @Slot()
    def on_save_session(self):
        """保存当前会话（使用第一帧坐标命名）"""
        if not self.recorded_frames:
            self._log("会话", "没有可保存的数据", LOG_WARNING)
            return
        # 如果正在采集，提示用户
        if self.is_recording:
            self._log("会话", "请先停止采集，再保存会话", LOG_WARNING)
            return
        target_path = QFileDialog.getExistingDirectory(
            self, "选择保存位置",
            self.connection_dialog.path_edit.toPlainText()
        )
        if target_path:
            # 获取当前处理参数
            processing_params = {
                'diff_mode': self.processing_dialog.diff_combo.currentText(),
                'use_median': self.processing_dialog.median_check.isChecked(),
                'contrast': self.processing_dialog.contrast_slider.value() / 100.0,
                'brightness': self.processing_dialog.brightness_slider.value(),
                'colormap': self.processing_dialog.colormap_combo.currentText(),
                'interpolation': self.processing_dialog.interpolation_combo.currentText(),
                'gamma': self.processing_dialog.gamma_slider.value() / 100.0,
                'sharpen': self.processing_dialog.sharpen_slider.value() / 10.0,
                'gaussian_blur': self.processing_dialog.gaussian_blur_slider.value() / 10.0,
                'bilateral_filter': self.processing_dialog.bilateral_filter_slider.value(),
                'edge_detection': self.processing_dialog.edge_detection_combo.currentText(),
                'accumulate': self.processing_dialog.accumulate_slider.value(),
            }
            # 获取当前日志
            log_messages = self.data_saver.log_messages if self.data_saver else []
            # 保存会话（使用第一帧坐标命名）
            success = self.session_manager.save_session(
                Path(target_path),
                self.recorded_frames,
                self.playback_controller.coords,
                self.playback_controller.fps_values,
                processing_params,
                log_messages
            )
            if success:
                self._log("会话", "会话保存成功", LOG_INFO)

    @Slot()
    def on_restore_defaults(self):
        """恢复默认设置 - 修复版：确保校准模式默认为关闭"""
        try:
            self.settings.clear()
            self.connection_dialog.ip_edit.setText("0.0.0.0")
            self.connection_dialog.port_edit.setText(str(LISTEN_PORT))
            self.connection_dialog.frame_count_spin.setValue(DEFAULT_FRAME_COUNT)
            self.connection_dialog.path_edit.setText(r"D:\thz_20251127_扬州风场_01号机组_3号叶片")
            self.connection_dialog.auto_save_check.setChecked(True)
            # 移除：恢复自动重启监听设置
            self.processing_dialog.interpolation_combo.setCurrentText("无")  # 默认无插值
            self.processing_dialog.contrast_slider.setValue(100)
            self.processing_dialog.brightness_slider.setValue(0)
            self.processing_dialog.colormap_combo.setCurrentText("JET")
            self.processing_dialog.gamma_slider.setValue(100)
            self.processing_dialog.sharpen_slider.setValue(0)
            self.processing_dialog.gaussian_blur_slider.setValue(0)
            self.processing_dialog.bilateral_filter_slider.setValue(0)
            self.processing_dialog.median_check.setChecked(True)
            self.processing_dialog.edge_detection_combo.setCurrentText("无")
            self.processing_dialog.diff_combo.setCurrentText("校准文件")  # 默认校准文件
            self.processing_dialog.accumulate_slider.setValue(1)
            self.connection_dialog.kalman_mode_btn.setChecked(True)
            self.connection_dialog.auto_switch_check.setChecked(False)  # 恢复默认为关闭
            self.left_open_btn.setArrowType(Qt.RightArrow)
            # 右侧面板默认是关闭的，箭头向左
            self.right_open_btn.setArrowType(Qt.LeftArrow)
            # 打开两个对话框
            self.connection_dialog.show()
            self._position_dialog(self.connection_dialog, "left")
            self.left_open_btn.setArrowType(Qt.RightArrow)  # 打开后箭头向右
            self.processing_dialog.show()
            self._position_dialog(self.processing_dialog, "right")
            self.right_open_btn.setArrowType(Qt.LeftArrow)  # 打开后箭头向左
            self._update_all_value_labels()
            self.update_image_display()
            # 停止所有定时器
            self.fps_timer.stop()
            self.log_scroll_timer.stop()
            # 移除：停止重连定时器
            # 清空所有缓存数据
            self.recorded_frames.clear()
            # 注意：这里不调用playback_controller.clear()，保留会话数据
            self.frame_buffer.clear()
            # 重置坐标和状态
            self.current_coordinate = np.zeros(COORD_DIMENSION)
            self.last_received_coord = np.zeros(6)
            self.coord_repeat_count = 0
            self.session_started = False
            self.waiting_for_first_coordinate = False
            self.first_frame_data = None
            self.reference_frame_for_playback = None
            self.is_playback_mode = False
            # ==================== 关键修复：重置校准模式状态 ====================
            # 显式设置校准模式为关闭状态
            self.is_calibration_mode = False
            self.connection_dialog.calibration_mode_check.setChecked(False)
            self._toggle_calibration_mode(False)
            self.record_btn.setText(" 开始采集")  # 确保按钮文本恢复为"开始采集"
            # 重置数据保存器并清理文件句柄
            if self.data_saver:
                if self.data_saver.current_session_path:
                    self.data_saver.end_session()
                self.data_saver = None
            # 重置卡尔曼滤波器状态
            self.coordinate_predictor.reset()
            # 重置图像显示
            self.current_frame = None
            self.image_label.setText("<span style='color:#999999; font-size:14px;'>等待采集...</span>")
            # 强制垃圾回收（关键：立即释放内存）
            gc.collect()
            # 记录内存状态
            self._log_memory("恢复默认设置")
            # 恢复日志滚动定时器
            self.log_scroll_timer.start(100)
            self._log("设置", "已恢复为默认设置并清理所有资源", LOG_INFO)

            # ==================== 新增：恢复高级处理默认设置 ====================
            self.processing_dialog.advanced_enable_check.setChecked(False)
            # ==================== 新增结束 ====================

        except Exception as e:
            self._log("设置", f"恢复默认设置失败: {e}", LOG_ERROR)

    @Slot()
    def on_load_config(self):
        """加载配置文件 - 使用 JSON 格式"""
        config_path, _ = QFileDialog.getOpenFileName(
            self, "选择配置文件",
            self.connection_dialog.path_edit.toPlainText(),
            "配置文件 (*.json);;所有文件 (*.*)"
        )
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 应用配置到UI
                self._apply_config_to_ui(config)
                self._log("配置", f"配置已加载: {config_path}", LOG_INFO)
            except Exception as e:
                self._log("配置", f"加载配置失败: {e}", LOG_ERROR)

    @Slot()
    def on_export_config(self):
        """导出配置到 JSON 文件"""
        # 修改：默认文件名和扩展名改为 .json
        default_path = self.connection_dialog.path_edit.toPlainText() + "/config.json"
        config_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置",
            default_path,
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if config_path:
            try:
                config = self._get_current_config()
                # 修改：直接保存为 JSON 格式
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                self._log("配置", f"配置已导出: {config_path}", LOG_INFO)
            except Exception as e:
                self._log("配置", f"导出配置失败: {e}", LOG_ERROR)

    def _get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "连接": {
                "IP": self.connection_dialog.ip_edit.text(),
                "端口": self.connection_dialog.port_edit.text(),
                # 移除：自动重启配置
            },
            "采集": {
                "总帧数": self.connection_dialog.frame_count_spin.value(),
                "存储路径": self.connection_dialog.path_edit.toPlainText(),
                "自动保存": self.connection_dialog.auto_save_check.isChecked(),
                "校准模式": self.is_calibration_mode,
            },
            "图像处理": {
                "插值方法": self.processing_dialog.interpolation_combo.currentText(),
                "对比度": self.processing_dialog.contrast_slider.value() / 100.0,
                "亮度": self.processing_dialog.brightness_slider.value(),
                "伪彩色": self.processing_dialog.colormap_combo.currentText(),
                "Gamma": self.processing_dialog.gamma_slider.value() / 100.0,
                "锐化": self.processing_dialog.sharpen_slider.value() / 10.0,
                "高斯模糊": self.processing_dialog.gaussian_blur_slider.value() / 10.0,
                "双边滤波": self.processing_dialog.bilateral_filter_slider.value(),
                "中值滤波": self.processing_dialog.median_check.isChecked(),
                "边缘检测": self.processing_dialog.edge_detection_combo.currentText(),
                "差分模式": self.processing_dialog.diff_combo.currentText(),
                "累积帧数": self.processing_dialog.accumulate_slider.value(),
            },
            "卡尔曼滤波": {
                "模式": "理论时序" if self.coordinate_predictor.use_fixed_fps else "测量时序",
                "自动切换": self.connection_dialog.auto_switch_check.isChecked(),
            }
        }

    def _apply_config_to_ui(self, config: Dict[str, Any]):
        """将配置应用到UI"""
        try:
            # 连接配置
            conn_config = config.get("连接", {})
            if "IP" in conn_config:
                self.connection_dialog.ip_edit.setText(conn_config["IP"])
            if "端口" in conn_config:
                self.connection_dialog.port_edit.setText(str(conn_config["端口"]))
            # 移除：恢复自动重启设置
            # 采集配置
            acq_config = config.get("采集", {})
            if "总帧数" in acq_config:
                self.connection_dialog.frame_count_spin.setValue(acq_config["总帧数"])
            if "存储路径" in acq_config:
                self.connection_dialog.path_edit.setText(acq_config["存储路径"])
            if "自动保存" in acq_config:
                self.connection_dialog.auto_save_check.setChecked(acq_config["自动保存"])
            if "校准模式" in acq_config:
                self.is_calibration_mode = acq_config["校准模式"]
                self.connection_dialog.calibration_mode_check.setChecked(self.is_calibration_mode)
                self._toggle_calibration_mode(self.is_calibration_mode)
            # 图像处理配置
            proc_config = config.get("图像处理", {})
            if "插值方法" in proc_config:
                self.processing_dialog.interpolation_combo.setCurrentText(proc_config["插值方法"])
            if "对比度" in proc_config:
                self.processing_dialog.contrast_slider.setValue(int(proc_config["对比度"] * 100))
            if "亮度" in proc_config:
                self.processing_dialog.brightness_slider.setValue(proc_config["亮度"])
            if "伪彩色" in proc_config:
                self.processing_dialog.colormap_combo.setCurrentText(proc_config["伪彩色"])
            if "Gamma" in proc_config:
                self.processing_dialog.gamma_slider.setValue(int(proc_config["Gamma"] * 100))
            if "锐化" in proc_config:
                self.processing_dialog.sharpen_slider.setValue(int(proc_config["锐化"] * 10))
            if "高斯模糊" in proc_config:
                self.processing_dialog.gaussian_blur_slider.setValue(int(proc_config["高斯模糊"] * 10))
            if "双边滤波" in proc_config:
                self.processing_dialog.bilateral_filter_slider.setValue(proc_config["双边滤波"])
            if "中值滤波" in proc_config:
                self.processing_dialog.median_check.setChecked(proc_config["中值滤波"])
            if "边缘检测" in proc_config:
                self.processing_dialog.edge_detection_combo.setCurrentText(proc_config["边缘检测"])
            if "差分模式" in proc_config:
                self.processing_dialog.diff_combo.setCurrentText(proc_config["差分模式"])
            if "累积帧数" in proc_config:
                self.processing_dialog.accumulate_slider.setValue(proc_config["累积帧数"])
            # 卡尔曼滤波配置
            kalman_config = config.get("卡尔曼滤波", {})
            if "模式" in kalman_config:
                mode = kalman_config["模式"] == "理论时序"
                self.connection_dialog.kalman_mode_btn.setChecked(mode)
            if "自动切换" in kalman_config:
                self.connection_dialog.auto_switch_check.setChecked(kalman_config["自动切换"])
            self._update_all_value_labels()
            self.update_image_display()
            self._log("配置", "配置已成功应用到UI", LOG_INFO)
        except Exception as e:
            self._log("配置", f"应用配置失败: {e}", LOG_ERROR)

    @Slot()
    def on_user_manual(self):
        """切换操作说明对话框的显示/隐藏"""
        if self.operation_manual_dialog.isVisible():
            self.operation_manual_dialog.hide()
        else:
            # 确保对话框显示在主窗口上方
            self.operation_manual_dialog.show()
            self.operation_manual_dialog.raise_()
            self.operation_manual_dialog.activateWindow()

    @Slot()
    def on_help_dialog(self):
        """切换关于与支持对话框的显示/隐藏"""
        if self.help_dialog.isVisible():
            self.help_dialog.hide()
        else:
            self.help_dialog.show()
            self.help_dialog.raise_()
            self.help_dialog.activate_window()

    def on_about(self):
        for msg in ["太赫兹探测器采集软件 v1.0.0 | © 2026 安徽中科太赫兹科技有限公司", "授权信息：专业版 | 已激活"]:
            self._log("帮助", msg, LOG_INFO)

    def restart_application(self):
        """
        软重启，保留配置，只清空数据和状态
        """
        try:
            # 停止采集和回放
            if self.is_recording:
                self.stop_recording()
            self.playback_controller.clear()

            # 停止定时器
            self.fps_timer.stop()
            # 移除：停止重连定时器

            # 清空数据缓存
            self.recorded_frames.clear()
            self.frame_buffer.clear()
            self.current_frame = None
            self.reference_frame_for_playback = None

            # 重置坐标和状态
            self.current_coordinate = np.zeros(COORD_DIMENSION)
            self.last_received_coord = np.zeros(6)
            self.coord_repeat_count = 0
            self.session_started = False
            self.waiting_for_first_coordinate = False
            self.first_frame_data = None
            self.is_playback_mode = False

            # 重置数据保存器
            if self.data_saver:
                if self.data_saver.current_session_path:
                    self.data_saver.end_session()
                self.data_saver = None

            # 重置卡尔曼滤波器
            self.coordinate_predictor.reset()

            # 重置UI状态
            self.frame_counter_label.setText("0/0")
            self.image_label.setText("<span style='color:#999999; font-size:14px;'>等待采集...</span>")
            self.image_label.setPixmap(QPixmap())  # 清空图像
            self.drone_widget.set_coordinate(np.zeros(COORD_DIMENSION), "", 0.0)

            # 清空日志显示（可选，保留最后一条提示信息）
            self.log_widget.clear()
            self._log("重启", "所有数据已清空，系统已重置", LOG_INFO)

            # 强制垃圾回收
            gc.collect()

            # 记录内存状态
            self._log_memory("重启")

            # 恢复必要定时器
            self.log_scroll_timer.start(100)

            # 新增：软重启后也自动开始监听
            QTimer.singleShot(500, self._auto_start_listening)

        except Exception as e:
            self._log("重启", f"重置失败: {e}", LOG_ERROR)

    def closeEvent(self, event: QCloseEvent):
        self.fps_timer.stop()
        self.log_scroll_timer.stop()  # 停止日志滚动定时器
        self._log("退出", "正在关闭应用并保存设置...", LOG_INFO)
        self.save_settings()
        settings = QSettings("T-Waves", "THZDetector")
        settings.setValue("splash/pos", self.pos())
        if self.tcp_server.is_connected:
            self.tcp_server.stop_listening()
        # 关闭所有对话框
        self.connection_dialog.close()
        self.processing_dialog.close()
        self.operation_manual_dialog.close()
        self.help_dialog.close()
        event.accept()

    def _log_memory(self, phase: str):
        process = psutil.Process()
        mem_info = process.memory_info()
        self._log("内存", f"{phase}: RSS={mem_info.rss // 1024 ** 2}MB, 帧数={len(self.recorded_frames)}", LOG_INFO)