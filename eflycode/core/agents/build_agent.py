"""构建智能体 - 主动执行复杂任务"""

from typing import List, Optional

from eflycode.core.agent.base import BaseAgent
from eflycode.core.llm.protocol import ToolDefinition
from eflycode.core.utils.logger import logger


# 任务完成标记常量
_COMPLETION_INDICATORS = frozenset({
    "任务完成",
    "已完成",
    "finished",
    "completed",
    "done",
})

# 未完成标记常量
_INCOMPLETE_INDICATORS = frozenset({
    "接下来",
    "然后",
    "还需要",
    "next step",
    "need to",
})


class BuildAgent(BaseAgent):
    """构建智能体（Build 模式）

    主动执行复杂任务，支持自动迭代和完成性检查。

    特性:
        - 自动迭代：完成一个步骤后自动进入下一步，不需要用户确认
        - 完成性检查：智能判断任务是否真正完成

    示例:
        >>> agent = BuildAgent(model="gpt-4", provider=provider)
        >>> is_complete = agent.check_completion(conversation)
    """

    ROLE = "build"

    def __init__(self, *args, **kwargs):
        """初始化 BuildAgent

        Args:
            *args: 传递给 BaseAgent 的位置参数
            **kwargs: 传递给 BaseAgent 的关键字参数
        """
        super().__init__(*args, **kwargs)
        self._auto_iterate = True
        self._completion_check_enabled = True

    def should_auto_iterate(self) -> bool:
        """判断是否应该自动迭代（不等待用户确认）

        Build 模式下默认启用自动迭代，Agent 会主动执行任务步骤。

        返回:
            bool: 总是返回 True，表示应该自动迭代

        示例:
            >>> agent = BuildAgent(model="gpt-4", provider=provider)
            >>> agent.should_auto_iterate()
            True
        """
        return self._auto_iterate

    def check_completion(self, conversation: Optional[object]) -> bool:
        """检查任务是否完成

        通过分析对话内容中的完成标记和未完成标记，判断任务是否真正完成。

        Args:
            conversation: 当前对话对象，必须有 content 属性

        返回:
            bool: True 表示任务完成，False 表示任务未完成或无法判断

        示例:
            >>> agent = BuildAgent(model="gpt-4", provider=provider)
            >>> conv = Mock(content="任务已完成")
            >>> agent.check_completion(conv)
            True
            >>> conv.content = "接下来需要做这个"
            >>> agent.check_completion(conv)
            False
        """
        if not conversation or not hasattr(conversation, 'content'):
            logger.warning("check_completion: conversation 无效或缺少 content 属性")
            return False

        content = conversation.content
        if not content or not isinstance(content, str):
            return False

        content_lower = content.lower()

        # 检查完成标记
        for indicator in _COMPLETION_INDICATORS:
            if indicator in content_lower:
                return True

        # 检查未完成标记
        for indicator in _INCOMPLETE_INDICATORS:
            if indicator in content_lower:
                return False

        # 如果没有明确的完成或未完成标记，默认认为未完成
        return False
