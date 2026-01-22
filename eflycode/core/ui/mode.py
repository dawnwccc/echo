"""Composer 工作模式管理

定义 5 种工作模式及其颜色、切换逻辑
"""

from enum import Enum
from typing import Callable, List, Dict
import logging

logger = logging.getLogger(__name__)


class ComposerMode(str, Enum):
    """Composer 工作模式枚举"""

    DEFAULT = "Default"
    PLAN = "Plan"
    BUILD = "Build"
    DEBUG = "Debug"
    ASK = "Ask"

    @property
    def color_style(self) -> str:
        """获取模式对应的颜色样式类名"""
        return f"composer.mode.{self.value.lower()}"

    @property
    def ansi_color(self) -> str:
        """获取模式对应的 ANSI 颜色"""
        return _MODE_COLORS[self]

    @property
    def label(self) -> str:
        """获取模式显示标签"""
        return f"[{self.value}]"


# 模式颜色配置（用于样式定义）
_MODE_COLORS: Dict[ComposerMode, str] = {
    ComposerMode.DEFAULT: "ansiwhite",
    ComposerMode.PLAN: "ansiyellow",
    ComposerMode.BUILD: "ansigreen",
    ComposerMode.DEBUG: "ansired",
    ComposerMode.ASK: "ansiblue",
}

# 模式切换顺序
_MODE_CYCLE: List[ComposerMode] = [
    ComposerMode.DEFAULT,
    ComposerMode.PLAN,
    ComposerMode.BUILD,
    ComposerMode.DEBUG,
    ComposerMode.ASK,
]


class ModeManager:
    """模式管理器

    管理当前工作模式，提供模式切换、回调通知和持久化功能
    """

    def __init__(self, initial_mode: ComposerMode = ComposerMode.DEFAULT):
        """初始化模式管理器

        Args:
            initial_mode: 初始模式
        """
        self._current_mode = initial_mode
        self._mode_change_callbacks: List[Callable[[ComposerMode, ComposerMode], None]] = []

    @property
    def current_mode(self) -> ComposerMode:
        """获取当前模式"""
        return self._current_mode

    def set_mode(self, mode: ComposerMode) -> None:
        """设置当前模式

        Args:
            mode: 要设置的模式
        """
        if self._current_mode != mode:
            old_mode = self._current_mode
            self._current_mode = mode
            self._notify_mode_change(old_mode, mode)
            logger.debug(f"Mode changed: {old_mode.value} → {mode.value}")

    def next_mode(self) -> ComposerMode:
        """切换到下一个模式（循环）

        Returns:
            切换后的模式
        """
        current_index = _MODE_CYCLE.index(self._current_mode)
        next_index = (current_index + 1) % len(_MODE_CYCLE)
        new_mode = _MODE_CYCLE[next_index]
        self.set_mode(new_mode)
        return new_mode

    def register_change_callback(
        self,
        callback: Callable[[ComposerMode, ComposerMode], None]
    ) -> None:
        """注册模式变化回调函数

        Args:
            callback: 回调函数，签名为 (old_mode, new_mode) -> None
        """
        self._mode_change_callbacks.append(callback)

    def _notify_mode_change(
        self,
        old_mode: ComposerMode,
        new_mode: ComposerMode
    ) -> None:
        """通知所有注册的回调函数模式已变化"""
        for callback in self._mode_change_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}", exc_info=True)
