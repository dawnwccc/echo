"""测试多智能体系统"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from eflycode.core.agent.factory import AgentFactory, AgentConfig
from eflycode.core.agents.default_agent import DefaultAgent
from eflycode.core.agents.plan_agent import PlanAgent
from eflycode.core.agents.build_agent import BuildAgent
from eflycode.core.agents.debug_agent import DebugAgent
from eflycode.core.agents.ask_agent import AskAgent
from eflycode.core.ui.mode import ComposerMode
from eflycode.core.config.models import Config, ModelEntry, ComposerSection, ConfigMeta
from pathlib import Path


class TestAgentRoles:
    """测试各 Agent 的 ROLE 属性"""

    def test_default_agent_role(self):
        """测试 DefaultAgent 的 ROLE"""
        assert DefaultAgent.ROLE == "default"

    def test_plan_agent_role(self):
        """测试 PlanAgent 的 ROLE"""
        assert PlanAgent.ROLE == "plan"

    def test_build_agent_role(self):
        """测试 BuildAgent 的 ROLE"""
        assert BuildAgent.ROLE == "build"

    def test_debug_agent_role(self):
        """测试 DebugAgent 的 ROLE"""
        assert DebugAgent.ROLE == "debug"

    def test_ask_agent_role(self):
        """测试 AskAgent 的 ROLE"""
        assert AskAgent.ROLE == "ask"


class TestAgentFactory:
    """测试 AgentFactory 类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        AgentFactory._instance = None
        AgentFactory._agent_classes = {}

    def test_singleton(self):
        """测试单例模式"""
        factory1 = AgentFactory()
        factory2 = AgentFactory()
        assert factory1 is factory2

    def test_get_instance(self):
        """测试获取单例实例"""
        factory = AgentFactory.get_instance()
        assert factory is not None
        assert isinstance(factory, AgentFactory)

    def test_register_agent(self):
        """测试注册 Agent 类"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.DEFAULT, DefaultAgent)

        assert ComposerMode.DEFAULT in factory._agent_classes
        assert factory._agent_classes[ComposerMode.DEFAULT] == DefaultAgent

    def test_register_invalid_agent(self):
        """测试注册无效的 Agent 类"""
        factory = AgentFactory.get_instance()

        with pytest.raises(TypeError):
            factory.register_agent(ComposerMode.DEFAULT, object)

    def test_register_multiple_agents(self):
        """测试注册多个 Agent 类"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.DEFAULT, DefaultAgent)
        factory.register_agent(ComposerMode.PLAN, PlanAgent)
        factory.register_agent(ComposerMode.BUILD, BuildAgent)
        factory.register_agent(ComposerMode.DEBUG, DebugAgent)
        factory.register_agent(ComposerMode.ASK, AskAgent)

        assert len(factory._agent_classes) == 5
        assert factory._agent_classes[ComposerMode.DEFAULT] == DefaultAgent
        assert factory._agent_classes[ComposerMode.PLAN] == PlanAgent
        assert factory._agent_classes[ComposerMode.BUILD] == BuildAgent
        assert factory._agent_classes[ComposerMode.DEBUG] == DebugAgent
        assert factory._agent_classes[ComposerMode.ASK] == AskAgent

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_create_default_agent(self, mock_provider):
        """测试创建 DefaultAgent"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.DEFAULT, DefaultAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.DEFAULT, config=config)
        agent = factory.create_agent(agent_config)

        assert isinstance(agent, DefaultAgent)
        assert agent.ROLE == "default"

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_create_plan_agent(self, mock_provider):
        """测试创建 PlanAgent"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.PLAN, PlanAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.PLAN, config=config)
        agent = factory.create_agent(agent_config)

        assert isinstance(agent, PlanAgent)
        assert agent.ROLE == "plan"

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_create_agent_with_session(self, mock_provider):
        """测试创建 Agent 时传入现有会话"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.DEFAULT, DefaultAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        mock_session = Mock()

        agent_config = AgentConfig(
            mode=ComposerMode.DEFAULT,
            config=config,
            session=mock_session
        )
        agent = factory.create_agent(agent_config)

        assert agent.session is mock_session

    def test_create_unregistered_agent_without_default(self):
        """测试创建未注册的 Agent 且没有默认 Agent"""
        factory = AgentFactory.get_instance()

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.BUILD, config=config)

        with pytest.raises(ValueError, match="无法创建 Agent"):
            factory.create_agent(agent_config)


class TestPlanAgent:
    """测试 PlanAgent 特有功能"""

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_plan_validation_enabled(self, mock_provider):
        """测试计划验证默认启用"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.PLAN, PlanAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.PLAN, config=config)
        agent = factory.create_agent(agent_config)

        assert agent._plan_validation_enabled is True


class TestBuildAgent:
    """测试 BuildAgent 特有功能"""

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_auto_iterate_enabled(self, mock_provider):
        """测试自动迭代默认启用"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.BUILD, BuildAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.BUILD, config=config)
        agent = factory.create_agent(agent_config)

        assert agent._auto_iterate is True

    def test_should_auto_iterate(self):
        """测试 should_auto_iterate 方法"""
        agent = BuildAgent(model="gpt-4", provider=Mock())
        assert agent.should_auto_iterate() is True

    def test_check_completion_with_completion_indicators(self):
        """测试完成性检查 - 包含完成标记"""
        agent = BuildAgent(model="gpt-4", provider=Mock())

        conversation = Mock()
        conversation.content = "任务已完成"

        assert agent.check_completion(conversation) is True

    def test_check_completion_with_incomplete_indicators(self):
        """测试完成性检查 - 包含未完成标记"""
        agent = BuildAgent(model="gpt-4", provider=Mock())

        conversation = Mock()
        conversation.content = "接下来我们需要做这个"

        assert agent.check_completion(conversation) is False

    def test_check_completion_with_invalid_conversation(self):
        """测试完成性检查 - 无效对话对象"""
        agent = BuildAgent(model="gpt-4", provider=Mock())

        assert agent.check_completion(None) is False
        assert agent.check_completion("not an object") is False

    def test_check_completion_with_empty_content(self):
        """测试完成性检查 - 空内容"""
        agent = BuildAgent(model="gpt-4", provider=Mock())

        conversation = Mock()
        conversation.content = None

        assert agent.check_completion(conversation) is False

        conversation.content = ""
        assert agent.check_completion(conversation) is False


class TestDebugAgent:
    """测试 DebugAgent 特有功能"""

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_verbose_logging_enabled(self, mock_provider):
        """测试详细日志默认启用"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.DEBUG, DebugAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.DEBUG, config=config)
        agent = factory.create_agent(agent_config)

        assert agent._verbose_logging is True
        assert agent._error_context_collection is True

    def test_diagnose_error_with_invalid_error(self):
        """测试诊断错误 - 传入无效错误对象"""
        agent = DebugAgent(model="gpt-4", provider=Mock())

        with pytest.raises(ValueError, match="error 必须是 Exception 实例"):
            agent.diagnose_error("not an exception")


class TestAskAgent:
    """测试 AskAgent 特有功能"""

    @patch('eflycode.core.llm.providers.openai.OpenAiProvider')
    def test_tools_disabled(self, mock_provider):
        """测试工具默认禁用"""
        factory = AgentFactory.get_instance()
        factory.register_agent(ComposerMode.ASK, AskAgent)

        config = Mock()
        config.llm_config = Mock()
        config.model_name = "gpt-4"

        agent_config = AgentConfig(mode=ComposerMode.ASK, config=config)
        agent = factory.create_agent(agent_config)

        assert agent._tools_enabled is False

    def test_get_available_tools_returns_empty(self):
        """测试 AskAgent 不返回工具"""
        agent = AskAgent(model="gpt-4", provider=Mock())
        tools = agent.get_available_tools()
        assert tools == []
