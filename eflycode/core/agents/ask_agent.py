"""问答智能体 - 快速简洁回答"""

from typing import List, Optional

from eflycode.core.agent.base import BaseAgent
from eflycode.core.llm.protocol import ToolDefinition
from eflycode.core.utils.logger import logger


# 简洁回答提示后缀
_CONCISE_ANSWER_PROMPT = "\\n\\n请简洁回答（不超过 200 字）。"


class AskAgent(BaseAgent):
    """问答智能体（Ask 模式）

    快速简洁回答，禁用工具调用，适用于知识性问答。

    特性:
        - 快速回答：直接给出答案，不需要详细解释
        - 简洁输出：避免冗长的说明和示例
        - 禁用工具：专注于知识性回答，不进行文件操作或命令执行
        - 独立任务：每个问题都是独立的，不依赖之前的对话

    示例:
        >>> agent = AskAgent(model="gpt-4", provider=provider)
        >>> response = agent.chat("Python 中什么是列表推导式?")
    """

    ROLE = "ask"

    def __init__(self, *args, **kwargs):
        """初始化 AskAgent

        Args:
            *args: 传递给 BaseAgent 的位置参数
            **kwargs: 传递给 BaseAgent 的关键字参数
        """
        super().__init__(*args, **kwargs)
        self._tools_enabled = False

    def get_available_tools(self) -> List[ToolDefinition]:
        """获取可用工具列表

        Ask 模式下禁用所有工具，返回空列表。

        返回:
            List[ToolDefinition]: 空列表，表示不使用任何工具

        示例:
            >>> agent = AskAgent(model="gpt-4", provider=provider)
            >>> tools = agent.get_available_tools()
            >>> len(tools)
            0
        """
        return []

    def chat(self, message: Optional[str] = "") -> object:
        """发送消息并强制简洁回答

        如果消息不是问题，自动添加简洁回答提示。

        Args:
            message: 用户消息，如果为空则使用会话历史

        返回:
            ChatConversation: 对话对象，包含响应和消息历史

        示例:
            >>> agent = AskAgent(model="gpt-4", provider=provider)
            >>> response = agent.chat("解释什么是递归")
            >>> # 会自动添加简洁回答提示
        """
        if message and not message.strip().endswith('?'):
            message = f"{message}{_CONCISE_ANSWER_PROMPT}"

        return super().chat(message)
