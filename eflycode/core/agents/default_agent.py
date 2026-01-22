"""默认智能体 - 通用任务处理"""

from eflycode.core.agent.base import BaseAgent


class DefaultAgent(BaseAgent):
    """默认智能体

    用于处理通用任务，平衡速度和质量。

    特性:
        - 标准的 Agent 行为
        - 继承 BaseAgent 的所有功能
        - 无特殊配置或行为

    示例:
        >>> agent = DefaultAgent(model="gpt-4", provider=provider)
    """

    ROLE = "default"
