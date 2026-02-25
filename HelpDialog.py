# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPushButton, QTextEdit, QTabWidget, QMessageBox, QLabel, QDialog)
from PySide6.QtCore import (Qt)

from C import _get_groupbox_style, _get_button_style, _get_textedit_style

class HelpDialog(QDialog):
    """帮助与支持对话框，显示软件信息、技术支持和授权详情"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于与支持")
        self.setMinimumSize(650, 450)
        self.setWindowFlags(Qt.Tool)  # 设置为工具窗口，非模态
        self._setup_ui()

    def _setup_ui(self):
        """设置对话框界面"""
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
        # 关于页面
        about_widget = self._create_about_tab()
        tab_widget.addTab(about_widget, "关于")
        # 技术支持页面
        support_widget = self._create_support_tab()
        tab_widget.addTab(support_widget, "技术支持")
        # 授权信息页面
        license_widget = self._create_license_tab()
        tab_widget.addTab(license_widget, "授权信息")
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

    def _create_about_tab(self):
        """创建关于页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        # Logo和公司名称
        logo_label = QLabel("T-Waves Inspector™")
        logo_label.setStyleSheet("""
            font-size: 28px; 
            font-weight: bold; 
            color: #0066cc;
            margin-bottom: 10px;
        """)
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        subtitle_label = QLabel("风电叶片太赫兹智能检测系统")
        subtitle_label.setStyleSheet("font-size: 16px; color: #666666;")
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)
        version_label = QLabel("版本: v1.0.0")
        version_label.setStyleSheet("font-size: 14px; color: #999999; margin-bottom: 20px;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        layout.addSpacing(20)
        # 公司信息
        company_group = QGroupBox("公司信息")
        company_group.setStyleSheet(_get_groupbox_style())
        company_layout = QVBoxLayout()
        company_name = QLabel("安徽中科太赫兹科技有限公司")
        company_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        company_layout.addWidget(company_name)
        website_label = QLabel('官方网站: <a href="https://www.t-waves.cn/" style="color: #0066cc;">www.t-waves.com</a>')
        website_label.setOpenExternalLinks(True)
        website_label.setStyleSheet("font-size: 14px; color: #333333;")
        company_layout.addWidget(website_label)
        company_group.setLayout(company_layout)
        layout.addWidget(company_group)
        # 功能简介
        desc_group = QGroupBox("系统简介")
        desc_group.setStyleSheet(_get_groupbox_style())
        desc_layout = QVBoxLayout()
        desc_text = QTextEdit()
        desc_text.setReadOnly(True)
        desc_text.setStyleSheet(_get_textedit_style())
        desc_text.setText(
            "T-Waves Inspector™ 是一款专为风电叶片检测设计的太赫兹智能成像系统。\n\n"
            "主要功能特点：\n"
            "• 实时太赫兹成像采集与显示\n"
            "• 12维无人机状态实时监控\n"
            "• 卡尔曼滤波坐标预测\n"
            "• 图像差分、增强与伪彩色处理\n"
            "• 自动会话管理与数据保存\n\n"
            "适用于风电叶片内部缺陷检测、结构健康监测等应用场景。"
        )
        desc_layout.addWidget(desc_text)
        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)
        # 版权信息
        copyright_label = QLabel("© 2026 安徽中科太赫兹科技有限公司 版权所有")
        copyright_label.setStyleSheet("font-size: 12px; color: #999999; margin-top: 20px;")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
        layout.addStretch()
        return widget

    def _create_support_tab(self):
        """创建技术支持页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        # 技术支持标题
        support_title = QLabel("技术支持")
        support_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333333; margin-bottom: 20px;")
        layout.addWidget(support_title)
        # 热线
        hotline_group = QGroupBox("技术支持热线")
        hotline_group.setStyleSheet(_get_groupbox_style())
        hotline_layout = QVBoxLayout()
        hotline_number = QLabel("400-888-XXXX")
        hotline_number.setStyleSheet("font-size: 18px; color: #f44336; font-weight: bold;")
        hotline_layout.addWidget(hotline_number)
        hotline_note = QLabel("工作时间: 周一至周五 9:00-18:00")
        hotline_note.setStyleSheet("font-size: 12px; color: #666666;")
        hotline_layout.addWidget(hotline_note)
        hotline_group.setLayout(hotline_layout)
        layout.addWidget(hotline_group)
        # 邮箱
        email_group = QGroupBox("技术支持邮箱")
        email_group.setStyleSheet(_get_groupbox_style())
        email_layout = QVBoxLayout()
        email_address = QLabel("support@t-waves.com")
        email_address.setStyleSheet("font-size: 16px; color: #0066cc; font-weight: bold;")
        email_layout.addWidget(email_address)
        email_note = QLabel("24小时内响应，工作日2小时内响应")
        email_note.setStyleSheet("font-size: 12px; color: #666666;")
        email_layout.addWidget(email_note)
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)
        # 在线支持
        online_group = QGroupBox("在线技术支持")
        online_group.setStyleSheet(_get_groupbox_style())
        online_layout = QVBoxLayout()
        online_info = QLabel(
            '访问 <a href="http://support.t-waves.com" style="color: #0066cc;">在线支持中心</a> 获取：'
        )
        online_info.setOpenExternalLinks(True)
        online_info.setStyleSheet("font-size: 14px; color: #333333;")
        online_layout.addWidget(online_info)
        online_list = QTextEdit()
        online_list.setReadOnly(True)
        online_list.setStyleSheet(_get_textedit_style())
        online_list.setText(
            "• 技术文档与操作手册\n"
            "• 常见问题解答(FAQ)\n"
            "• 软件更新与补丁下载\n"
            "• 在线技术支持聊天"
        )
        online_list.setMaximumHeight(100)
        online_layout.addWidget(online_list)
        online_group.setLayout(online_layout)
        layout.addWidget(online_group)
        # 远程协助
        remote_group = QGroupBox("远程协助")
        remote_group.setStyleSheet(_get_groupbox_style())
        remote_layout = QVBoxLayout()
        remote_info = QLabel("如需远程协助，请拨打热线预约远程支持服务")
        remote_info.setStyleSheet("font-size: 14px; color: #333333;")
        remote_layout.addWidget(remote_info)
        remote_btn = QPushButton("生成远程协助代码")
        remote_btn.setStyleSheet(_get_button_style())
        remote_btn.setFixedWidth(150)
        remote_btn.clicked.connect(self._generate_remote_code)
        remote_layout.addWidget(remote_btn)
        remote_group.setLayout(remote_layout)
        layout.addWidget(remote_group)
        layout.addStretch()
        return widget

    def _create_license_tab(self):
        """创建授权信息页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        # 授权信息标题
        license_title = QLabel("授权信息")
        license_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333333; margin-bottom: 20px;")
        layout.addWidget(license_title)
        # 授权类型
        license_group = QGroupBox("授权详情")
        license_group.setStyleSheet(_get_groupbox_style())
        license_layout = QGridLayout()
        license_layout.setSpacing(12)
        # 授权类型
        license_layout.addWidget(QLabel("授权类型:"), 0, 0)
        license_type = QLabel("专业版")
        license_type.setStyleSheet("font-size: 16px; color: #4CAF50; font-weight: bold;")
        license_layout.addWidget(license_type, 0, 1)
        # 激活状态
        license_layout.addWidget(QLabel("激活状态:"), 1, 0)
        status = QLabel("已激活 ✓")
        status.setStyleSheet("font-size: 16px; color: #4CAF50; font-weight: bold;")
        license_layout.addWidget(status, 1, 1)
        # 授权到期时间
        license_layout.addWidget(QLabel("授权到期时间:"), 2, 0)
        expiry_date = QLabel("2026-12-31")
        expiry_date.setStyleSheet("font-size: 16px; color: #f44336; font-weight: bold;")
        license_layout.addWidget(expiry_date, 2, 1)
        # 设备ID
        license_layout.addWidget(QLabel("设备ID:"), 3, 0)
        device_id = QLabel("TW-2026-001234-5678")
        device_id.setStyleSheet("font-size: 14px; color: #333333; font-family: monospace;")
        license_layout.addWidget(device_id, 3, 1)
        license_group.setLayout(license_layout)
        layout.addWidget(license_group)
        # 授权功能
        features_group = QGroupBox("授权功能")
        features_group.setStyleSheet(_get_groupbox_style())
        features_layout = QVBoxLayout()
        features_text = QTextEdit()
        features_text.setReadOnly(True)
        features_text.setStyleSheet(_get_textedit_style())
        features_text.setText(
            "当前授权包含以下功能：\n\n"
            "✓ 实时太赫兹图像采集\n"
            "✓ 12维无人机状态监控\n"
            "✓ 卡尔曼滤波坐标预测\n"
            "✓ 高级图像处理 (差分/增强/伪彩)\n"
            "✓ 自动会话管理与数据保存\n"
            "✓ 历史数据回放与分析\n"
            "✓ 校准模式支持\n"
            "✓ 远程技术支持\n\n"
            "如需升级授权或获取更多信息，请联系销售部门。"
        )
        features_layout.addWidget(features_text)
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        # 提醒
        reminder_label = QLabel("⚠ 您的授权将于 2026-12-31 到期")
        reminder_label.setStyleSheet("font-size: 12px; color: #ff9800; font-weight: bold; padding: 10px; "
                                     "background-color: #fff3cd; border-radius: 4px; margin-top: 20px;")
        reminder_label.setWordWrap(True)
        layout.addWidget(reminder_label)
        layout.addStretch()
        return widget

    def _generate_remote_code(self):
        """生成远程协助代码（示例实现）"""
        import random
        import string
        # 生成8位随机码
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # 显示代码
        QMessageBox.information(
            self,
            "远程协助代码",
            f"您的远程协助代码为：\n\n<b>{code}</b>\n\n"
            f"请将此代码提供给技术支持工程师。\n"
            f"代码有效期为30分钟。",
            QMessageBox.Ok
        )