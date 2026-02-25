# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QApplication)
from PySide6.QtCore import (QTimer)
from PySide6.QtGui import (QColor, QPalette)
import sys
import signal

from C import (LOGO_PATH)
from SwitchButtonSplashScreen import SplashScreen
from TerahertzDetectorUI import TerahertzDetectorUI
# -------------------- main --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#ffffff"))
    palette.setColor(QPalette.WindowText, QColor("#333333"))
    app.setPalette(palette)
    # 创建主窗口
    window = TerahertzDetectorUI()
    # 信号处理函数
    def signal_handler(sig, frame):
        window.close()  # 触发关闭事件
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # 显示启动画面
    splash = SplashScreen(LOGO_PATH)
    splash.show()
    # 定时检查信号（让Python能处理信号）
    timer = QTimer()
    timer.start(200)  # 每200ms触发一次
    timer.timeout.connect(lambda: None)  # 空操作，只是为了让Python处理信号
    QTimer.singleShot(1100, lambda: [splash.close(), window.show()])
    sys.exit(app.exec())