# -*- coding: utf-8 -*-
import numpy as np
import cv2
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from C import sanitize_path, create_session_folder, LOG_ERROR, LOG_INFO, SESSION_PARAMS_FILE

class DataSaver:
    def __init__(self, base_path: Path):
        self.base_path = Path(sanitize_path(str(base_path)))
        self.current_session_path: Optional[Path] = None
        self.log_messages: List[Dict[str, Any]] = []
        self.processing_params: Dict[str, Any] = {}

    def set_processing_params(self, params: Dict[str, Any]):
        """设置图像处理参数"""
        self.processing_params = params.copy()

    def log(self, module: str, message: str, level: int = LOG_INFO):
        timestamp = datetime.now().isoformat()
        self.log_messages.append({"timestamp": timestamp, "module": module, "level": level, "message": message})

    def start_session(self, coords: np.ndarray, params: Dict[str, Any]) -> bool:
        """启动新会话，创建文件夹"""
        try:
            self.current_session_path = create_session_folder(coords, self.base_path, params)
            self.log("保存", f"会话已启动: {self.current_session_path}", LOG_INFO)
            return True
        except Exception as e:
            self.log("保存", f"创建会话失败: {e}", LOG_ERROR)
            return False

    def save_frame(self, processed_img: np.ndarray, raw_data: np.ndarray, frame_num: int,
                   coords: np.ndarray, fps: float) -> bool:
        """保存帧数据，包含完整的12维坐标信息和推送端FPS（与PNG同目录）"""
        if not self.current_session_path:
            return False
        try:
            # 保存PNG图像
            png_path = self.current_session_path / f"frame_{frame_num:06d}.png"
            is_success, buffer = cv2.imencode('.png', processed_img)
            if is_success:
                with open(png_path, 'wb') as f:
                    f.write(buffer.tobytes())
            # 保存原始数据和完整坐标信息的JSON（与PNG同目录）
            raw_data_path = self.current_session_path / f"frame_{frame_num:06d}_raw.json"
            # 准备完整的元数据
            coord_data = {
                "position": {
                    "x": float(coords[0]),
                    "y": float(coords[1]),
                    "z": float(coords[2])
                },
                "attitude": {
                    "roll": float(coords[3]),
                    "pitch": float(coords[4]),
                    "yaw": float(coords[5])
                },
                "velocity": {
                    "vx": float(coords[6]),
                    "vy": float(coords[7]),
                    "vz": float(coords[8])
                },
                "angular_velocity": {
                    "vroll": float(coords[9]),
                    "vpitch": float(coords[10]),
                    "vyaw": float(coords[11])
                }
            }
            json_data = {
                "frame_number": frame_num,
                "timestamp": datetime.now().isoformat(),
                "coordinates": coord_data,
                "push_fps": fps,  # 添加推送端FPS信息
                "raw_data": raw_data.tolist(),
                "shape": raw_data.shape,
                "dtype": str(raw_data.dtype)
            }
            with open(raw_data_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            if frame_num % 10 == 0:
                self.log("保存", f"已保存帧 {frame_num:06d}", LOG_INFO)
            return True
        except Exception as e:
            self.log("保存", f"保存帧失败: {e}", LOG_ERROR)
            return False

    def save_calibration_file(self, all_frames: List[np.ndarray], base_path: Path) -> bool:
        """保存校准文件（平均帧）- 修复路径问题"""
        try:
            if not all_frames:
                return False
            # 计算所有帧的平均值
            avg_frame = np.mean(all_frames, axis=0).astype(np.uint8)
            # 保存为与base_path文件夹同名的文件，保存在base_path目录下
            folder_name = base_path.name
            json_path = base_path / f"{folder_name}.json"
            png_path = base_path / f"{folder_name}.png"
            # 保存JSON（包含平均数据）
            json_data = {
                "timestamp": datetime.now().isoformat(),
                "average_data": avg_frame.tolist(),
                "shape": avg_frame.shape,
                "dtype": str(avg_frame.dtype)
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            # 保存PNG（无图像处理效果）
            is_success, buffer = cv2.imencode('.png', avg_frame)
            if is_success:
                with open(png_path, 'wb') as f:
                    f.write(buffer.tobytes())
            return True
        except Exception as e:
            self.log("保存", f"保存校准文件失败: {e}", LOG_ERROR)
            return False

    def end_session(self) -> bool:
        """结束会话，保存日志和处理参数（与PNG同目录）"""
        try:
            if self.current_session_path:
                # 保存处理参数
                params_path = self.current_session_path / SESSION_PARAMS_FILE
                with open(params_path, 'w', encoding='utf-8') as f:
                    json.dump(self.processing_params, f, ensure_ascii=False, indent=2)
                # 保存日志
                log_file_path = self.current_session_path / "session_log.json"
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.log_messages, f, ensure_ascii=False, indent=2)
                self.log("保存", f"会话已结束，日志保存到: {log_file_path}", LOG_INFO)
                return True
        except Exception as e:
            self.log("保存", f"结束会话失败: {e}", LOG_ERROR)
            return False
        finally:
            self.current_session_path = None
            self.log_messages.clear()
            self.processing_params.clear()
        return False