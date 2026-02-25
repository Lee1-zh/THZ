# -*- coding: utf-8 -*-
from PySide6.QtCore import (QTimer, QObject)
import numpy as np
from typing import List

from C import COORD_DIMENSION
from CoorDroneWidget import DroneWidget
from ScalableImageLabel import ScalableImageLabel

# -------------------- 增强的回放控制器 --------------------
class PlaybackController(QObject):
    def __init__(self, image_label: ScalableImageLabel, drone_widget: DroneWidget, parent=None):
        super().__init__(parent)
        self.image_label = image_label
        self.drone_widget = drone_widget
        self.frames: List[np.ndarray] = []
        self.coords: List[np.ndarray] = []
        self.fps_values: List[float] = []
        self.current_index = 0
        self.is_playing = False
        self.timer = QTimer(self, timeout=self._next_frame)
        self.image_label.play_pause_btn.clicked.connect(self.toggle)
        self.image_label.progress_slider.valueChanged.connect(self._jump_to_frame)

    def set_session_data(self, frames: List[np.ndarray], coords: List[np.ndarray], fps_values: List[float]):
        """设置会话数据（包含坐标）"""
        self.frames = list(frames)
        self.coords = list(coords)
        self.fps_values = list(fps_values)
        self.current_index = max(0, len(frames) - 1)
        self.image_label.set_recorded_frames(len(self.frames))
        if self.fps_values:
            avg_fps = np.mean(self.fps_values)
            self.timer.setInterval(max(1, 1000 // int(avg_fps)))
        else:
            self.timer.setInterval(33)  # 默认30fps

    def clear(self):
        self.frames.clear()
        self.coords.clear()
        self.fps_values.clear()
        self.current_index = 0
        self.is_playing = False
        self.timer.stop()
        self.image_label.set_recorded_frames(0)
        self.drone_widget.set_coordinate(np.zeros(COORD_DIMENSION), "", 0.0)

    def toggle(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.image_label.play_pause_btn.setText("⏸")
            self.timer.start()
        else:
            self.image_label.play_pause_btn.setText("▶")
            self.timer.stop()

    def _next_frame(self):
        if not self.frames:
            return
        self.current_index = (self.current_index + 1) % len(self.frames)
        self._update_display()

    def _jump_to_frame(self, index: int):
        if index < len(self.frames):
            self.current_index = index
            self._update_display()

    def _update_display(self):
        """更新图像和无人机状态"""
        if self.current_index < len(self.frames):
            self.image_label.update_playback_frame(self.current_index, len(self.frames))
            if hasattr(self.parent(), 'on_playback_frame'):
                self.parent().on_playback_frame(self.frames[self.current_index])

        # 更新无人机状态
        if self.current_index < len(self.coords):
            coord = self.coords[self.current_index]
            fps = self.fps_values[self.current_index] if self.current_index < len(self.fps_values) else 30.0
            self.drone_widget.set_coordinate(coord, "", fps)