"""Agent 工厂，负责创建和管理不同模式的 Agent 实例"""

from dataclasses import dataclass
from typing import Dict, Optional, Type

from eflycode.core.agent.base import BaseAgent
from eflycode.core.config.models import Config
from eflycode.core.ui.mode import ComposerMode
from eflycode.core.agent.session import Session
from eflycode.core.event.event_bus import EventBus
from eflycode.core.utils.logger import logger


# 会话保留策略常量
_SESSION_CLEAR_MODES = frozenset({ComposerMode.ASK})


@dataclass
class AgentConfig:
    """Agent 创建配置

    属性:
        mode: 目标工作模式
        config: 应用配置对象
        session: 可选的现有会话，用于模式切换时保留状态
        event_bus: 可选的事件总线，用于复用现有事件总线
    """

    mode: ComposerMode
    config: Config
    session: Optional[Session] = None
    event_bus: Optional[EventBus] = None


class AgentFactory:
    """Agent 工厂类，负责创建和管理不同模式的 Agent 实例

    采用工厂模式和单例模式，统一管理 Agent 的创建、切换和状态迁移。

    示例:
        >>> factory = AgentFactory.get_instance()
        >>> factory.register_agent(ComposerMode.BUILD, BuildAgent)
        >>> agent_config = AgentConfig(mode=ComposerMode.BUILD, config=config)
        >>> agent = factory.create_agent(agent_config)
    """

    _instance: Optional["AgentFactory"] = None
    _agent_classes: Dict[ComposerMode, Type[BaseAgent]] = {}

    def __new__(cls) -> "AgentFactory":
        """单例模式实现，确保全局只有一个工厂实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "AgentFactory":
        """获取单例实例

        返回:
            AgentFactory: 全局唯一的工厂实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_agent(
        self,
        mode: ComposerMode,
        agent_cls: Type[BaseAgent]
    ) -> None:
        """注册 Agent 类到模式

        Args:
            mode: 工作模式
            agent_cls: Agent 类，必须继承自 BaseAgent

        Raises:
            TypeError: 当 agent_cls 不是 BaseAgent 的子类时抛出
        """
        if not issubclass(agent_cls, BaseAgent):
            raise TypeError(f"{agent_cls.__name__} 必须继承自 BaseAgent")

        self._agent_classes[mode] = agent_cls
        logger.debug(f"注册 Agent 类: mode={mode.value}, class={agent_cls.__name__}")

    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """创建指定模式的 Agent 实例

        根据配置创建 Agent，支持会话状态和事件总线的复用。

        Args:
            agent_config: Agent 创建配置，包含模式、配置对象、可选的会话和事件总线

        Returns:
            BaseAgent: 新创建的 Agent 实例

        Raises:
            ValueError: 当未注册的模式且没有默认 Agent 时抛出
            RuntimeError: 当 Agent 创建失败时抛出

        示例:
            >>> config = AgentConfig(
            ...     mode=ComposerMode.BUILD,
            ...     config=app_config,
            ...     session=existing_session,
            ...     event_bus=existing_event_bus
            ... )
            >>> agent = factory.create_agent(config)
        """
        from eflycode.core.llm.providers.openai import OpenAiProvider

        agent_cls = self._agent_classes.get(agent_config.mode)
        if not agent_cls:
            logger.warning(f"未注册模式 {agent_config.mode.value}，使用 DefaultAgent")
            agent_cls = self._agent_classes.get(
                ComposerMode.DEFAULT,
                self._get_default_agent_class()
            )

        if not agent_cls:
            raise ValueError(f"无法创建 Agent：未注册模式 {agent_config.mode.value} 且没有默认 Agent")

        try:
            provider = OpenAiProvider(agent_config.config.llm_config)

            agent = agent_cls(
                model=agent_config.config.model_name,
                provider=provider,
            )

            if agent_config.session:
                agent.session = agent_config.session

            if agent_config.event_bus:
                agent.event_bus = agent_config.event_bus

            logger.info(
                f"创建 Agent 成功: mode={agent_config.mode.value}, "
                f"class={agent_cls.__name__}, model={agent_config.config.model_name}"
            )
            return agent

        except Exception as e:
            logger.error(
                f"创建 Agent 失败: mode={agent_config.mode.value}, error={e}",
                exc_info=True
            )
            raise RuntimeError(f"创建 Agent 失败: {e}") from e

    def switch_agent(
        self,
        current_agent: BaseAgent,
        target_mode: ComposerMode,
        config: Config,
    ) -> BaseAgent:
        """切换 Agent 模式

        根据会话保留策略，智能处理会话状态的迁移。Ask 模式总是清空会话，
        其他模式切换时保留会话状态。

        Args:
            current_agent: 当前 Agent 实例
            target_mode: 目标模式
            config: 应用配置对象

        Returns:
            BaseAgent: 新创建的 Agent 实例

        Raises:
            RuntimeError: 当 Agent 创建或切换失败时抛出

        示例:
            >>> new_agent = factory.switch_agent(
            ...     current_agent=agent,
            ...     target_mode=ComposerMode.BUILD,
            ...     config=config
            ... )
        """
        old_mode_str = current_agent.ROLE
        new_mode_str = target_mode.value

        old_mode = self._parse_mode_string(old_mode_str)
        should_preserve = self._should_preserve_session(old_mode, target_mode)

        logger.info(
            f"切换 Agent: {old_mode_str} → {new_mode_str}, "
            f"preserve_session={should_preserve}"
        )

        old_session = current_agent.session if should_preserve else None
        old_event_bus = current_agent.event_bus

        agent_config = AgentConfig(
            mode=target_mode,
            config=config,
            session=old_session,
            event_bus=old_event_bus
        )

        new_agent = self.create_agent(agent_config)

        try:
            current_agent.shutdown()
        except Exception as e:
            logger.warning(f"清理旧 Agent 失败: {e}")

        if old_event_bus:
            old_event_bus.emit(
                "agent.switched",
                old_mode=old_mode_str,
                new_mode=new_mode_str,
                preserved_session=should_preserve,
            )

        return new_agent

    def _should_preserve_session(
        self,
        old_mode: ComposerMode,
        new_mode: ComposerMode
    ) -> bool:
        """判断是否应该保留会话状态

        保留策略：Ask 模式总是清空（独立任务），切换到 Ask 模式时清空，其他情况保留。

        Args:
            old_mode: 旧模式
            new_mode: 新模式

        Returns:
            bool: True 表示保留会话，False 表示清空会话
        """
        if old_mode in _SESSION_CLEAR_MODES or new_mode in _SESSION_CLEAR_MODES:
            return False
        return True

    def _parse_mode_string(self, mode_str: str) -> ComposerMode:
        """将模式字符串解析为 ComposerMode 枚举

        Args:
            mode_str: 模式字符串

        Returns:
            ComposerMode: 对应的模式枚举，如果无效则返回 DEFAULT

        示例:
            >>> factory._parse_mode_string("build")
            <ComposerMode.BUILD>
        """
        for mode in ComposerMode:
            if mode.value.lower() == mode_str.lower():
                return mode
        return ComposerMode.DEFAULT

    def _get_default_agent_class(self) -> Optional[Type[BaseAgent]]:
        """获取默认 Agent 类

        Returns:
            Optional[Type[BaseAgent]]: DefaultAgent 类，如果未注册则返回 None
        """
        return self._agent_classes.get(ComposerMode.DEFAULT)
