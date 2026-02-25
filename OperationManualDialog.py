# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QTabWidget, QLabel, QDialog)
from PySide6.QtCore import (Qt)

from C import _get_button_style, _get_textedit_style

class OperationManualDialog(QDialog):
    """操作说明对话框，提供详细的软件使用指南"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("操作说明")
        self.setMinimumSize(700, 500)
        self.setWindowFlags(Qt.Tool)  # 设置为工具窗口，非模态
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        # 创建标签页
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #d0d0d0; 
                background-color: #ffffff;
            }
            QTabBar::tab { 
                background-color: #f5f5f5; 
                color: #333333;
                padding: 8px 20px; 
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background-color: #4d90fe; 
                color: white;
            }
            QTabBar::tab:hover { 
                background-color: #e0e0e0;
            }
        """)
        # 快速开始标签页
        quick_start = self._create_quick_start_tab()
        tab_widget.addTab(quick_start, "快速开始")
        # 连接配置标签页
        connection_tab = self._create_connection_tab()
        tab_widget.addTab(connection_tab, "连接配置")
        # 图像处理标签页
        processing_tab = self._create_processing_tab()
        tab_widget.addTab(processing_tab, "图像处理")
        # 采集操作标签页
        acquisition_tab = self._create_acquisition_tab()
        tab_widget.addTab(acquisition_tab, "采集操作")
        # 回放分析标签页
        playback_tab = self._create_playback_tab()
        tab_widget.addTab(playback_tab, "回放分析")
        layout.addWidget(tab_widget)
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet(_get_button_style())
        close_btn.clicked.connect(self.close)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _create_quick_start_tab(self):
        """创建快速开始标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("快速开始指南")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0066cc; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(_get_textedit_style())
        content.setText(
            """欢迎使用 T-Waves Inspector™ 风电叶片太赫兹智能检测系统！

第一步：配置连接
1. 点击左侧箭头按钮打开"设备连接管理"面板
2. 确认监听IP地址和端口设置正确
3. 点击"开始监听"按钮，等待客户端连接
4. 观察监听状态变为"监听中"表示准备就绪

第二步：配置图像处理
1. 点击右侧箭头按钮打开"图像处理"面板
2. 根据检测需求调整以下参数：
   - 差分模式：选择"校准文件"可消除背景噪声
   - 伪彩色：推荐使用"JET"增强缺陷对比度
   - 对比度/亮度：根据信号强度微调
3. 实时预览调整效果

第三步：开始采集
1. 确认客户端已连接并推送数据
2. 点击"开始采集"按钮
3. 观察实时图像和无人机状态显示
4. 系统自动保存采集的数据到指定目录
5. 达到预设帧数后自动停止，或手动停止

第四步：数据分析
1. 点击"文件"→"打开会话"加载历史数据
2. 使用鼠标滚轮缩放图像
3. 悬停显示播放控制条，支持逐帧查看
4. 观察无人机坐标变化与图像的关联

提示：所有配置会自动保存，下次启动时自动恢复。"""
        )
        layout.addWidget(content)
        layout.addStretch()
        return widget

    def _create_connection_tab(self):
        """创建连接配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("连接配置详解")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0066cc; margin-bottom: 10px;")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(_get_textedit_style())
        content.setText(
            """设备连接管理参数说明：

监听IP地址：
• 0.0.0.0：监听所有网络接口，允许任意IP的客户端连接
• 指定IP：仅监听特定网卡，提高安全性

监听端口：
• 默认值：50000
• 范围：1-65535
• 确保端口未被其他程序占用

自动重启监听：
• 开启后，当客户端异常断开时自动重新监听
• 适用于无人值守的长时间采集任务
• 可设置最大重试次数（默认77次）

连接质量监控：
• FPS显示：实际接收数据的帧率
• 延迟显示：数据包到达的时间间隔（毫秒）
• 心跳状态：正常/待机/断开
• 无人机IP：显示当前连接的客户端地址

常见问题：
1. 无法连接：检查防火墙设置，确保端口已开放
2. 频繁断开：检查网络稳定性，考虑启用自动重启
3. 延迟过高：切换到"理论时序"模式，信任推送端FPS"""
        )
        layout.addWidget(content)
        layout.addStretch()
        return widget

    def _create_processing_tab(self):
        """创建图像处理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("图像处理参数说明")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0066cc; margin-bottom: 10px;")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(_get_textedit_style())
        content.setText(
            """图像处理参数详解：

差分模式：
• 关闭：显示原始太赫兹图像
• 打开：减去参考帧，突出变化区域
• 校准文件：使用校准数据消除系统噪声
  * 需先运行校准模式采集背景数据
  * 校准文件保存在会话目录

插值方法：
• 无：保持原始64×64分辨率
• 最近邻：快速放大，可能有锯齿
• 双线性：平滑放大，平衡速度和质量
• 双三次：高质量放大，计算量稍大
• Lanczos：最佳质量，最慢

对比度/亮度：
• 对比度：1.0为原始值，>1.0增强对比
• 亮度：-100到+100，调整整体亮度

伪彩色：
• 将灰度图映射为彩色，增强视觉效果
• JET：彩虹色，缺陷对比最明显
• HOT：白热效果，适合高温区域
• HSV：色调饱和，适合相位检测

Gamma校正：
• 1.0：线性响应
• <1.0：提亮暗部，适合弱信号
• >1.0：压暗亮部，适合强信号

锐化/模糊：
• 锐化：增强边缘，突出缺陷边界
• 高斯模糊：平滑噪声，SNR>5时有效
• 双边滤波：保边平滑，保护缺陷边缘
• 中值滤波：去除椒盐噪声

边缘检测：
• Canny：经典边缘检测，双阈值
• Sobel：梯度检测，方向敏感
• Laplacian：二阶导数，对噪声敏感

累积帧数：
• 1：单帧显示，实时性好
• >1：多帧平均，提高SNR"""
        )
        layout.addWidget(content)

        layout.addStretch()
        return widget

    def _create_acquisition_tab(self):
        """创建采集操作标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("采集操作指南")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0066cc; margin-bottom: 10px;")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(_get_textedit_style())
        content.setText(
            """采集操作详细步骤：

开始采集前：
1. 确认连接正常，监听状态显示"监听中"
2. 确认无人机已就位，开始推送数据
3. 观察实时图像是否清晰
4. 调整图像处理参数至最佳状态

开始采集：
1. 点击"开始采集"按钮
2. 系统等待第一个有效坐标数据
3. 收到坐标后自动创建会话目录
4. 开始保存原始数据和处理后的图像

采集过程中：
• 实时显示当前帧数和总帧数
• 显示当前采集状态（采集中/待机）
• 实时更新无人机12维状态信息
• 自动保存每帧的原始数据和坐标
• 支持手动停止（再次点击采集按钮）

校准模式：
• 用于采集背景噪声数据
• 关闭太赫兹源，采集纯噪声
• 数据用于差分模式的"校准文件"选项
• 建议每个检测日校准一次

自动保存：
• 每帧保存两个文件：
  - PNG：处理后的图像
  - JSON：原始数据和完整坐标
• 会话目录命名规则：
  - 坐标_x_y_z_时间戳
  - 自动包含第一帧坐标信息

采集完成：
• 达到预设帧数自动停止
• 或手动点击停止采集
• 自动保存处理参数和日志
• 数据立即可用于回放

注意事项：
• 确保存储空间充足
• 网络中断会自动重连（如启用）
• 坐标重复时自动增大观测噪声
• 支持卡尔曼滤波坐标预测"""
        )
        layout.addWidget(content)
        layout.addStretch()
        return widget

    def _create_playback_tab(self):
        """创建回放分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("回放与分析")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0066cc; margin-bottom: 10px;")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(_get_textedit_style())
        content.setText(
            """回放与分析功能：

加载会话：
1. 点击"文件"→"打开会话"
2. 选择之前保存的会话文件夹
3. 自动加载所有帧和处理参数
4. 显示总帧数和会话信息

回放控制：
• 鼠标悬停显示播放控制条
• 点击播放/暂停按钮（▶/⏸）
• 拖动进度条跳转到指定帧
• 使用鼠标滚轮缩放图像
• 平移查看放大后的细节

坐标关联分析：
• 每帧显示对应的12维无人机状态
• 位置：x, y, z（米）
• 姿态：roll, pitch, yaw（度）
• 速度：vx, vy, vz（米/秒）
• 角速度：vroll, vpitch, vyaw（度/秒）
• 分析位置变化与缺陷检测的关系

图像对比：
• 切换不同的处理参数查看效果
• 差分模式可对比原始和去背景图像
• 累积帧功能可查看多帧平均效果

数据导出：
• 点击"文件"→"保存会话"
• 将当前会话复制到指定位置
• 保留所有原始数据和处理参数

快捷键：
• F1：打开操作说明
• F2：打开关于与支持
• Ctrl+O：打开会话
• Ctrl+S：保存会话
• Ctrl+D：恢复默认设置
• Ctrl+L：加载配置
• Ctrl+E：导出配置
• Ctrl+R：重启应用
• Ctrl+Q：退出应用

故障排除：
• 图像不显示：检查连接和差分模式
• 坐标不更新：检查推送端数据格式
• 回放卡顿：减少累积帧数
• 内存不足：定期清理旧会话数据"""
        )
        layout.addWidget(content)
        layout.addStretch()
        return widget