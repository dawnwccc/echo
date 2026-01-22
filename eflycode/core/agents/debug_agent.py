"""调试智能体 - 详细诊断和错误分析"""

import traceback
from typing import Optional, Dict, Any

from eflycode.core.agent.base import BaseAgent
from eflycode.core.utils.logger import logger


class DebugAgent(BaseAgent):
    """调试智能体（Debug 模式）

    提供详细的诊断信息和错误分析。

    特性:
        - 详细日志：记录完整的诊断过程
        - 错误分析：分析错误的根本原因和传播路径
        - 上下文收集：主动收集相关的代码、配置和环境信息
        - 解决方案验证：确保解决方案可行且安全

    示例:
        >>> agent = DebugAgent(model="gpt-4", provider=provider)
        >>> error_report = agent.diagnose_error(error, context={"file": "app.py"})
    """

    ROLE = "debug"

    def __init__(self, *args, **kwargs):
        """初始化 DebugAgent

        Args:
            *args: 传递给 BaseAgent 的位置参数
            **kwargs: 传递给 BaseAgent 的关键字参数
        """
        super().__init__(*args, **kwargs)
        self._verbose_logging = True
        self._error_context_collection = True

    def diagnose_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """诊断错误并生成报告

        收集错误信息并生成详细的诊断报告，包括错误类型、消息、堆栈跟踪和上下文。

        Args:
            error: 异常对象
            context: 额外的上下文信息，如文件名、代码片段等

        返回:
            str: 诊断报告，包含错误分析和解决建议

        异常:
            ValueError: 当 error 不是 Exception 实例时抛出

        示例:
            >>> agent = DebugAgent(model="gpt-4", provider=provider)
            >>> try:
            ...     risky_operation()
            ... except Exception as e:
            ...     report = agent.diagnose_error(e, {"file": "app.py", "line": 42})
        """
        if not isinstance(error, Exception):
            raise ValueError(f"error 必须是 Exception 实例，收到: {type(error)}")

        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }

        prompt = self._build_diagnosis_prompt(error_info)

        try:
            response = self.chat(prompt)
            return response.content
        except Exception as e:
            logger.error(f"诊断失败: {e}")
            return f"诊断失败: {e}"

    def _build_diagnosis_prompt(self, error_info: Dict[str, Any]) -> str:
        """构建诊断提示词

        Args:
            error_info: 包含错误类型、消息、堆栈跟踪和上下文的字典

        Returns:
            str: 格式化的诊断提示词

        示例:
            >>> agent = DebugAgent(model="gpt-4", provider=provider)
            >>> error_info = {"type": "ValueError", "message": "invalid literal"}
            >>> prompt = agent._build_diagnosis_prompt(error_info)
        """
        return f"""请详细分析以下错误：

**错误类型**: {error_info['type']}
**错误消息**: {error_info['message']}

**堆栈跟踪**:
```
{error_info['traceback']}
```

请分析：
1. 错误发生的根本原因
2. 错误传播路径
3. 可能的解决方案
"""
