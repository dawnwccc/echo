import asyncio
from typing import Awaitable, Callable, List, Optional, Union

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import CompletionsMenu, Layout
from prompt_toolkit.layout.containers import (
    Float,
    FloatContainer,
    HSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from eflycode.core.ui.style import build_prompt_toolkit_style
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.mode import ComposerMode, ModeManager
from eflycode.cli.components.smart_completer import SmartCompleter

def build_get_line_prefix(
    prompt_text: str,
    busy_prompt_text: str,
    get_prompt_width: Callable[[], int],
    on_busy: Optional[Callable[[], bool]] = None,
) -> Callable[[int, int], FormattedText]:
    def _get_line_prefix(line_number: int, wrap_count: int) -> FormattedText:
        prompt = prompt_text
        if on_busy is not None and on_busy():
            prompt = busy_prompt_text
        if line_number == 0:
            return FormattedText([("class:composer.prompt", prompt)])
        return FormattedText([("class:composer.prompt", " " * get_prompt_width())])
    return _get_line_prefix

def build_get_line_prefix_width(
    prompt_text: str,
    busy_prompt_text: str,
    on_busy: Optional[Callable[[], bool]] = None,
) -> int:
    def _get_line_prefix_width() -> int:
        prompt = prompt_text
        if on_busy is not None and on_busy():
            prompt = busy_prompt_text
        return len(prompt)
    return _get_line_prefix_width

def build_placeholder_visible(buffer: Buffer) -> Callable[[], bool]:
    def _placeholder_visible() -> bool:
        return buffer.text.strip() == ""
    return _placeholder_visible


class ComposerComponent:

    def __init__(
        self,
        agent_factory: Optional['AgentFactory'] = None,
        app_context: Optional['ApplicationContext'] = None,
    ) -> None:
        self._completer = SmartCompleter()
        self._mode_manager = ModeManager(initial_mode=ComposerMode.DEFAULT)
        self._agent_factory = agent_factory
        self._app_context = app_context
        self._toolbar_text = None
        self._statusbar_control = None  # 状态栏控件，用于刷新

        # 同步初始模式
        if app_context and app_context.current_agent:
            try:
                current_mode = ComposerMode(app_context.current_agent.ROLE)
                self._mode_manager.set_mode(current_mode)
            except ValueError:
                # 如果 ROLE 不是有效的 ComposerMode，使用默认值
                pass

    def get_completer(self) -> SmartCompleter:
        return self._completer

    @property
    def mode_manager(self) -> ModeManager:
        """获取模式管理器"""
        return self._mode_manager

    def _build_statusbar_text(self) -> FormattedText:
        """构建状态栏文本

        左侧显示当前模式（带颜色），右侧显示工具栏文本

        Returns:
            FormattedText: 状态栏格式化文本
        """
        try:
            mode = self._mode_manager.current_mode
            # 使用 ANSI 颜色值
            mode_style = f"{mode.ansi_color} bold"

            # 左侧：模式标签
            fragments = [
                (mode_style, f" {mode.label} "),
            ]

            # 右侧：工具栏文本（如果有）
            if self._toolbar_text:
                # 添加分隔符和工具栏文本
                fragments.append(("#5A5A5A", "  "))
                fragments.append(("#5A5A5A", str(self._toolbar_text)))

            return FormattedText(fragments)
        except Exception as e:
            # 如果出错，返回简单的文本
            logger.error(f"Error building statusbar text: {e}")
            return FormattedText([("", " [Error] ")])

    def _refresh_statusbar(self) -> None:
        """刷新状态栏显示

        重新构建状态栏文本并更新控件
        """
        if self._statusbar_control:
            # 重新获取文本
            new_text = self._build_statusbar_text()
            # 直接更新 FormattedText 对象
            self._statusbar_control.text = new_text

    def _on_mode_changed(
        self,
        old_mode: ComposerMode,
        new_mode: ComposerMode
    ) -> None:
        """模式变化时的回调函数

        Args:
            old_mode: 旧模式
            new_mode: 新模式
        """
        # 触发 ApplicationContext 的 Agent 切换
        if self._app_context:
            self._app_context.switch_agent_mode(new_mode)

        # 刷新状态栏
        self._refresh_statusbar()

    async def show(
        self,
        *,
        prompt_text: str = "> ",
        busy_prompt_text: str = "> ",
        placeholder: str = "share your ideas...",
        toolbar_text: Optional[str] = None,
        multiline: bool = True,
        min_height: int = 1,
        max_height: int = 20,
        completer: Optional[Completer] = None,
        on_complete: Optional[Union[Callable[[str], bool], Callable[[str], Awaitable[bool]]]] = None,
        on_busy: Optional[Callable[[], bool]] = None,
        # 新增参数
        initial_mode: ComposerMode = ComposerMode.DEFAULT,
    ) -> str:
        completer = completer or self._completer
        if on_complete is None:
            on_complete = self._completer.handle_command_async

        # 保存工具栏文本
        self._toolbar_text = toolbar_text

        # 设置初始模式
        self._mode_manager.set_mode(initial_mode)

        # 注册模式变化回调
        self._mode_manager.register_change_callback(self._on_mode_changed)

        buffer = Buffer(
            completer=completer,
            multiline=multiline,
            complete_while_typing=False,
        )
        if completer is not None:
            def _on_text_changed(_):
                text = buffer.text.strip()
                last_token = text.rsplit(" ", 1)[-1] if text else ""
                if not last_token.startswith(("/", "#", "@")):
                    if buffer.complete_state:
                        buffer.cancel_completion()
                    return
                if buffer.complete_state and buffer.complete_state.completions:
                    return
                buffer.start_completion(select_first=False)
            buffer.on_text_changed += _on_text_changed
        get_prompt_width = build_get_line_prefix_width(prompt_text, busy_prompt_text, on_busy)

        input_window = Window(
            content=BufferControl(buffer=buffer),
            height=Dimension(min=min_height, max=max_height),
            wrap_lines=True,
            dont_extend_height=True,
            get_line_prefix=build_get_line_prefix(prompt_text, busy_prompt_text, get_prompt_width, on_busy),
        )
        placeholder_float = Float(
            left=get_prompt_width(),
            top=0,
            hide_when_covering_content=True,
            content=Window(
                content=FormattedTextControl(
                    lambda: FormattedText([("class:composer.placeholder", placeholder)])
                ),
                height=1,
                dont_extend_height=True,
            ),
        )
        completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=CompletionsMenu(
                scroll_offset=1,
                extra_filter=has_focus(buffer),
            )
        )

        # 创建状态栏窗口
        initial_statusbar_text = self._build_statusbar_text()
        self._statusbar_control = FormattedTextControl(
            text=initial_statusbar_text
        )

        statusbar_window = Window(
            content=self._statusbar_control,
            height=1,
            dont_extend_height=True,
        )

        kb = KeyBindings()

        @kb.add(Keys.Enter)
        def _on_enter(event: KeyPressEvent):
            if event.current_buffer.complete_state:
                state = event.current_buffer.complete_state
                completion = state.current_completion
                if completion is None and state.completions:
                    completion = state.completions[0]
                if completion is not None:
                    event.current_buffer.apply_completion(completion)
                    return
            event.current_buffer.insert_text("\n")
        
        @kb.add(Keys.ControlM)
        def _on_submit(event: KeyPressEvent):
            text = event.current_buffer.text.strip()
            # 检查是否是命令，以 / 开头
            if text.startswith("/"):
                # 处理命令
                if on_complete:
                    # 异步命令在外层处理，避免嵌套 prompt_toolkit 应用导致 UI 残留
                    if asyncio.iscoroutinefunction(on_complete):
                        event.app.exit(result=text)
                        return
                    # 同步回调
                    handled = on_complete(text)
                    if handled:
                        # 命令已处理，退出并返回空字符串，让主循环继续
                        event.app.exit(result="")
                        return
            # 普通输入，退出并返回结果
            event.app.exit(result=text)
        
        @kb.add(Keys.Tab)
        def _on_tab(event: KeyPressEvent):
            if completer is None:
                return
            event.current_buffer.start_completion(select_first=False)

        @kb.add(Keys.BackTab)  # Shift+Tab
        def _on_shift_tab(event: KeyPressEvent):
            """切换到下一个模式"""
            self._mode_manager.next_mode()
            # 强制 UI 重绘
            event.app.invalidate()

        @kb.add(Keys.ControlD)
        def _on_cancel(event: KeyPressEvent):
            event.app.exit(result=None)

        def _container_contents() -> List[Window]:
            contents = [input_window]
            # 使用新的 statusbar_window
            if self._toolbar_text is not None:
                contents.append(statusbar_window)
            return contents
        
        def _container_floats() -> List[Float]:
            floats = [placeholder_float]
            if completer is not None:
                floats.append(completions_float)
            return floats
        
        root = FloatContainer(
            content=HSplit(_container_contents()),
            floats=_container_floats(),
        )

        app = Application(
            layout=Layout(root, focused_element=input_window),
            key_bindings=kb,
            style=build_prompt_toolkit_style(),
            full_screen=False,
            erase_when_done=True,
            mouse_support=False
        )
        result = await app.run_async()
        if result is None:
            raise UserCanceledError()

        return str(result)
        

def main():
    import asyncio
    async def _main():
        composer = ComposerComponent()
        result = await composer.show()
        print(result)
    asyncio.run(_main())

if __name__ == "__main__":
    main()
