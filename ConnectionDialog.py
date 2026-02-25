from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QLineEdit, QSpinBox, QTextEdit, QDialog, QSizeGrip)
from PySide6.QtCore import (Qt)

from C import _get_textedit_style, _get_button_style, _get_spinbox_style, DEFAULT_FRAME_COUNT, _get_lineedit_style, LISTEN_PORT, _get_groupbox_style, create_icon
from SwitchButtonSplashScreen import SwitchButton

class ConnectionDialog(QDialog):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window  # 保存主窗口引用
        # 设置窗口标志为Tool和无边框
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setMinimumWidth(64)  # 最小宽度128
        # 添加大小调整手柄
        self.size_grip = QSizeGrip(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        # 设备连接管理组
        conn_group = QGroupBox("📡 设备连接管理")
        conn_layout = QVBoxLayout()
        conn_layout.setSpacing(8)
        conn_layout.addWidget(QLabel("监听IP地址:"))
        self.ip_edit = QLineEdit("0.0.0.0")
        self.ip_edit.setStyleSheet(_get_lineedit_style())
        conn_layout.addWidget(self.ip_edit)
        conn_layout.addWidget(QLabel("监听端口:"))
        self.port_edit = QLineEdit(str(LISTEN_PORT))
        self.port_edit.setStyleSheet(_get_lineedit_style())
        conn_layout.addWidget(self.port_edit)
        # 移除：自动重启监听选项
        conn_layout.addStretch()
        conn_group.setLayout(conn_layout)
        conn_group.setStyleSheet(_get_groupbox_style())
        layout.addWidget(conn_group)
        # 采集配置管理组
        config_group = QGroupBox("⚙️ 采集配置管理")
        config_layout = QVBoxLayout()
        config_layout.setSpacing(8)
        # 移除FPS配置（由推送端决定）
        config_layout.addWidget(QLabel("总帧数:"))
        self.frame_count_spin = QSpinBox(minimum=1, maximum=1000000, value=DEFAULT_FRAME_COUNT)
        self.frame_count_spin.setStyleSheet(_get_spinbox_style())
        config_layout.addWidget(self.frame_count_spin)

        # 校准模式
        calibration_layout = QHBoxLayout()
        calibration_layout.addWidget(QLabel("校准模式:"))
        calibration_layout.addStretch()
        self.calibration_mode_check = SwitchButton()
        self.calibration_mode_check.setChecked(False)  # 默认关闭
        self.calibration_mode_check.toggled.connect(self._toggle_calibration_mode)
        calibration_layout.addWidget(self.calibration_mode_check)
        config_layout.addLayout(calibration_layout)
        config_layout.addWidget(QLabel("会话路径:"))
        self.path_edit = QTextEdit(r"D:\thz_20251127_扬州风场_01号机组_3号叶片")
        self.path_edit.setStyleSheet(_get_textedit_style())
        self.path_edit.setMaximumHeight(70)
        self.path_edit.setMaximumWidth(150)
        config_layout.addWidget(self.path_edit)
        self.browse_btn = QPushButton(" 浏览...")
        self.browse_btn.setIcon(create_icon("📁", QColor("#666666")))
        self.browse_btn.setStyleSheet(_get_button_style())
        config_layout.addWidget(self.browse_btn)
        autosave_layout = QHBoxLayout()
        autosave_layout.addWidget(QLabel("自动保存:"))
        autosave_layout.addStretch()
        self.auto_save_check = SwitchButton()
        self.auto_save_check.setChecked(True)
        autosave_layout.addWidget(self.auto_save_check)
        config_layout.addLayout(autosave_layout)
        # ==================== 卡尔曼滤波配置 ====================
        kalman_layout = QHBoxLayout()
        kalman_layout.addWidget(QLabel("卡尔曼滤波:"))
        self.kalman_mode_btn = QPushButton("理论时序")
        self.kalman_mode_btn.setCheckable(True)
        self.kalman_mode_btn.setFixedSize(83, 30)
        self.kalman_mode_btn.setStyleSheet(_get_button_style())
        if self.main_window:
            self.kalman_mode_btn.toggled.connect(self.main_window._toggle_kalman_mode)
        kalman_layout.addWidget(self.kalman_mode_btn)
        config_layout.addLayout(kalman_layout)
        auto_switch_layout = QHBoxLayout()
        auto_switch_layout.addWidget(QLabel("自动切换:"))
        auto_switch_layout.addStretch()
        self.auto_switch_check = SwitchButton()
        self.auto_switch_check.setChecked(False)  # 默认为关闭
        if self.main_window:
            self.auto_switch_check.toggled.connect(self.main_window._toggle_auto_switch)
        auto_switch_layout.addWidget(self.auto_switch_check)
        config_layout.addLayout(auto_switch_layout)
        # ==================== 新增结束 ====================
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        config_group.setStyleSheet(_get_groupbox_style())
        layout.addWidget(config_group)
        layout.addStretch()
        # 添加大小调整手柄到右下角
        size_grip_layout = QHBoxLayout()
        size_grip_layout.addStretch()
        size_grip_layout.addWidget(self.size_grip)
        layout.addLayout(size_grip_layout)

    def _toggle_calibration_mode(self, checked):
        """切换校准模式"""
        if self.main_window:
            self.main_window._toggle_calibration_mode(checked)