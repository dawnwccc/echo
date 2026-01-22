"""主程序入口

将各个组件 Agent、UI、事件系统串联起来，实现完整的 CLI 应用
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from eflycode.cli.components.composer import ComposerComponent
from eflycode.cli.command_registry import get_command_registry
from eflycode.cli.output import TerminalOutput
from eflycode.core.agent.base import BaseAgent
from eflycode.core.agent.factory import AgentFactory, AgentConfig
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.agents.default_agent import DefaultAgent
from eflycode.core.agents.plan_agent import PlanAgent
from eflycode.core.agents.build_agent import BuildAgent
from eflycode.core.agents.debug_agent import DebugAgent
from eflycode.core.agents.ask_agent import AskAgent
from eflycode.core.config import Config
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.agent.session_store import SessionStore
from eflycode.core.llm.advisors.request_log_advisor import RequestLogAdvisor
from eflycode.core.ui.bridge import EventBridge
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.mode import ComposerMode
from eflycode.core.ui.renderer import Renderer
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.core.utils.file_manager import get_file_manager
from eflycode.core.utils.logger import logger
from eflycode.core.event.event_bus import get_global_event_bus


@dataclass
class ApplicationContext:
    """应用上下文"""

    config: Config
    ui_queue: UIEventQueue | None = None
    output: TerminalOutput | None = None
    renderer: Renderer | None = None
    event_bridge: EventBridge | None = None

    # 新增字段：多智能体支持
    current_agent: BaseAgent | None = None  # 当前 Agent 实例
    agent_factory: 'AgentFactory' | None = None  # Agent 工厂引用

    def switch_agent_mode(self, target_mode: ComposerMode) -> None:
        """切换 Agent 模式

        Args:
            target_mode: 目标模式
        """
        if not self.agent_factory:
            logger.warning("AgentFactory 未初始化，无法切换模式")
            return

        if not self.current_agent:
            logger.warning("当前没有 Agent 实例，无法切换模式")
            return

        # 切换 Agent
        new_agent = self.agent_factory.switch_agent(
            current_agent=self.current_agent,
            target_mode=target_mode,
            config=self.config,
        )

        self.current_agent = new_agent

        logger.info(f"ApplicationContext Agent 已切换: {target_mode.value}")


def initialize_application(setup_ui: bool = False) -> ApplicationContext:
    """初始化应用程序
    
    加载配置、设置工作区目录，执行应用程序初始化
    
    Returns:
        ApplicationContext: 应用上下文
    """
    logger.info("初始化应用程序")
    
    # 加载配置
    config_manager = ConfigManager.get_instance()
    config = config_manager.load()
    logger.info(f"配置加载完成，工作区目录: {config.workspace_dir}")
    
    # 设置工作区目录
    if config.workspace_dir:
        os.chdir(config.workspace_dir)
        logger.info(f"切换到工作区目录: {config.workspace_dir}")
    
    app_context = ApplicationContext(config=config)

    # 初始化 AgentFactory 并注册所有 Agent 类
    agent_factory = AgentFactory.get_instance()
    agent_factory.register_agent(ComposerMode.DEFAULT, DefaultAgent)
    agent_factory.register_agent(ComposerMode.PLAN, PlanAgent)
    agent_factory.register_agent(ComposerMode.BUILD, BuildAgent)
    agent_factory.register_agent(ComposerMode.DEBUG, DebugAgent)
    agent_factory.register_agent(ComposerMode.ASK, AskAgent)
    app_context.agent_factory = agent_factory

    if setup_ui:
        ui_queue = UIEventQueue()
        output = TerminalOutput()
        renderer = Renderer(ui_queue, output)
        event_bridge = EventBridge(
            event_bus=get_global_event_bus(),
            ui_queue=ui_queue,
            event_types=[
                "app.startup",
                "app.initialized",
                "app.shutdown",
                "agent.task.start",
                "agent.task.stop",
                "agent.message.start",
                "agent.message.delta",
                "agent.message.stop",
                "agent.tool.call.start",
                "agent.tool.call.ready",
                "agent.tool.call",
                "agent.tool.result",
                "agent.tool.error",
                "agent.error",
                "agent.switched",  # 新增：Agent 切换事件
            ],
        )
        event_bridge.start()

        app_context.ui_queue = ui_queue
        app_context.output = output
        app_context.renderer = renderer
        app_context.event_bridge = event_bridge

        event_bus = get_global_event_bus()
        event_bus.emit("app.startup")
        event_bus.emit("app.initialized", config=config)

        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            ui_queue.process_events()
            renderer.tick()
            if ui_queue.size() == 0:
                time.sleep(0.01)
            else:
                time.sleep(0)

    return app_context


def run_agent_task(agent: BaseAgent, user_input: str, run_loop: AgentRunLoop) -> None:
    """在后台线程运行 Agent 任务

    Args:
        agent: Agent 实例
        user_input: 用户输入
        run_loop: AgentRunLoop 实例
    """
    try:
        run_loop.run(user_input)
    except Exception as e:
        agent.event_bus.emit("agent.error", agent=agent, error=e)


def _render_resumed_history(output: TerminalOutput, session_messages: list) -> None:
    """渲染恢复会话的历史消息"""
    if not session_messages:
        return
    output.write("\n[已恢复历史消息]\n")
    for message in session_messages:
        content = message.content or ""
        role = message.role
        if role == "tool":
            continue
        if role == "assistant" and message.tool_calls:
            for tool_call in message.tool_calls:
                args = tool_call.function.arguments or ""
                args_preview = args if len(args) <= 120 else f"{args[:120]}..."
                output.write(f"\n[tool] {tool_call.function.name} {args_preview}\n")
        output.write(f"\n{role}: {content}\n")
    output.write("\n")

async def run_interactive_cli(
    resume_session_id: str | None = None,
    app_context: ApplicationContext | None = None,
) -> None:
    """运行交互式 CLI

    Args:
        resume_session_id: 要恢复的会话 ID
        app_context: 应用上下文，可选
    """
    
    logger.info("启动 eflycode CLI")

    if not app_context:
        app_context = initialize_application(setup_ui=True)
    if not app_context.ui_queue or not app_context.output or not app_context.renderer:
        raise RuntimeError("应用上下文未初始化 UI 组件")
    if not app_context.event_bridge:
        raise RuntimeError("应用上下文未初始化 EventBridge")

    config = app_context.config
    logger.info(f"使用配置，工作区目录: {config.workspace_dir}")

    # 获取初始模式
    default_mode_str = config.composer.default_mode if hasattr(config, 'composer') and config.composer else "Default"
    try:
        initial_mode = ComposerMode(default_mode_str)
    except ValueError:
        initial_mode = ComposerMode.DEFAULT
        logger.warning(f"Invalid mode in config: {default_mode_str}, using Default")

    # 使用 AgentFactory 创建初始 Agent
    if not app_context.agent_factory:
        raise RuntimeError("AgentFactory 未初始化")

    agent_config = AgentConfig(mode=initial_mode, config=config)
    agent = app_context.agent_factory.create_agent(agent_config)

    # 保存到 ApplicationContext
    app_context.current_agent = agent

    logger.info(f"Agent 创建完成，模型: {config.model_name}, 模式: {initial_mode.value}")

    session_data = None
    if resume_session_id:
        session_data = SessionStore.get_instance().load(resume_session_id)
        if not session_data:
            raise ValueError(f"未找到会话: {resume_session_id}")
        agent.session.load_state(
            session_id=session_data["id"],
            messages=session_data["messages"],
            initial_user_question=session_data.get("initial_user_question"),
        )
        logger.info(f"已恢复会话: {agent.session.id}")

    # 默认启用请求日志
    request_log_advisor = RequestLogAdvisor(session_id=agent.session.id)
    agent.provider.add_advisors([request_log_advisor])
    logger.info(f"RequestLogAdvisor 已添加，日志文件: {request_log_advisor.log_file}")
    
    # UI 组件从初始化上下文获取
    ui_queue = app_context.ui_queue
    output = app_context.output
    renderer = app_context.renderer
    file_manager = get_file_manager()
    file_manager.start_watching()
    # 创建智能命令 completer，传入 agent_factory 和 app_context
    composer = ComposerComponent(
        agent_factory=app_context.agent_factory,
        app_context=app_context,
    )
    registry = get_command_registry()
    
    event_bridge = app_context.event_bridge
    if session_data:
        _render_resumed_history(output, agent.session.get_messages())
    
    try:
        # 主循环
        while True:
            try:
                # 从配置中读取默认模式
                config = app_context.config
                default_mode_str = config.composer.default_mode if hasattr(config, 'composer') and config.composer else "Default"

                # 转换为 ComposerMode 枚举
                try:
                    initial_mode = ComposerMode(default_mode_str)
                except ValueError:
                    initial_mode = ComposerMode.DEFAULT
                    logger.warning(f"Invalid mode in config: {default_mode_str}, using Default")

                # 获取用户输入
                user_input = await composer.show(
                    prompt_text="> ",
                    busy_prompt_text="🤔> ",
                    placeholder="share your ideas...",
                    toolbar_text="Press Ctrl+M to submit, Ctrl+D to exit, /model to select model",
                    initial_mode=initial_mode,
                )
                
                if not user_input or not user_input.strip():
                    continue

                if user_input.strip().startswith("/"):
                    handled = await registry.handle_command_async(user_input)
                    if handled:
                        continue
                    continue

                logger.info(f"收到用户输入: {user_input[:50]}...")
                
                session_messages = agent.session.get_messages()

                # 新任务开始时，检查session最后一条消息
                # 如果最后一条消息是tool消息，需要添加一个空的assistant消息来修复消息序列
                # 这样可以保持对话历史的连续性，同时确保消息序列正确
                if session_messages:
                    last_message = session_messages[-1]
                    if last_message.role == "tool":
                        # 最后一条是tool消息，添加一个空的assistant消息来结束上一个任务
                        # 这样可以保持消息序列正确，同时保留对话历史
                        logger.info("检测到session最后一条消息是tool消息，添加空的assistant消息以修复消息序列")
                        agent.session.add_message("assistant", content="")
                
                # 创建运行循环
                run_loop = AgentRunLoop(agent)
                
                # 使用 asyncio.to_thread 在线程中运行同步的 Agent 任务
                # 这样可以避免阻塞事件循环
                # 同时在前台处理 UI 更新
                agent_task = asyncio.create_task(
                    asyncio.to_thread(run_agent_task, agent, user_input, run_loop)
                )
                
                # UI 渲染循环，在 Agent 执行期间持续更新
                while not agent_task.done():
                    # 处理 UI 事件
                    ui_queue.process_events(time_budget_ms=50)
                    
                    # 更新渲染
                    renderer.tick(time_budget_ms=50)
                    
                    # 短暂休眠，避免 CPU 占用过高
                    await asyncio.sleep(0.01)
                
                # 等待任务完成，如果还没完成
                try:
                    await agent_task
                except Exception as e:
                    logger.error(f"Agent 任务执行失败: {e}", exc_info=True)
                
                # 最终渲染
                while ui_queue.size() > 0:
                    ui_queue.process_events()
                    renderer.tick()
                
                renderer.tick()
                output.write("\n")
                
            except UserCanceledError:
                # 用户取消，按 Ctrl+D
                output.write("\n[退出]\n")
                break
            except KeyboardInterrupt:
                # Ctrl+C
                output.write("\n[中断]\n")
                break
            except Exception as e:
                output.show_error(e)
                logger.exception("主循环错误")
    
    finally:
        # 清理资源
        get_global_event_bus().emit("app.shutdown")
        event_bridge.stop()
        renderer.close()
        file_manager.stop_watching()
        
        # 断开MCP客户端连接
        if hasattr(agent, "_mcp_clients"):
            for mcp_client in agent._mcp_clients:
                try:
                    mcp_client.disconnect()
                except Exception as e:
                    logger.warning(f"断开MCP客户端连接失败: {e}")
        
        agent.shutdown()


def main() -> None:
    """主函数，用于向后兼容"""
    asyncio.run(run_interactive_cli())


if __name__ == "__main__":
    main()
