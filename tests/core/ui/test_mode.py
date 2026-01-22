"""测试 Composer 工作模式管理"""

import pytest

from eflycode.core.ui.mode import ComposerMode, ModeManager


class TestComposerMode:
    """测试 ComposerMode 枚举"""

    def test_mode_values(self):
        """测试模式值"""
        assert ComposerMode.DEFAULT.value == "Default"
        assert ComposerMode.PLAN.value == "Plan"
        assert ComposerMode.BUILD.value == "Build"
        assert ComposerMode.DEBUG.value == "Debug"
        assert ComposerMode.ASK.value == "Ask"

    def test_mode_labels(self):
        """测试模式标签"""
        assert ComposerMode.DEFAULT.label == "[Default]"
        assert ComposerMode.PLAN.label == "[Plan]"
        assert ComposerMode.BUILD.label == "[Build]"
        assert ComposerMode.DEBUG.label == "[Debug]"
        assert ComposerMode.ASK.label == "[Ask]"

    def test_mode_color_styles(self):
        """测试颜色样式"""
        assert ComposerMode.DEFAULT.color_style == "composer.mode.default"
        assert ComposerMode.PLAN.color_style == "composer.mode.plan"
        assert ComposerMode.BUILD.color_style == "composer.mode.build"
        assert ComposerMode.DEBUG.color_style == "composer.mode.debug"
        assert ComposerMode.ASK.color_style == "composer.mode.ask"

    def test_ansi_colors(self):
        """测试 ANSI 颜色"""
        assert ComposerMode.DEFAULT.ansi_color == "ansiwhite"
        assert ComposerMode.PLAN.ansi_color == "ansiyellow"
        assert ComposerMode.BUILD.ansi_color == "ansigreen"
        assert ComposerMode.DEBUG.ansi_color == "ansired"
        assert ComposerMode.ASK.ansi_color == "ansiblue"


class TestModeManager:
    """测试 ModeManager 类"""

    def test_initial_mode(self):
        """测试初始模式"""
        manager = ModeManager(initial_mode=ComposerMode.DEFAULT)
        assert manager.current_mode == ComposerMode.DEFAULT

    def test_set_mode(self):
        """测试设置模式"""
        manager = ModeManager()
        manager.set_mode(ComposerMode.BUILD)
        assert manager.current_mode == ComposerMode.BUILD

    def test_next_mode(self):
        """测试模式切换顺序"""
        manager = ModeManager(initial_mode=ComposerMode.DEFAULT)

        # 按顺序切换
        assert manager.next_mode() == ComposerMode.PLAN
        assert manager.next_mode() == ComposerMode.BUILD
        assert manager.next_mode() == ComposerMode.DEBUG
        assert manager.next_mode() == ComposerMode.ASK
        assert manager.next_mode() == ComposerMode.DEFAULT  # 循环回 Default

    def test_mode_change_callback(self):
        """测试模式变化回调"""
        manager = ModeManager()
        called = []

        def callback(old, new):
            called.append((old, new))

        manager.register_change_callback(callback)
        manager.set_mode(ComposerMode.PLAN)

        assert len(called) == 1
        assert called[0] == (ComposerMode.DEFAULT, ComposerMode.PLAN)

    def test_no_callback_on_same_mode(self):
        """测试设置相同模式时不触发回调"""
        manager = ModeManager(initial_mode=ComposerMode.DEFAULT)
        called = []

        def callback(old, new):
            called.append((old, new))

        manager.register_change_callback(callback)
        manager.set_mode(ComposerMode.DEFAULT)  # 设置相同模式

        assert len(called) == 0  # 不应触发回调

    def test_multiple_callbacks(self):
        """测试多个回调函数"""
        manager = ModeManager()
        called1 = []
        called2 = []

        def callback1(old, new):
            called1.append((old, new))

        def callback2(old, new):
            called2.append((old, new))

        manager.register_change_callback(callback1)
        manager.register_change_callback(callback2)
        manager.set_mode(ComposerMode.ASK)

        assert len(called1) == 1
        assert len(called2) == 1
        assert called1[0] == (ComposerMode.DEFAULT, ComposerMode.ASK)
        assert called2[0] == (ComposerMode.DEFAULT, ComposerMode.ASK)
