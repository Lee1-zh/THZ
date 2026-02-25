import numpy as np
import collections
from typing import Optional

from C import MAX_RECORDED_FRAMES, FRAME_HEIGHT, FRAME_WIDTH

# -------------------- 帧缓存 --------------------
class FrameBuffer:
    def __init__(self, max_size: int = MAX_RECORDED_FRAMES):
        self.buffer: collections.deque[np.ndarray] = collections.deque(maxlen=max_size)
        self.reference_frame: Optional[np.ndarray] = None

    def add_frame(self, frame: np.ndarray):
        self.buffer.append(frame)

    def get_accumulated_frame(self, accumulate_count: int) -> np.ndarray:
        if accumulate_count <= 1 or not self.buffer:
            return self.buffer[-1] if self.buffer else np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)
        count = min(accumulate_count, len(self.buffer))
        return np.mean(list(self.buffer)[-count:], axis=0).astype(np.uint8)

    def set_reference(self, frame: np.ndarray):
        self.reference_frame = frame.copy()

    def clear(self):
        self.buffer.clear()
        self.reference_frame = None