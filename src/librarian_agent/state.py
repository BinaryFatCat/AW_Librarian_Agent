"""
状态定义模块
定义 Librarian Agent 的状态结构
"""

from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class LibrarianState(TypedDict):
    """
    Librarian Agent 状态
    
    Attributes:
        intent: 上个 Agent (Parser) 传入的 BDD 步骤信息
        messages: 对话历史，用于 LLM 多轮推理
        candidates: 匹配到的候选 AW 列表
        result: 最终结果（由下一个 Agent 更新）
        library_path: AW 库的本地路径
        current_step: 当前处理的步骤信息
        debug: 是否开启调试日志
    """
    # 上游输入：来自 Parser Agent
    intent: dict
    
    # 对话消息列表（自动累加）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 候选 AW 列表
    candidates: List[dict]
    
    # 下游输出：由后续 Agent 填充
    result: dict
    
    # 配置信息
    library_path: str
    current_step: dict
    debug: bool
