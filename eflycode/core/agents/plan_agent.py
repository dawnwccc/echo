"""规划智能体 - 任务规划和分解"""

from typing import Optional

from eflycode.core.agent.base import BaseAgent
from eflycode.core.utils.logger import logger


# 结构化输出标记常量
_STRUCTURE_INDICATORS = frozenset({
    "##",           # Markdown 标题
    "1.", "2.",      # 编号列表
    "-",            # 项目列表
})


class PlanAgent(BaseAgent):
    """规划智能体（Plan 模式）

    专注于任务规划和分解，提供结构化输出。

    特性:
        - 计划验证：检查输出是否包含结构化内容
        - 任务分解：将复杂任务分解为可执行步骤
        - 依赖分析：识别任务依赖关系

    示例:
        >>> agent = PlanAgent(model="gpt-4", provider=provider)
        >>> conversation = agent.chat("帮我实现用户认证功能")
    """

    ROLE = "plan"

    def __init__(self, *args, **kwargs):
        """初始化 PlanAgent

        Args:
            *args: 传递给 BaseAgent 的位置参数
            **kwargs: 传递给 BaseAgent 的关键字参数
        """
        super().__init__(*args, **kwargs)
        self._plan_validation_enabled = True

    def chat(self, message: Optional[str] = "") -> object:
        """发送消息并验证输出结构

        Args:
            message: 用户消息，如果为空则使用会话历史

        Returns:
            ChatConversation: 对话对象，包含响应和消息历史

        示例:
            >>> agent = PlanAgent(model="gpt-4", provider=provider)
            >>> result = agent.chat("制定项目计划")
        """
        conversation = super().chat(message)

        if self._plan_validation_enabled and conversation.content:
            self._validate_plan_output(conversation.content)

        return conversation

    def _validate_plan_output(self, content: str) -> None:
        """验证输出是否包含结构化计划

        检查内容是否包含标题、列表或其他结构化标记。

        Args:
            content: 要验证的文本内容

        示例:
            >>> agent = PlanAgent(model="gpt-4", provider=provider)
            >>> agent._validate_plan_output("## 步骤一\\n1. 分析需求")
        """
        has_structure = any(indicator in content for indicator in _STRUCTURE_INDICATORS)

        if not has_structure:
            logger.warning("PlanAgent 输出缺乏结构化格式，建议使用标题或列表")
