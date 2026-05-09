"""Spinner 动画 - 等待 AI 响应时显示"""

import sys
import threading
import time

# 旋转帧 (Braille 风格)
FRAMES = ['\u2801', '\u2803', '\u2807', '\u280f', '\u281f', '\u283f', '\u287f', '\u28ff']
# 点动画
DOTS = ['   ', '.  ', '.. ', '...']
# 脉冲
PULSE = ['\u25cb', '\u25d4', '\u25cf', '\u25d4']


class Spinner:
    """终端 spinner 动画"""

    def __init__(self, text="thinking", style="dots"):
        self.text = text
        self.style = style
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """启动 spinner (非阻塞)"""
        self._stop.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 spinner 并清除"""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        # 清除 spinner 行
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()

    def _animate(self):
        gray = "\033[38;5;245m"
        accent = "\033[38;5;141m"
        reset = "\033[0m"

        frames = DOTS if self.style == "dots" else PULSE
        i = 0
        while not self._stop.is_set():
            frame = frames[i % len(frames)]
            sys.stdout.write(f"\r  {gray}{frame}{reset} {accent}{self.text}{reset} ")
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.3)
