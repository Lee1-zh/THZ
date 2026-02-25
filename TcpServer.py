# -*- coding: utf-8 -*-
from PySide6.QtCore import (QTimer, Signal, QObject)
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
import numpy as np
import cv2
from typing import Optional
import struct
import time

from C import LOG_ERROR, FRAME_HEIGHT, FRAME_WIDTH, COORD_DIMENSION, LISTEN_PORT, LOG_INFO

class TcpServer(QObject):
    dataReceived = Signal(np.ndarray)
    coordinateReceived = Signal(np.ndarray, float, float, str)  # 坐标数据、时间戳、fps、发送端IP
    connectionChanged = Signal(bool, str)  # 连接状态、心跳状态
    connectionError = Signal(str)
    connectionQuality = Signal(float)  # 新增：连接质量（毫秒级延迟）
    def __init__(self, log_callback=None):  # 添加回调参数
        super().__init__()
        self.log_callback = log_callback  # 保存回调函数
        self.server = QTcpServer(self)
        self.client_socket: Optional[QTcpSocket] = None
        self.read_buffer = bytearray()
        self.expected_size = 0
        self.server.newConnection.connect(self._on_new_connection)
        # 帧数据缓冲区
        self.frame_data_buffer = bytearray()
        self.coord_data_buffer = bytearray()
        # 心跳检测
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self._check_heartbeat)
        self.last_data_time = time.time()
        self.heartbeat_status = "正常"
        # 新增：延迟测量相关
        self._last_packet_time = time.time()  # 上次收到数据包的时间
        self._current_delay_ms = 0.0  # 当前估算的延迟（毫秒）

    def _on_new_connection(self):
        if self.client_socket:
            self._cleanup_client_socket()
        self.client_socket = self.server.nextPendingConnection()
        if not self.client_socket:
            return
        self.client_socket.readyRead.connect(self._on_data_ready_read)
        self.client_socket.disconnected.connect(self._on_client_disconnected)
        self.client_socket.errorOccurred.connect(self._on_socket_error)
        self.client_socket.setSocketOption(QTcpSocket.KeepAliveOption, 1)
        self.client_socket.setSocketOption(QTcpSocket.LowDelayOption, 1)
        peer = f"{self.client_socket.peerAddress().toString()}:{self.client_socket.peerPort()}"
        if self.log_callback:
            self.log_callback("网络", f"客户端接入 {peer}", LOG_INFO)
        # 重置心跳和延迟计时
        self.last_data_time = time.time()
        self._last_packet_time = time.time()
        self._current_delay_ms = 0.0
        self.heartbeat_timer.start(1000)  # 每秒检查一次
        self.connectionChanged.emit(True, self.heartbeat_status)

    def _on_client_disconnected(self):
        if self.log_callback:
            self.log_callback("网络", "客户端断开", LOG_INFO)
        self.heartbeat_timer.stop()
        self.heartbeat_status = "断开"
        self._cleanup_client_socket()
        self.connectionChanged.emit(False, self.heartbeat_status)

    def _on_socket_error(self, error):
        if self.client_socket:
            error_msg = self.client_socket.errorString()
            if self.log_callback:
                self.log_callback("网络", f"Socket错误: {error_msg}", LOG_ERROR)
            self.connectionError.emit(error_msg)
            self._on_client_disconnected()

    def _check_heartbeat(self):
        """检查心跳状态"""
        elapsed = time.time() - self.last_data_time
        if elapsed > 5.0:  # 5秒无数据
            if self.heartbeat_status != "待机":
                self.heartbeat_status = "待机"
                self.connectionChanged.emit(True, self.heartbeat_status)
        else:
            if self.heartbeat_status != "正常":
                self.heartbeat_status = "正常"
                self.connectionChanged.emit(True, self.heartbeat_status)

    def _cleanup_client_socket(self):
        if self.client_socket:
            try:
                self.client_socket.readyRead.disconnect()
                self.client_socket.disconnected.disconnect()
                self.client_socket.errorOccurred.disconnect()
            except:
                pass
            if self.client_socket.state() != QTcpSocket.UnconnectedState:
                self.client_socket.disconnectFromHost()
                if self.client_socket.waitForDisconnected(1000):
                    self.client_socket.deleteLater()
            self.client_socket = None
        self.read_buffer.clear()
        self.expected_size = 0
        self.frame_data_buffer.clear()
        self.coord_data_buffer.clear()

    def _on_data_ready_read(self):
        if not self.client_socket:
            return
        while self.client_socket.bytesAvailable():
            data = self.client_socket.readAll()
            self.read_buffer.extend(data)
            self.last_data_time = time.time()  # 更新心跳时间
            # 新增：计算数据包到达延迟
            current_time = time.time()
            time_diff = current_time - self._last_packet_time
            self._current_delay_ms = time_diff * 1000.0  # 转换为毫秒
            self._last_packet_time = current_time
            # 发送连接质量信号
            self.connectionQuality.emit(self._current_delay_ms)
            # 处理数据包
            self._process_data_packets()

    def _process_data_packets(self):
        """处理数据包（帧数据或坐标数据）"""
        while len(self.read_buffer) >= 8:
            # 读取包头
            header = struct.unpack("!II", self.read_buffer[:8])
            packet_type = header[0]  # 0=帧数据, 1=坐标数据
            packet_size = header[1]
            if len(self.read_buffer) < 8 + packet_size:
                break
            # 提取数据
            packet_data = self.read_buffer[8:8 + packet_size]
            self.read_buffer = self.read_buffer[8 + packet_size:]
            if packet_type == 0:  # 帧数据
                self._process_frame_data(packet_data)
            elif packet_type == 1:  # 坐标数据
                self._process_coordinate_data(packet_data)

    def _process_frame_data(self, data: bytes):
        """处理帧数据"""
        try:
            arr = np.frombuffer(data, dtype=np.float64).copy()
            if arr.size != FRAME_WIDTH * FRAME_HEIGHT:
                return
            frame_2d = arr.reshape((FRAME_HEIGHT, FRAME_WIDTH))
            img8 = cv2.normalize(frame_2d, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            self.dataReceived.emit(img8)
        except Exception as e:
            if self.log_callback:
                self.log_callback("帧处理", f"帧处理失败: {e}", LOG_ERROR)

    def _process_coordinate_data(self, data: bytes):
        """处理坐标数据"""
        try:
            # 解析坐标数据格式: [x, y, z, roll, pitch, yaw, fps, vx, vy, vz, vroll, vpitch, vyaw] (float64)
            arr = np.frombuffer(data, dtype=np.float64).copy()
            if len(arr) >= 7:
                coord = np.zeros(COORD_DIMENSION)
                coord[:min(len(arr), COORD_DIMENSION)] = arr[:min(len(arr), COORD_DIMENSION)]
                fps = arr[6] if len(arr) > 6 else 10.0  # 推送端FPS
                timestamp = time.time()
                # 获取发送端IP
                sender_ip = ""
                if self.client_socket:
                    sender_ip = self.client_socket.peerAddress().toString()
                self.coordinateReceived.emit(coord, timestamp, fps, sender_ip)
        except Exception as e:
            if self.log_callback:
                self.log_callback("坐标处理", f"坐标处理失败: {e}", LOG_ERROR)

    def start_listening(self, ip: str = "0.0.0.0", port: int = LISTEN_PORT) -> bool:
        if self.server.isListening():
            return True
        self._cleanup_client_socket()
        result = self.server.listen(QHostAddress(ip), port)
        if result:
            if self.log_callback:
                self.log_callback("监听", f"服务器在 {ip}:{port} 启动监听", LOG_INFO)
        else:
            if self.log_callback:
                self.log_callback("监听", f"服务器启动监听失败: {self.server.errorString()}", LOG_ERROR)
        return result

    def stop_listening(self):
        if self.server.isListening():
            self.server.close()
            if self.log_callback:
                self.log_callback("监听", "服务器停止监听", LOG_INFO)
        self.heartbeat_timer.stop()
        self.heartbeat_status = "未启动"
        self._cleanup_client_socket()

    @property
    def is_connected(self) -> bool:
        return self.client_socket is not None and self.client_socket.state() == QTcpSocket.ConnectedState