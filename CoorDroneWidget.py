# -------------------- 12维卡尔曼滤波器 --------------------
from PySide6.QtWidgets import (QLabel, QSizePolicy)
from PySide6.QtCore import (Qt, QTimer)
from PySide6.QtGui import (QVector3D)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
import numpy as np
import collections
from typing import Optional
import OpenGL.GLU as glu
import math
import OpenGL.GL as gl

from C import COORD_DIMENSION

class CoordinatePredictor:
    """12维卡尔曼滤波器用于预测无人机坐标
    状态向量（12维）: [x, y, z, roll, pitch, yaw, vx, vy, vz, vroll, vpitch, vyaw]
    - 位置/姿态（6维）：x,y,z坐标 + roll,pitch,yaw角度
    - 速度/角速度（6维）：线速度和角速度
    """
    def __init__(self, initial_fps: float = 30.0):
        """
        初始化卡尔曼滤波器
        输入参数:
            initial_fps: float - 初始帧率，用于计算默认时间步长
        """
        # 状态维度: 12维状态向量
        self.state_dim = COORD_DIMENSION  # 从常量导入，通常是12
        # 状态转移矩阵 A（动态更新dt）
        # 描述状态从t-1到t时刻的转移关系
        self.A = np.eye(self.state_dim)
        # 观测矩阵 H (观测位置和姿态)
        # 从12维状态向量中提取6维可观测部分（位置和姿态）
        self.H = np.zeros((6, self.state_dim))
        for i in range(6):
            self.H[i, i] = 1.0
        # 过程噪声协方差 Q
        # 表示状态转移模型中的不确定性
        self.Q = np.eye(self.state_dim) * 0.1
        # 观测噪声协方差 R（基础值）
        # 表示传感器测量的不确定性
        self.R_base = np.eye(6) * 1.0
        # 当前使用的 R（根据是否更新动态调整）
        self.R = self.R_base.copy()
        # 状态估计（12维向量）
        self.x = np.zeros(self.state_dim)
        # 协方差估计
        # 表示对当前状态估计的不确定性
        self.P = np.eye(self.state_dim) * 100.0
        # 上次更新时间戳
        self.last_update_time = None
        # 历史状态队列（用于调试和分析）
        self.state_history = collections.deque(maxlen=10)
        # FPS相关参数
        self.current_fps = initial_fps
        self.default_dt = 1.0 / initial_fps
        # 模式选择：True=使用理论FPS，False=使用实际测量时间间隔
        self.use_fixed_fps = True  # 默认使用理论时序模式
        # 日志回调函数（用于外部日志记录）
        self.log_callback = None

    def set_fps(self, fps: float, use_fixed: Optional[bool] = None):
        """
        更新滤波器的FPS参数
        输入参数:
            fps: float - 新的帧率值（必须>0）
            use_fixed: Optional[bool] - 是否使用固定FPS模式，None则保持当前模式
        """
        if fps <= 0:
            return
        # 更新FPS和时间步长
        self.current_fps = fps
        self.default_dt = 1.0 / fps
        # 根据参数决定模式
        if use_fixed is not None:
            self.use_fixed_fps = use_fixed
        # 记录日志
        if self.log_callback:
            mode_str = "理论时序" if self.use_fixed_fps else "测量时序"
            self.log_callback(f"卡尔曼滤波器fps已更新为: {fps:.1f} ({mode_str})")

    def reset(self):
        """重置滤波器到初始状态
        无输入参数
        无返回值
        """
        self.x = np.zeros(self.state_dim)  # 重置状态向量
        self.P = np.eye(self.state_dim) * 100.0  # 重置协方差
        self.last_update_time = None  # 清除时间戳
        self.state_history.clear()  # 清空历史
        self.R = self.R_base.copy()  # 重置观测噪声
        self.use_fixed_fps = True  # 重置为默认模式

    def update(self, measurement: np.ndarray, timestamp: float, is_coord_updated: bool = True):
        """
        执行卡尔曼滤波更新步骤（预测+更新）
        输入参数:
            measurement: np.ndarray - 6维测量向量 [x, y, z, roll, pitch, yaw]
            timestamp: float - 当前测量数据的时间戳
            is_coord_updated: bool - 标记坐标是否为新数据（True=新数据，False=重复数据）
        返回值: 无（更新内部状态self.x）
        """
        # 验证测量数据长度
        if len(measurement) != 6:
            if self.log_callback:
                self.log_callback(f"测量数据长度错误: {len(measurement)} != 6")
            return
        # ===== 核心逻辑：根据模式选择dt计算方式 =====
        if self.use_fixed_fps:
            # 模式1：使用推送的FPS作为时间步长
            dt = self.default_dt
            if self.log_callback:
                self.log_callback(f"使用推送端FPS: dt={dt:.4f}s, FPS={self.current_fps:.1f}")
        else:
            # 模式2：使用实际收到数据的时间间隔
            if self.last_update_time is not None:
                dt = timestamp - self.last_update_time
                if self.log_callback:
                    actual_fps = 1 / dt if dt > 0 else 0
                    self.log_callback(f"使用实际时间间隔: dt={dt:.4f}s, FPS={actual_fps:.1f}")
            else:
                dt = self.default_dt
                if self.log_callback:
                    self.log_callback(f"首次更新，使用默认dt={dt:.4f}s")
        # 更新状态转移矩阵A的速度项（位置+=速度*dt）
        for i in range(6):
            self.A[i, i + 6] = dt
        # 记录当前时间戳
        self.last_update_time = timestamp
        # 根据坐标是否更新来调整观测噪声协方差R
        # 如果是重复数据，增大观测噪声，降低对测量值的信任度
        if is_coord_updated:
            self.R = self.R_base.copy()
            if self.log_callback:
                self.log_callback("坐标已更新，使用正常观测噪声")
        else:
            self.R = self.R_base * 100.0  # 增大100倍
            if self.log_callback:
                self.log_callback("坐标重复，增大观测噪声，信任预测值")
        # ===== 预测步骤 =====
        # 预测下一时刻的状态
        x_prior = self.A @ self.x
        # 预测下一时刻的协方差
        P_prior = self.A @ self.P @ self.A.T + self.Q
        if self.log_callback:
            self.log_callback(f"预测: pos=({x_prior[0]:.3f}, {x_prior[1]:.3f}, {x_prior[2]:.3f})")
        # ===== 更新步骤 =====
        z = measurement  # 当前测量值
        y = z - self.H @ x_prior  # 测量残差（实际与预测的差值）
        S = self.H @ P_prior @ self.H.T + self.R  # 残差协方差
        K = P_prior @ self.H.T @ np.linalg.inv(S)  # 卡尔曼增益
        # 更新状态估计
        self.x = x_prior + K @ y
        # 更新协方差估计
        self.P = (np.eye(self.state_dim) - K @ self.H) @ P_prior
        # 保存历史状态
        self.state_history.append(self.x.copy())
        # 记录日志
        if self.log_callback:
            self.log_callback(f"测量: pos=({z[0]:.3f}, {z[1]:.3f}, {z[2]:.3f})")
            self.log_callback(f"更新: pos=({self.x[0]:.3f}, {self.x[1]:.3f}, {self.x[2]:.3f}), "
                              f"vel=({self.x[6]:.3f}, {self.x[7]:.3f}, {self.x[8]:.3f})")

    def predict(self, future_time: float) -> np.ndarray:
        """
        预测未来时间点的状态
        输入参数:
            future_time: float - 未来时间（秒）
        返回值:
            np.ndarray - 6维预测状态 [x, y, z, roll, pitch, yaw]
        """
        if self.last_update_time is None:
            return self.x[:6].copy()  # 未初始化时返回零状态
        # 使用当前FPS计算预测步数
        steps = int(future_time * self.current_fps)
        if steps <= 0:
            return self.x[:6].copy()
        # 迭代预测
        x_pred = self.x.copy()
        for _ in range(steps):
            x_pred = self.A @ x_pred
        return x_pred[:6].copy()  # 只返回位置和姿态

    def get_current_state(self) -> np.ndarray:
        """
        获取当前状态
        返回值:
            np.ndarray - 12维当前状态向量（完整状态）
        """
        return self.x.copy()

# -------------------- 无人机3D可视化 --------------------
class DroneWidget(QOpenGLWidget):
    """无人机3D可视化组件 - 显示完整12维参数和移动背景"""
    def __init__(self, parent=None):
        """
        初始化3D可视化组件
        输入参数:
            parent: QWidget - 父组件，默认为None
        """
        super().__init__(parent)
        # 设置最小尺寸和大小策略
        self.setMinimumSize(220, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 无人机模型参数
        self.drone_size = 3
        self.arm_length = 3
        # 当前状态 - 完整的12维参数
        self.position = QVector3D(0, 0, 0)  # 位置
        self.rotation = QVector3D(0, 0, 0)  # 姿态：roll, pitch, yaw（角度制）
        # 12维参数和IP地址
        self.full_coords = np.zeros(COORD_DIMENSION)  # 完整12维坐标数组
        self.sender_ip = ""  # 发送数据的客户端IP
        self.push_fps = 0.0  # 推送端FPS
        # 动画定时器（用于刷新显示）
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20fps刷新率
        # 参数显示标签（绿色文字，显示12维参数）
        self.params_label = QLabel(self)
        self.params_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0);
                color: #00ff00;
                font-family: monospace;
                font-size: 8px;
                padding: 4px;
                border-radius: 3px;
            }
        """)
        self.params_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.params_label.setWordWrap(True)
        # IP显示标签（黄色文字，左下角）
        self.ip_label = QLabel(self)
        self.ip_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 200);
                color: #ffff00;
                font-family: monospace;
                font-size: 10px;
                padding: 3px 5px;
                border-radius: 3px;
            }
        """)
        self.ip_label.setAlignment(Qt.AlignCenter)
        # FPS显示标签（青色文字，右下角）
        self.fps_label = QLabel(self)
        self.fps_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 200);
                color: #00ffff;
                font-family: monospace;
                font-size: 10px;
                padding: 3px 5px;
                border-radius: 3px;
            }
        """)
        self.fps_label.setAlignment(Qt.AlignCenter)

    def set_coordinate(self, coord: np.ndarray, sender_ip: str = "", push_fps: float = 0.0):
        """
        设置无人机坐标、IP和FPS
        输入参数:
            coord: np.ndarray - 12维坐标数组 [x,y,z,roll,pitch,yaw,vx,vy,vz,vr,vp,vy]
            sender_ip: str - 发送数据的客户端IP地址，默认为空字符串
            push_fps: float - 推送端FPS，默认为0.0
        """
        if len(coord) >= COORD_DIMENSION:
            self.full_coords = coord  # 保存完整12维坐标
            # 更新位置（用于背景移动效果）
            self.position = QVector3D(coord[0], coord[1], coord[2])
            # 更新姿态
            self.rotation = QVector3D(coord[3], coord[4], coord[5])
            # 保存客户端信息
            self.sender_ip = sender_ip
            self.push_fps = push_fps
            # 更新参数显示文本（12维参数）
            params_text = f"""位置: x={coord[0]:.2f} y={coord[1]:.2f} z={coord[2]:.2f}
姿态: r={coord[3]:.1f}° p={coord[4]:.1f}° yw={coord[5]:.1f}°
线速度: vx={coord[6]:.2f} vy={coord[7]:.2f} vz={coord[8]:.2f}
角速度: vr={coord[9]:.2f} vp={coord[10]:.2f} vy={coord[11]:.2f}"""
            self.params_label.setText(params_text)
            # 更新IP显示
            if sender_ip:
                self.ip_label.setText(f"客户端: {sender_ip}")
            # 更新FPS显示
            if push_fps > 0:
                self.fps_label.setText(f"推送FPS: {push_fps:.1f}")
            # 触发重绘
            self.update()

    def update_animation(self):
        """更新动画（触发重绘）"""
        self.update()

    def initializeGL(self):
        """初始化OpenGL环境"""
        gl.glEnable(gl.GL_DEPTH_TEST)  # 启用深度测试
        gl.glClearColor(0.05, 0.05, 0.1, 1.0)  # 设置清除颜色：深蓝色天空背景

    def resizeGL(self, w: int, h: int):
        """
        窗口大小改变时调用
        输入参数:
            w: int - 新宽度
            h: int - 新高度
        """
        # 设置视口
        gl.glViewport(0, 0, w, h)
        # 设置投影矩阵
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        aspect = w / h if h > 0 else 1.0
        glu.gluPerspective(60.0, aspect, 0.1, 100.0)  # 透视投影
        # 设置模型视图矩阵
        gl.glMatrixMode(gl.GL_MODELVIEW)
        # 调整标签大小和位置
        self.params_label.setGeometry(0, 0, min(300, w - 0), min(48, h - 20))
        # IP标签在左下角
        ip_width = min(150, w - 10)
        self.ip_label.setGeometry(5, h - 20, ip_width, 15)
        # FPS标签在右下角
        fps_width = min(100, w - 10)
        self.fps_label.setGeometry(w - fps_width - 5, h - 20, fps_width, 15)

    def paintGL(self):
        """绘制无人机 - 第三人称视角，背景移动效果"""
        # 清除缓冲区
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glLoadIdentity()
        # 设置第三人称视角相机（固定跟随）
        camera_distance = 7.0
        camera_height = 3.0
        # 相机固定在无人机后方（无人机保持在画面中心）
        # gluLookAt(eyeX, eyeY, eyeZ, centerX, centerY, centerZ, upX, upY, upZ)
        glu.gluLookAt(0, -camera_distance, camera_height,  # 相机位置
                      0, 0, 0,  # 观察点（无人机在中心）
                      0, 0, 1)  # 上方向
        # 绘制地面网格，根据无人机位置移动
        self.draw_moving_ground()
        # 绘制无人机（始终在中心）
        self.draw_drone()

    def draw_moving_ground(self):
        """绘制移动的地面网格（根据无人机位置移动）"""
        gl.glBegin(gl.GL_LINES)
        gl.glColor3f(0.3, 0.3, 0.3)  # 灰色网格线
        grid_size = 20  # 网格范围
        grid_step = 1.0  # 网格间距
        # 根据无人机位置计算网格偏移（实现移动效果）
        offset_x = self.position.x() % grid_step
        offset_y = self.position.y() % grid_step
        # 绘制网格线
        for i in range(-grid_size, grid_size + 1):
            # 平行于X轴的线（考虑Y偏移）
            y_pos = i * grid_step - offset_y
            gl.glVertex3f(-grid_size * grid_step, y_pos, 0)
            gl.glVertex3f(grid_size * grid_step, y_pos, 0)
            # 平行于Y轴的线（考虑X偏移）
            x_pos = i * grid_step - offset_x
            gl.glVertex3f(x_pos, -grid_size * grid_step, 0)
            gl.glVertex3f(x_pos, grid_size * grid_step, 0)
        gl.glEnd()
        # 绘制坐标轴（固定在世界坐标系原点）
        gl.glPushMatrix()
        # 将坐标轴移到无人机相对位置（保持相对关系）
        gl.glTranslatef(-self.position.x(), -self.position.y(), 0)
        self.draw_axes()
        gl.glPopMatrix()

    def draw_axes(self):
        """绘制世界坐标轴（X红，Y绿，Z蓝）"""
        axis_length = 3.0
        gl.glBegin(gl.GL_LINES)
        # X轴 - 红色
        gl.glColor3f(1.0, 0.0, 0.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(axis_length, 0, 0)
        # Y轴 - 绿色
        gl.glColor3f(0.0, 1.0, 0.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(0, axis_length, 0)
        # Z轴 - 蓝色
        gl.glColor3f(0.0, 0.0, 1.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(0, 0, axis_length)
        gl.glEnd()

    def draw_drone(self):
        """绘制无人机 - 简化版，始终在画面中心"""
        gl.glPushMatrix()
        # 应用旋转 (ZYX顺序) - 位置固定在原点
        gl.glRotatef(self.rotation.z(), 0, 0, 1)  # yaw（偏航）
        gl.glRotatef(self.rotation.y(), 0, 1, 0)  # pitch（俯仰）
        gl.glRotatef(self.rotation.x(), 1, 0, 0)  # roll（横滚）
        # 绘制机身（简化立方体）
        gl.glColor3f(0.2, 0.6, 1.0)  # 蓝色机身
        gl.glBegin(gl.GL_QUADS)
        # 顶面
        gl.glVertex3f(-0.4, -0.4, 0.1)
        gl.glVertex3f(0.4, -0.4, 0.1)
        gl.glVertex3f(0.4, 0.4, 0.1)
        gl.glVertex3f(-0.4, 0.4, 0.1)
        # 底面
        gl.glVertex3f(-0.4, -0.4, -0.1)
        gl.glVertex3f(-0.4, 0.4, -0.1)
        gl.glVertex3f(0.4, 0.4, -0.1)
        gl.glVertex3f(0.4, -0.4, -0.1)
        gl.glEnd()
        # 绘制机臂（简化线条）
        gl.glColor3f(0.8, 0.8, 0.8)  # 灰色
        gl.glBegin(gl.GL_LINES)
        arm_length = self.arm_length
        # 四个机臂（四旋翼布局）
        arms = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
        for dx, dy in arms:
            gl.glVertex3f(0, 0, 0)  # 中心点
            gl.glVertex3f(dx * arm_length * 0.3, dy * arm_length * 0.3, 0)
        gl.glEnd()
        # 绘制电机（简化球体）
        gl.glColor3f(1.0, 0.0, 0.0)  # 红色电机
        for dx, dy in arms:
            gl.glPushMatrix()
            gl.glTranslatef(dx * arm_length * 0.3, dy * arm_length * 0.3, 0)
            self.draw_sphere(0.2, 6, 6)  # 半径0.2，6x6细分
            gl.glPopMatrix()
        # 绘制螺旋桨旋转圆环
        gl.glColor3f(0.0, 1.0, 0.0)  # 绿色
        gl.glBegin(gl.GL_LINE_LOOP)
        prop_radius = arm_length * 0.5
        # 绘制16边形圆环
        for i in range(16):
            angle = i * 22.5 * math.pi / 180  # 22.5度 = 360/16
            x = prop_radius * math.cos(angle)
            y = prop_radius * math.sin(angle)
            gl.glVertex3f(x, y, 0.3)
        gl.glEnd()
        gl.glPopMatrix()

    def draw_sphere(self, radius: float, slices: int, stacks: int):
        """
        使用纯OpenGL绘制球体
        输入参数:
            radius: float - 球体半径
            slices: int - 经度方向细分数量
            stacks: int - 纬度方向细分数量
        """
        for i in range(stacks):
            # 计算当前纬度
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = math.sin(lat0)
            zr0 = math.cos(lat0)
            # 计算下一纬度
            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = math.sin(lat1)
            zr1 = math.cos(lat1)
            # 绘制四边形条带
            gl.glBegin(gl.GL_QUAD_STRIP)
            for j in range(slices + 1):
                lng = 2 * math.pi * float(j) / slices
                x = math.cos(lng)
                y = math.sin(lng)
                # 当前纬度顶点
                gl.glNormal3f(x * zr0 * radius, y * zr0 * radius, z0 * radius)
                gl.glVertex3f(x * zr0 * radius, y * zr0 * radius, z0 * radius)
                # 下一纬度顶点
                gl.glNormal3f(x * zr1 * radius, y * zr1 * radius, z1 * radius)
                gl.glVertex3f(x * zr1 * radius, y * zr1 * radius, z1 * radius)
            gl.glEnd()