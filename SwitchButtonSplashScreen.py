from PySide6.QtWidgets import (QLabel, QApplication, QAbstractButton, QSplashScreen)
from PySide6.QtCore import (Qt, QSettings, QPropertyAnimation, QRect, QEasingCurve, Property)
from PySide6.QtGui import (QPixmap, QPainter, QColor)
# -------------------- 12维卡尔曼滤波器 --------------------
class SplashScreen(QSplashScreen):
    def __init__(self, logo_path: str):
        # 先创建并处理pixmap
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            screen = QApplication.primaryScreen().geometry()
            max_size = min(screen.width(), screen.height()) * 0.7
            pixmap = pixmap.scaled(int(max_size), int(max_size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # 调用父类初始化
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        # 继续其他初始化
        self.setWindowTitle("启动中...")
        self.version_label = QLabel("v1.0.0", self)
        self.version_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold; background: transparent;")
        self.version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)

    def showEvent(self, event):
        super().showEvent(event)
        settings = QSettings("T-Waves", "THZDetector")
        if pos := settings.value("splash/pos"):
            self.move(pos)
        self.version_label.setGeometry(self.width() - 80, self.height() - 30, 70, 20)

class SwitchButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 26)
        self._offset = 3
        self._brush_background = QColor("#d0d0d0")
        self._brush_circle = QColor("#ffffff")
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.setDuration(200)

    @Property(int)
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value
        self.update()

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_offset()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track_rect = QRect(0, 0, self.width(), self.height()).adjusted(0, 5, 0, -5)
        track_radius = track_rect.height() / 2
        brush = QApplication.palette().highlight() if self.isChecked() else self._brush_background
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)
        circle_size = self.height() - 6
        circle_rect = QRect(self.offset, 3, circle_size, circle_size)
        painter.setBrush(self._brush_circle)
        painter.drawEllipse(circle_rect)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._animate_toggle()

    def toggle(self):
        super().toggle()
        self._animate_toggle()

    def _update_offset(self):
        circle_size = self.height() - 6
        max_offset = self.width() - circle_size - 3
        self._offset = max_offset if self.isChecked() else 3
        self.update()

    def _animate_toggle(self):
        circle_size = self.height() - 6
        max_offset = self.width() - circle_size - 3
        self._animation.setStartValue(self.offset)
        self._animation.setEndValue(max_offset if self.isChecked() else 3)
        self._animation.start()