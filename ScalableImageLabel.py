# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
                               QGraphicsOpacityEffect, QLabel, QSizePolicy)
from PySide6.QtCore import (Qt, QPropertyAnimation, QEvent, QPoint)
from PySide6.QtGui import (QPixmap, QPainter, QEnterEvent, QTouchEvent, QTabletEvent)
from typing import Optional

from C import DISPLAY_SIZE, CONTROL_BAR_HEIGHT, FADE_DURATION


# -------------------- 可缩放的图像标签组件（支持触屏） --------------------
class ScalableImageLabel(QLabel):
    """
    支持缩放、平移的图像显示标签，内置播放控制条

    支持交互方式：
    - 鼠标：滚轮缩放，悬停显示控制条
    - 触屏：双指缩放，单指拖动，点击显示控制条，操作完成后自动隐藏
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ========== 基础配置 ==========
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(DISPLAY_SIZE, DISPLAY_SIZE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            border: 1px solid #e0e0e0; 
            background: #fafafa; 
            border-radius: 4px;
        """)
        self.setMouseTracking(True)
        # 启用触屏事件接收
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

        # ========== 图像状态变量 ==========
        self.original_pixmap: Optional[QPixmap] = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.is_recording = False

        # ========== 触屏状态追踪 ==========
        self._touch_active = False  # 是否有手指正在触摸
        self._last_touch_pos = QPoint()  # 最后触摸位置（用于判断是否在控件内）
        self._control_bar_visible = False  # 控制条当前是否可见

        self._setup_control_bar()
        self._setup_animations()

    def _setup_control_bar(self):
        """初始化播放控制条"""
        self.control_bar = QWidget(self)
        self.control_bar.setFixedHeight(CONTROL_BAR_HEIGHT)

        self.control_bar.setStyleSheet("""
            QWidget { 
                background-color: rgba(240, 240, 240, 220); 
                border: none; 
                border-top: 1px solid #e0e0e0; 
                border-radius: 0 0 4px 4px; 
            }
            QPushButton { 
                background-color: #ffffff; 
                border: 1px solid #cccccc; 
                border-radius: 15px; 
                font-size: 16px; 
                padding: 4px; 
            }
            QPushButton:hover { 
                background-color: #f5f5f5; 
                border-color: #999999; 
            }
            QSlider { 
                background-color: transparent; 
                height: 20px; 
            }
            QSlider::groove:horizontal { 
                height: 6px; 
                background: #e0e0e0; 
                border-radius: 3px; 
            }
            QSlider::handle:horizontal { 
                width: 16px; 
                height: 16px; 
                background: #ffffff; 
                border: 1px solid #cccccc; 
                border-radius: 8px; 
                margin: -5px 0; 
            }
            QSlider::handle:horizontal:hover { 
                background: #f0f0f0; 
                border-color: #999999; 
            }
        """)

        control_layout = QVBoxLayout(self.control_bar)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(7)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)

        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedSize(32, 32)
        button_layout.addWidget(self.play_pause_btn)

        self.frame_info_label = QLabel("第 0 帧 / 共 0 帧")
        self.frame_info_label.setStyleSheet("""
            color: #333333; 
            font-size: 12px; 
            font-weight: 500;
        """)
        button_layout.addWidget(self.frame_info_label)
        button_layout.addStretch()

        control_layout.addLayout(button_layout)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        control_layout.addWidget(self.progress_slider)

        self.control_bar.setMouseTracking(True)
        self.control_bar.hide()

    def _setup_animations(self):
        """设置淡入淡出动画"""
        self.opacity_effect = QGraphicsOpacityEffect(self.control_bar)
        self.control_bar.setGraphicsEffect(self.opacity_effect)

        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(FADE_DURATION)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)

        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(FADE_DURATION)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(self.control_bar.hide)

    def event(self, event: QEvent) -> bool:
        """
        统一事件处理：同时捕获鼠标事件和触屏事件

        解决触屏设备不触发 enterEvent/leaveEvent 的问题
        """
        event_type = event.type()

        # ========== 触屏事件处理 ==========
        if event_type == QEvent.TouchBegin:
            self._touch_active = True
            touch_event = QTouchEvent(event)
            if touch_event.touchPoints():
                # 获取第一个触摸点位置
                pos = touch_event.touchPoints()[0].pos().toPoint()
                self._last_touch_pos = pos
                # 无论在哪，只要开始触摸就显示控制条
                if not self.is_recording:
                    self._show_control_bar()
            return True

        elif event_type == QEvent.TouchUpdate:
            self._touch_active = True
            touch_event = QTouchEvent(event)
            if touch_event.touchPoints():
                pos = touch_event.touchPoints()[0].pos().toPoint()
                self._last_touch_pos = pos
                # 触摸过程中保持显示
                if not self.is_recording and not self._control_bar_visible:
                    self._show_control_bar()
            return True

        elif event_type == QEvent.TouchEnd:
            self._touch_active = False
            # 触摸结束后，延迟检查是否需要隐藏
            # 使用 QTimer.singleShot 延迟判断，给 leaveEvent 机会触发
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._check_should_hide)
            return True

        # ========== 平板/手写笔事件（部分触摸屏驱动使用） ==========
        elif event_type == QEvent.TabletPress:
            self._touch_active = True
            tablet_event = QTabletEvent(event)
            self._last_touch_pos = tablet_event.pos()
            if not self.is_recording:
                self._show_control_bar()
            return True

        elif event_type == QEvent.TabletMove:
            self._touch_active = True
            tablet_event = QTabletEvent(event)
            self._last_touch_pos = tablet_event.pos()
            return True

        elif event_type == QEvent.TabletRelease:
            self._touch_active = False
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._check_should_hide)
            return True

        # ========== 鼠标事件（保持原有逻辑） ==========
        elif event_type == QEvent.MouseMove:
            # 鼠标移动时更新位置
            mouse_event = event
            self._last_touch_pos = mouse_event.pos()
            # 确保控制条显示（兼容纯鼠标设备）
            if not self.is_recording and not self._control_bar_visible:
                self._show_control_bar()

        return super().event(event)

    def enterEvent(self, event: QEnterEvent):
        """鼠标/手指进入控件区域"""
        super().enterEvent(event)
        if not self.is_recording:
            self._show_control_bar()

    def leaveEvent(self, event):
        """鼠标/手指离开控件区域"""
        super().leaveEvent(event)
        if not self.is_recording and not self._touch_active:
            # 只有在没有活跃触摸时才隐藏
            self._hide_control_bar()

    def _show_control_bar(self):
        """显示控制条"""
        self._control_bar_visible = True
        self.control_bar.show()
        self.fade_out_animation.stop()
        self.fade_in_animation.start()

    def _hide_control_bar(self):
        """隐藏控制条"""
        self._control_bar_visible = False
        self.fade_in_animation.stop()
        self.fade_out_animation.start()

    def _check_should_hide(self):
        """
        检查是否应该隐藏控制条（用于触屏结束后）

        如果手指抬起时不在控件区域内，则隐藏
        """
        if self.is_recording or self._touch_active:
            return

        # 检查最后位置是否在控件范围内
        if not self.rect().contains(self._last_touch_pos):
            self._hide_control_bar()
        # 如果在范围内，保持显示（等待 leaveEvent 或下次操作）

    def set_recording(self, recording: bool):
        """设置录制状态"""
        self.is_recording = recording
        if recording:
            self._control_bar_visible = False
            self.control_bar.hide()

    def setPixmap(self, pixmap: Optional[QPixmap]):
        """设置图像"""
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.offset_x = self.offset_y = 0
        self._update_display()

    def _update_display(self):
        """更新图像显示"""
        if not self.original_pixmap:
            return

        widget_size = min(self.width(), self.height())
        target_size = int(widget_size * self.scale_factor)

        scaled = self.original_pixmap.scaled(
            target_size, target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        display_pixmap = QPixmap(self.width(), self.height())
        display_pixmap.fill(Qt.transparent)

        painter = QPainter(display_pixmap)

        if self.scale_factor <= 1.0:
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            max_offset_x = max(0, scaled.width() - self.width())
            max_offset_y = max(0, scaled.height() - self.height())
            self.offset_x = max(0, min(self.offset_x, max_offset_x))
            self.offset_y = max(0, min(self.offset_y, max_offset_y))
            painter.drawPixmap(-self.offset_x, -self.offset_y, scaled)

        painter.end()
        super().setPixmap(display_pixmap)

    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        if not self.original_pixmap:
            return

        zoom_factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        new_scale = self.scale_factor * zoom_factor

        if 1.0 <= new_scale <= 7.0:
            mouse_pos = event.position().toPoint()
            widget_size = min(self.width(), self.height())
            current_size = int(widget_size * self.scale_factor)

            offset_x = self.offset_x if self.scale_factor > 1.0 else 0
            offset_y = self.offset_y if self.scale_factor > 1.0 else 0

            image_x = (mouse_pos.x() + offset_x) / max(1, current_size) * self.original_pixmap.width()
            image_y = (mouse_pos.y() + offset_y) / max(1, current_size) * self.original_pixmap.height()

            self.scale_factor = new_scale
            new_size = int(widget_size * new_scale)

            if new_scale > 1.0:
                self.offset_x = int(image_x / self.original_pixmap.width() * new_size - mouse_pos.x())
                self.offset_y = int(image_y / self.original_pixmap.height() * new_size - mouse_pos.y())
            else:
                self.offset_x = self.offset_y = 0

            self._update_display()

        event.accept()

    def set_recorded_frames(self, count: int):
        """设置已录制帧数"""
        self.progress_slider.setRange(0, max(0, count - 1))
        self.progress_slider.setEnabled(count > 0)

        if count > 0:
            self.frame_info_label.setText(f"第 {count} 帧 / 共 {count} 帧")
            self.progress_slider.setValue(count - 1)
        else:
            self.frame_info_label.setText("第 0 帧 / 共 0 帧")

    def update_playback_frame(self, frame_index: int, total_frames: int):
        """更新播放进度"""
        self.frame_info_label.setText(f"第 {frame_index + 1} 帧 / 共 {total_frames} 帧")
        self.progress_slider.setValue(frame_index)

    def resizeEvent(self, event):
        """调整大小事件"""
        super().resizeEvent(event)

        if self.original_pixmap:
            widget_size = min(self.width(), self.height())
            x = (self.width() - widget_size) // 2
            y = (self.height() - widget_size) // 2
            self.control_bar.setGeometry(
                x,
                y + widget_size - self.control_bar.height(),
                widget_size,
                self.control_bar.height()
            )
        else:
            self.control_bar.setGeometry(
                0,
                self.height() - self.control_bar.height(),
                self.width(),
                self.control_bar.height()
            )

        if self.original_pixmap:
            self._update_display()