import numpy as np
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from C import LOG_ERROR, LOG_INFO, SESSION_PARAMS_FILE, COORD_DIMENSION, create_save_session_folder

# -------------------- SessionManager 会话管理器 --------------------
class SessionManager:
    """会话管理器：负责加载和保存会话（兼容原始结构）"""
    def __init__(self, parent_window: 'TerahertzDetectorUI'):
        self.parent = parent_window

    def open_session(self, session_path: Path) -> bool:
        """打开会话文件夹（兼容原始结构）"""
        try:
            if not session_path.is_dir():
                self.parent._log("会话", "无效会话文件夹路径", LOG_ERROR)
                return False
            # 读取处理参数
            params_path = session_path / SESSION_PARAMS_FILE
            if not params_path.exists():
                self.parent._log("会话", "未找到处理参数文件", LOG_ERROR)
                return False
            with open(params_path, 'r', encoding='utf-8') as f:
                processing_params = json.load(f)
            # 应用到图像处理界面
            self._apply_processing_params(processing_params)
            # 读取所有帧和坐标数据（从原始结构）
            frames = []
            coords = []
            fps_values = []
            # 查找所有raw_data文件
            raw_files = sorted(session_path.glob("frame_*_raw.json"))
            if not raw_files:
                self.parent._log("会话", "未找到帧数据文件", LOG_ERROR)
                return False
            for raw_file in raw_files:
                # 读取原始数据
                with open(raw_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    frame_array = np.array(raw_data['raw_data'], dtype=np.uint8)
                    frames.append(frame_array)
                    # 获取坐标数据
                    coord_info = raw_data['coordinates']
                    full_coord = np.zeros(COORD_DIMENSION)
                    full_coord[0] = coord_info['position']['x']
                    full_coord[1] = coord_info['position']['y']
                    full_coord[2] = coord_info['position']['z']
                    full_coord[3] = coord_info['attitude']['roll']
                    full_coord[4] = coord_info['attitude']['pitch']
                    full_coord[5] = coord_info['attitude']['yaw']
                    full_coord[6] = coord_info['velocity']['vx']
                    full_coord[7] = coord_info['velocity']['vy']
                    full_coord[8] = coord_info['velocity']['vz']
                    full_coord[9] = coord_info['angular_velocity']['vroll']
                    full_coord[10] = coord_info['angular_velocity']['vpitch']
                    full_coord[11] = coord_info['angular_velocity']['vyaw']
                    coords.append(full_coord)
                    # 获取FPS
                    fps_values.append(raw_data.get('push_fps', 30.0))

            if not frames or not coords:
                self.parent._log("会话", "未找到有效的帧或坐标数据", LOG_ERROR)
                return False
            # 设置到回放控制器
            self.parent.playback_controller.set_session_data(frames, coords, fps_values)
            # 更新UI
            self.parent.image_label.setText(
                f"<span style='color:#999999; font-size:14px;'>会话已加载: {session_path.name}</span>")
            self.parent.record_btn.setEnabled(True)  # 启用采集按钮，允许替换会话
            self.parent._log("会话", f"成功加载会话: {session_path.name}, 共 {len(frames)} 帧", LOG_INFO)
            return True
        except Exception as e:
            self.parent._log("会话", f"加载会话失败: {e}", LOG_ERROR)
            return False

    def save_session(self, target_path: Path, frames: List[np.ndarray], coords: List[np.ndarray],
                     fps_values: List[float], processing_params: Dict[str, Any],
                     log_messages: List[Dict[str, Any]]) -> bool:
        """保存当前会话到目标文件夹（使用第一帧坐标命名，兼容原始结构）"""
        try:
            if not frames or not coords:
                self.parent._log("会话", "没有有效的数据可保存", LOG_ERROR)
                return False
            # 使用第一帧坐标创建会话文件夹
            first_coord = coords[0] if coords else np.zeros(COORD_DIMENSION)
            session_path = create_save_session_folder(first_coord, target_path)
            # 保存处理参数
            params_path = session_path / SESSION_PARAMS_FILE
            with open(params_path, 'w', encoding='utf-8') as f:
                json.dump(processing_params, f, ensure_ascii=False, indent=2)
            # 保存帧和坐标数据（与PNG同目录）
            for i, (frame, coord, fps) in enumerate(zip(frames, coords, fps_values)):
                # 保存原始数据和坐标（单个JSON）
                raw_data_path = session_path / f"frame_{i:06d}_raw.json"
                raw_json = {
                    "frame_number": i,
                    "timestamp": datetime.now().isoformat(),
                    "coordinates": {
                        "position": {"x": float(coord[0]), "y": float(coord[1]), "z": float(coord[2])},
                        "attitude": {"roll": float(coord[3]), "pitch": float(coord[4]), "yaw": float(coord[5])},
                        "velocity": {"vx": float(coord[6]), "vy": float(coord[7]), "vz": float(coord[8])},
                        "angular_velocity": {"vroll": float(coord[9]), "vpitch": float(coord[10]),
                                             "vyaw": float(coord[11])}
                    },
                    "push_fps": float(fps),
                    "raw_data": frame.tolist(),
                    "shape": frame.shape,
                    "dtype": str(frame.dtype)
                }
                with open(raw_data_path, 'w', encoding='utf-8') as f:
                    json.dump(raw_json, f, ensure_ascii=False, indent=2)
            # 保存日志
            log_path = session_path / "session_log.json"
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_messages, f, ensure_ascii=False, indent=2)
            self.parent._log("会话", f"会话已保存到: {session_path}", LOG_INFO)
            return True
        except Exception as e:
            self.parent._log("会话", f"保存会话失败: {e}", LOG_ERROR)
            return False

    def _apply_processing_params(self, params: Dict[str, Any]):
        """将处理参数应用到UI"""
        pd = self.parent.processing_dialog
        # 插值方法
        if 'interpolation' in params:
            pd.interpolation_combo.setCurrentText(params['interpolation'])
        # 对比度
        if 'contrast' in params:
            contrast_value = int(params['contrast'] * 100)
            pd.contrast_slider.setValue(contrast_value)
        # 亮度
        if 'brightness' in params:
            pd.brightness_slider.setValue(params['brightness'])
        # 伪彩色
        if 'colormap' in params:
            pd.colormap_combo.setCurrentText(params['colormap'])
        # Gamma
        if 'gamma' in params:
            gamma_value = int(params['gamma'] * 100)
            pd.gamma_slider.setValue(gamma_value)
        # 锐化
        if 'sharpen' in params:
            sharpen_value = int(params['sharpen'] * 10)
            pd.sharpen_slider.setValue(sharpen_value)
        # 高斯模糊
        if 'gaussian_blur' in params:
            blur_value = int(params['gaussian_blur'] * 10)
            pd.gaussian_blur_slider.setValue(blur_value)
        # 双边滤波
        if 'bilateral_filter' in params:
            pd.bilateral_filter_slider.setValue(params['bilateral_filter'])
        # 中值滤波
        if 'use_median' in params:
            pd.median_check.setChecked(params['use_median'])
        # 边缘检测
        if 'edge_detection' in params:
            pd.edge_detection_combo.setCurrentText(params['edge_detection'])
        # 差分模式
        if 'diff_mode' in params:
            pd.diff_combo.setCurrentText(params['diff_mode'])
        # 累积帧数
        if 'accumulate' in params:
            pd.accumulate_slider.setValue(params['accumulate'])

        # ==================== 应用高级处理参数 ====================
        # 高级处理启用状态
        if 'advanced_enable' in params:
            pd.advanced_enable_check.setChecked(params['advanced_enable'])