"""
LangGraph 图构建模块
使用自定义 StateGraph 实现 Librarian Agent
支持完整的状态流转：intent → candidates → result
"""

import json
import re
from typing import Literal, List

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.graph import StateGraph, END, START

from .state import LibrarianState
from .tools import create_tools


# ============================================================================
# 配置参数
# ============================================================================

# 最大上下文 Token 数（防止超出 LLM 上下文窗口）
MAX_CONTEXT_TOKENS = 8000

# 最大工具调用轮次（防止无限循环）
MAX_TOOL_ITERATIONS = 15


# ============================================================================
# 系统提示词
# ============================================================================

LIBRARIAN_SYSTEM_PROMPT = """你是一名资深的测试自动化专家 Librarian，负责在 AW (Action Word) 知识库中查找匹配的 AW 定义。

## 你的任务
根据用户提供的 BDD 测试步骤，在本地 AW Markdown 库中查找最匹配的 AW。

## AW 库路径
{library_path}

## 可用工具

| 工具 | 用途 | 何时使用 |
|------|------|----------|
| `find_aw_files` | 列出库中所有 .md 文件 | 🔹 **首次调用**：了解库结构 |
| `rg_search_keywords` | ripgrep 关键词搜索 | 🔹 搜索动作/实体（如 "project", "branch"） |
| `cat_read_file` | 读取文件完整内容 | 🔹 验证 AW 参数和功能细节 |
| `extract_aw_metadata` | 提取 YAML 元数据 | 🔹 获取 AW 的结构化信息 |
| `grep_search_pattern` | 正则模式搜索 | 🔹 搜索特定格式（如 YAML frontmatter） |

## 🧠 你的思考过程（ReAct 模式）

你必须按以下模式进行**多轮推理**：

### 第一轮：探索
1. **Thought**: 分析步骤的 action_type（如 API_CALL, UI_OPERATION）和描述中的关键词
2. **Action**: 调用 `find_aw_files` 了解库结构，然后用 `rg_search_keywords` 搜索关键词
3. **Observation**: 观察搜索结果，记录匹配的文件路径

### 第二轮：验证
1. **Thought**: 分析搜索结果，判断哪些文件可能匹配
2. **Action**: 用 `cat_read_file` 或 `extract_aw_metadata` 读取候选文件详情
3. **Observation**: 验证 AW 的参数、功能是否与步骤匹配

### 第三轮：决策
1. **Thought**: 综合所有信息，做出最终判断
2. **Action**: 输出候选列表（或继续搜索如果信息不足）

## ⚠️ 重要规则

1. **必须使用工具** - 不要凭空猜测 AW，必须通过搜索验证
2. **观察结果后再决策** - 每次工具调用后，仔细分析返回内容
3. **🚫 禁止重复操作** - 如果某个搜索已返回「未找到」，**绝对不要**用相同或相似的关键词再次搜索！改用完全不同的策略（如：中→英、动词→名词、cat读取文件列表）
4. **搜索无结果时** - 尝试完全不同的关键词（同义词、英文/中文转换、更宽泛的词）
5. **通用备选** - 如果多次搜索仍找不到精确匹配，`rawApiCall` 可作为通用 API 调用 AW
6. **多关键词搜索** - 可以一次搜索多个关键词，如 "project,branch,create"


## 📤 最终输出格式

完成搜索后，**必须**输出如下 JSON 格式的候选列表：

```json
[
  {{
    "aw_id": "aw_createProject",
    "aw_name": "创建项目",
    "parameters": [{{"name": "projectName", "type": "string"}}],
    "reason": "步骤描述创建项目，AW 功能完全匹配"
  }}
]
```

- `reason`: 解释为什么选择这个 AW

如果确实找不到匹配，返回空数组 `[]` 并说明原因。
"""


# ============================================================================
# 直接调用 LLM API（绕过 LangChain Pydantic 验证）
# ============================================================================

def call_llm_raw(model, messages: list, tools: list, debug_mode: bool = False) -> AIMessage:
    """
    直接使用 httpx 调用 LLM API，绕过 LangChain 的 Pydantic 验证。
    用于处理 DeepSeek R1 返回 tool_calls.args 为字符串的情况。
    """
    import httpx
    import os
    
    # 获取 API 配置
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = getattr(model, 'openai_api_base', None) or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_name = getattr(model, 'model_name', None) or "deepseek-r1"
    
    # 构建请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 转换消息格式（确保 Tool/AI 消息配对正确）
    formatted_messages = []
    last_ai_tool_calls = []  # 跟踪最后一个 AIMessage 的 tool_calls
    
    for msg in messages:
        if isinstance(msg, SystemMessage):
            formatted_messages.append({"role": "system", "content": msg.content or ""})
        elif isinstance(msg, HumanMessage):
            formatted_messages.append({"role": "user", "content": msg.content or ""})
        elif isinstance(msg, AIMessage):
            ai_msg = {"role": "assistant", "content": msg.content or ""}
            # 处理 tool_calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                ai_msg["tool_calls"] = []
                last_ai_tool_calls = []
                for tc in msg.tool_calls:
                    if isinstance(tc, dict):
                        tc_id = tc.get('id', f'call_{len(ai_msg["tool_calls"])}')
                        ai_msg["tool_calls"].append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc.get('name', ''),
                                "arguments": json.dumps(tc.get('args', {}), ensure_ascii=False)
                            }
                        })
                        last_ai_tool_calls.append(tc_id)
            formatted_messages.append(ai_msg)
        elif isinstance(msg, ToolMessage):
            # 只有当 tool_call_id 匹配时才添加
            tool_call_id = getattr(msg, 'tool_call_id', None)
            if tool_call_id and (tool_call_id in last_ai_tool_calls or not last_ai_tool_calls):
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": msg.content or ""
                })
    
    # 转换工具格式
    formatted_tools = []
    for tool in tools:
        tool_schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if hasattr(tool, 'args_schema') else {}
            }
        }
        formatted_tools.append(tool_schema)
    
    payload = {
        "model": model_name,
        "messages": formatted_messages,
        "tools": formatted_tools if formatted_tools else None,
        "tool_choice": "auto"
    }
    
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        # 解析响应
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        raw_tool_calls = message.get("tool_calls", [])
        
        # 安全解析 tool_calls
        tool_calls = []
        for tc in raw_tool_calls:
            if isinstance(tc, dict) and "function" in tc:
                func = tc["function"]
                name = func.get("name", "")
                args = func.get("arguments", "{}")
                
                # 关键：将 args 从字符串转为字典
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                
                if name:
                    tool_calls.append({
                        "name": name,
                        "args": args,
                        "id": tc.get("id", f"call_{len(tool_calls)}"),
                        "type": "tool_call"
                    })
        
        if debug_mode and tool_calls:
            print(f"[DEBUG] ✅ 原始 API 调用成功，解析到 {len(tool_calls)} 个工具调用")
        
        return AIMessage(content=content, tool_calls=tool_calls)
        
    except Exception as e:
        if debug_mode:
            print(f"[DEBUG] ❌ 原始 API 调用失败: {str(e)}")
        return AIMessage(content=f"API 调用失败: {str(e)}", tool_calls=[])


# ============================================================================
# 工具调用安全解析（处理 DeepSeek R1 等模型的特殊格式）
# ============================================================================

def parse_tool_calls_from_response(response) -> list:
    """
    从 LLM 响应中安全地解析 tool_calls。
    处理 DeepSeek R1 等模型返回的 args 是 JSON 字符串的情况。
    """
    tool_calls = []
    
    def safe_parse_args(args):
        """安全解析 args，处理字符串和字典两种情况"""
        if args is None:
            return {}
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return {}
        return {}
    
    # 策略 1: 直接从 response.tool_calls 解析
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tc in response.tool_calls:
            try:
                # 处理字典和对象两种格式
                if isinstance(tc, dict):
                    name = tc.get('name', '')
                    args = safe_parse_args(tc.get('args', {}))
                    tc_id = tc.get('id', f'call_{len(tool_calls)}')
                else:
                    # 对象属性方式
                    name = getattr(tc, 'name', '') or (getattr(tc, 'function', {}) or {}).get('name', '')
                    args = safe_parse_args(getattr(tc, 'args', None) or getattr(tc, 'arguments', {}))
                    tc_id = getattr(tc, 'id', f'call_{len(tool_calls)}')
                
                if name:  # 确保有工具名称
                    tool_calls.append({
                        'name': name,
                        'args': args,
                        'id': tc_id,
                        'type': 'tool_call'
                    })
            except Exception as e:
                pass  # 忽略解析失败的单个 tool_call
        
        if tool_calls:
            return tool_calls
    
    # 策略 2: 从 additional_kwargs 解析 (OpenAI 格式)
    if hasattr(response, 'additional_kwargs'):
        raw_tool_calls = response.additional_kwargs.get('tool_calls', [])
        for tc in raw_tool_calls:
            try:
                if isinstance(tc, dict) and 'function' in tc:
                    func = tc['function']
                    name = func.get('name', '')
                    args = safe_parse_args(func.get('arguments', '{}'))
                    tc_id = tc.get('id', f'call_{len(tool_calls)}')
                    
                    if name:
                        tool_calls.append({
                            'name': name,
                            'args': args,
                            'id': tc_id,
                            'type': 'tool_call'
                        })
            except Exception:
                pass
    
    # 策略 3: 从内容中解析 JSON 格式的工具调用 (DeepSeek R1 特殊格式)
    if not tool_calls and hasattr(response, 'content') and response.content:
        content = response.content
        
        # 策略 3.1: 匹配 ```json [...] ``` 格式的工具调用数组
        # DeepSeek R1 可能输出: ```json\n[{"name": "rg_search_keywords", "arguments": {...}}]\n```
        json_block_pattern = r'```json\s*\n?([\s\S]*?)\n?```'
        json_matches = re.findall(json_block_pattern, content)
        
        for json_str in json_matches:
            try:
                parsed = json.loads(json_str.strip())
                # 如果是数组并且包含 name/arguments 或 name/args
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and ('name' in item or 'function' in item):
                            # 支持两种格式: {name, arguments} 或 {function: {name, arguments}}
                            if 'function' in item:
                                func = item['function']
                                name = func.get('name', '')
                                args = safe_parse_args(func.get('arguments', {}))
                            else:
                                name = item.get('name', '')
                                args = safe_parse_args(item.get('arguments', item.get('args', {})))
                            
                            if name:
                                tool_calls.append({
                                    'name': name,
                                    'args': args,
                                    'id': item.get('id', f'call_{len(tool_calls)}'),
                                    'type': 'tool_call'
                                })
            except json.JSONDecodeError:
                pass
        
        if tool_calls:
            return tool_calls
        
        # 策略 3.2: 匹配 function<❘ tool◁sep❘>tool_name 格式 (DeepSeek R1 旧格式)
        func_pattern = r'function<[^>]*>\s*(\w+)\s*```json\s*([\s\S]*?)```'
        matches = re.findall(func_pattern, content)
        for name, args_str in matches:
            try:
                args = json.loads(args_str.strip())
                tool_calls.append({
                    'name': name,
                    'args': args,
                    'id': f'call_{len(tool_calls)}',
                    'type': 'tool_call'
                })
            except json.JSONDecodeError:
                pass
        
        if tool_calls:
            return tool_calls
        
        # 策略 3.3: 直接匹配 JSON 数组 [{"name": ..., "arguments": ...}]
        # 匹配类似: [{"name": "rg_search_keywords", "arguments": {"keywords": "..."}}]
        array_pattern = r'\[\s*\{\s*["\']name["\']\s*:\s*["\']([\w_]+)["\'][\s\S]*?\}\s*\]'
        if re.search(array_pattern, content):
            # 尝试找到并解析整个 JSON 数组
            bracket_start = content.find('[')
            if bracket_start != -1:
                # 找到匹配的右括号
                depth = 0
                for i, c in enumerate(content[bracket_start:]):
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            json_str = content[bracket_start:bracket_start + i + 1]
                            try:
                                parsed = json.loads(json_str)
                                if isinstance(parsed, list):
                                    for item in parsed:
                                        if isinstance(item, dict) and 'name' in item:
                                            name = item.get('name', '')
                                            args = safe_parse_args(item.get('arguments', item.get('args', {})))
                                            if name:
                                                tool_calls.append({
                                                    'name': name,
                                                    'args': args,
                                                    'id': item.get('id', f'call_{len(tool_calls)}'),
                                                    'type': 'tool_call'
                                                })
                            except json.JSONDecodeError:
                                pass
                            break
    
    return tool_calls


def extract_tool_calls_from_content(content: str) -> list:
    """
    从消息内容中提取工具调用。
    这是一个独立函数，用于处理 LLM 返回的工具调用在 content 中的情况。
    """
    tool_calls = []
    
    def safe_parse_args(args):
        if args is None:
            return {}
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return {}
        return {}
    
    if not content:
        return tool_calls
    
    # 策略 1: 匹配 ```json [...] ``` 格式
    json_block_pattern = r'```json\s*\n?([\s\S]*?)\n?```'
    json_matches = re.findall(json_block_pattern, content)
    
    for json_str in json_matches:
        try:
            parsed = json.loads(json_str.strip())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and ('name' in item or 'function' in item):
                        if 'function' in item:
                            func = item['function']
                            name = func.get('name', '')
                            args = safe_parse_args(func.get('arguments', {}))
                        else:
                            name = item.get('name', '')
                            args = safe_parse_args(item.get('arguments', item.get('args', {})))
                        
                        if name:
                            tool_calls.append({
                                'name': name,
                                'args': args,
                                'id': item.get('id', f'call_{len(tool_calls)}'),
                                'type': 'tool_call'
                            })
        except json.JSONDecodeError:
            pass
    
    if tool_calls:
        return tool_calls
    
    # 策略 2: 直接查找 JSON 数组
    bracket_start = content.find('[')
    if bracket_start != -1:
        depth = 0
        for i, c in enumerate(content[bracket_start:]):
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    json_str = content[bracket_start:bracket_start + i + 1]
                    try:
                        parsed = json.loads(json_str)
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and 'name' in item:
                                    name = item.get('name', '')
                                    args = safe_parse_args(item.get('arguments', item.get('args', {})))
                                    if name:
                                        tool_calls.append({
                                            'name': name,
                                            'args': args,
                                            'id': item.get('id', f'call_{len(tool_calls)}'),
                                            'type': 'tool_call'
                                        })
                    except json.JSONDecodeError:
                        pass
                    break
    
    return tool_calls


def fix_message_pairs(messages: list) -> list:
    """
    修复消息历史中的 Tool/AI 配对问题。
    
    DashScope API 要求：
    - 每个 ToolMessage (role="tool") 必须紧跟在带有 tool_calls 的 AIMessage 之后
    - 如果修剪后 ToolMessage 失去了对应的 AIMessage，需要移除这些孤立的 ToolMessage
    
    返回修复后的消息列表。
    """
    if not messages:
        return messages
    
    fixed_messages = []
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        if isinstance(msg, ToolMessage):
            # 检查前一条消息是否是带有 tool_calls 的 AIMessage
            if fixed_messages and isinstance(fixed_messages[-1], AIMessage):
                last_ai = fixed_messages[-1]
                # 检查这个 AIMessage 是否有 tool_calls
                if hasattr(last_ai, 'tool_calls') and last_ai.tool_calls:
                    # 检查 tool_call_id 是否匹配
                    tool_call_ids = {tc.get('id') for tc in last_ai.tool_calls if isinstance(tc, dict)}
                    msg_tool_call_id = getattr(msg, 'tool_call_id', None)
                    
                    if msg_tool_call_id in tool_call_ids or not tool_call_ids:
                        # 配对正确，保留这个 ToolMessage
                        fixed_messages.append(msg)
                    else:
                        # tool_call_id 不匹配，跳过这个 ToolMessage
                        pass
                else:
                    # 前一条 AIMessage 没有 tool_calls，跳过这个 ToolMessage
                    pass
            else:
                # 没有前置的 AIMessage，跳过这个 ToolMessage
                pass
        else:
            # 非 ToolMessage，直接保留
            fixed_messages.append(msg)
        
        i += 1
    
    return fixed_messages


def create_safe_ai_message(response) -> AIMessage:
    """从 LLM 响应创建安全的 AIMessage"""
    content = getattr(response, 'content', '')
    tool_calls = parse_tool_calls_from_response(response)
    
    return AIMessage(
        content=content,
        tool_calls=tool_calls if tool_calls else [],
        additional_kwargs=getattr(response, 'additional_kwargs', {}),
    )


# ============================================================================
# 节点函数
# ============================================================================

def create_librarian_node(model, tools: List):
    """
    创建 Librarian 推理节点。
    
    这是核心的 LLM 调用节点，负责：
    1. 分析当前步骤（从 current_step 读取）
    2. 决定调用哪些工具
    3. 生成最终的候选列表
    
    Args:
        model: LangChain ChatModel 实例
        tools: 绑定了 library_path 的工具列表
    """
    
    def librarian_node(state: LibrarianState) -> dict:
        """Librarian 主推理节点"""
        debug_mode = state.get("debug", False)
        
        # 检查工具调用轮次，防止无限循环
        current_messages = list(state.get("messages", []))
        tool_call_count = sum(1 for m in current_messages if hasattr(m, 'tool_calls') and m.tool_calls)
        
        if tool_call_count >= MAX_TOOL_ITERATIONS:
            if debug_mode:
                print(f"[DEBUG] ⚠️ 已达到最大工具调用轮次 ({MAX_TOOL_ITERATIONS})，强制结束")
            # 返回一个空候选列表的消息
            return {"messages": [AIMessage(
                content="已达到最大搜索轮次，未找到精确匹配。\n```json\n[]\n```",
                tool_calls=[]
            )]}
        
        # 构建系统提示（注入 library_path）
        system_prompt = LIBRARIAN_SYSTEM_PROMPT.format(
            library_path=state.get("library_path", "未指定")
        )
        
        # 消息修剪：保留最近的消息，防止超出上下文窗口
        # 注意：只有当消息数量较多时才进行修剪
        if len(current_messages) > 0:
            # 计算当前消息的大致 Token 数
            approx_tokens = count_tokens_approximately(current_messages)
            
            if approx_tokens > MAX_CONTEXT_TOKENS:
                # 只保留最近的消息，但确保至少保留一条 HumanMessage
                trimmed_messages = trim_messages(
                    current_messages,
                    strategy="last",
                    token_counter=count_tokens_approximately,
                    max_tokens=MAX_CONTEXT_TOKENS,
                    # 移除 start_on 和 end_on 限制，避免全部被裁剪
                    include_system=False,
                )
                
                if debug_mode:
                    print(f"[DEBUG] 📝 消息修剪: {len(current_messages)} → {len(trimmed_messages)} 条 (Token: {approx_tokens} → ≤{MAX_CONTEXT_TOKENS})")
                
                # 修复消息配对：确保 ToolMessage 有对应的 AIMessage
                trimmed_messages = fix_message_pairs(trimmed_messages)
                
                if debug_mode and len(trimmed_messages) != len(current_messages):
                    print(f"[DEBUG] 🔧 消息配对修复后: {len(trimmed_messages)} 条")
            else:
                trimmed_messages = current_messages
        else:
            trimmed_messages = current_messages
        
        # 最终检查：确保消息配对正确（即使没有修剪也要检查）
        trimmed_messages = fix_message_pairs(list(trimmed_messages))
        
        # 构建消息列表：系统提示 + 修剪后的历史消息
        messages = [SystemMessage(content=system_prompt)] + list(trimmed_messages)
        
        # 首次调用时，添加用户任务（从 current_step 或 intent 读取）
        if not any(isinstance(m, HumanMessage) for m in trimmed_messages):
            current_step = state.get("current_step", state.get("intent", {}))
            task_prompt = (
                f"## 任务：为以下 BDD 测试步骤查找候选 AW\n\n"
                f"```json\n{json.dumps(current_step, ensure_ascii=False, indent=2)}\n```\n\n"
                f"### 请按以下步骤执行：\n"
                f"1. **分析步骤**：识别 action_type 和关键实体（如 project, branch, API 等）\n"
                f"2. **搜索 AW 库**：使用工具搜索相关 AW 文件\n"
                f"3. **验证匹配**：读取候选 AW 详情，确认参数和功能\n"
                f"4. **输出结果**：返回 JSON 格式的候选列表\n\n"
                f"开始吧！首先分析步骤，然后调用工具搜索。"
            )
            messages.append(HumanMessage(content=task_prompt))
            
            if debug_mode:
                print("\n" + "="*60)
                print("[DEBUG] 🚀 Librarian Agent 启动")
                print("="*60)
                print(f"[DEBUG] 📥 输入步骤: {current_step.get('step_id', 'N/A')}")
                print(f"[DEBUG] 📝 描述: {current_step.get('description', 'N/A')[:100]}")
                print(f"[DEBUG] 📂 AW 库: {state.get('library_path', 'N/A')}")
                print("-"*60)
        
        # 调用 LLM（绑定工具，让 LLM 自主决定是否调用）
        model_with_tools = model.bind_tools(tools)
        
        try:
            # 尝试正常调用
            response = model_with_tools.invoke(messages)
            safe_response = create_safe_ai_message(response)
        except Exception as e:
            error_str = str(e)
            # 检测 Pydantic 验证错误（tool_calls.args 应该是字典但实际是字符串）
            if "validation error" in error_str.lower() and ("tool_calls" in error_str or "dict_type" in error_str):
                if debug_mode:
                    print(f"[DEBUG] ⚠️ 检测到 DeepSeek R1 tool_calls.args 格式问题，尝试修复...")
                
                # 直接调用底层 API 绕过 LangChain 的 Pydantic 验证
                safe_response = call_llm_raw(model, messages, tools, debug_mode)
            else:
                error_msg = f"LLM 调用出错: {str(e)}"
                if debug_mode:
                    print(f"[DEBUG] ❌ {error_msg}")
                safe_response = AIMessage(content=error_msg, tool_calls=[])
        
        if debug_mode:
            # 计算当前是第几轮
            ai_count = sum(1 for m in state.get("messages", []) if isinstance(m, AIMessage))
            round_num = ai_count + 1
            
            print(f"\n[DEBUG] 🤖 第 {round_num} 轮 LLM 推理")
            print("-"*40)
            
            # 显示 LLM 思考内容（截取关键部分）
            content = safe_response.content or "<空>"
            if content and content != "<空>":
                print("[DEBUG] 💭 LLM 思考:")
                # 显示前800字符，如果有 Thought/Action/Observation 则高亮
                display_content = content[:800]
                print(display_content)
                if len(content) > 800:
                    print(f"... (共 {len(content)} 字符)")
            
            # 显示工具调用
            if safe_response.tool_calls:
                print(f"\n[DEBUG] 🔧 工具调用 ({len(safe_response.tool_calls)} 个):")
                for tc in safe_response.tool_calls:
                    tool_name = tc.get('name', '')
                    tool_args = tc.get('args', {})
                    print(f"  ├─ {tool_name}")
                    for k, v in tool_args.items():
                        # 截断长参数
                        v_str = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
                        print(f"  │   └─ {k}: {v_str}")
            else:
                print("\n[DEBUG] ⏹️ 无工具调用 → 即将进入提取阶段")
            print("-"*40)
        
        # 返回更新后的 messages（LangGraph 会自动累加）
        return {"messages": [safe_response]}
    
    return librarian_node


def should_continue(state: LibrarianState) -> Literal["tools", "extract"]:
    """
    条件路由：判断下一步是调用工具还是提取结果。
    
    LLM 自主决定：
    - 如果返回 tool_calls → 继续调用工具
    - 如果不返回 tool_calls → 进入提取阶段
    """
    messages = state.get("messages", [])
    if not messages:
        return "extract"
    
    last_message = messages[-1]
    
    # 检查 LLM 是否请求调用工具
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        debug_mode = state.get("debug", False)
        if debug_mode:
            tool_names = [tc.get('name') for tc in last_message.tool_calls]
            print(f"[DEBUG] ➡️ 路由: librarian → tools ({', '.join(tool_names)})")
        return "tools"
    
    # 没有工具调用请求，进入提取阶段
    debug_mode = state.get("debug", False)
    if debug_mode:
        print(f"[DEBUG] ➡️ 路由: librarian → extract (提取候选)")
    return "extract"


def extract_candidates_node(state: LibrarianState) -> dict:
    """
    从 LLM 回复中提取候选 AW 列表。
    
    这个节点负责：
    1. 从所有消息中收集 AI 回复
    2. 提取 JSON 格式的候选列表
    3. 清理和丰富候选数据
    4. 更新 state.candidates
    """
    messages = state.get("messages", [])
    current_step = state.get("current_step", state.get("intent", {}))
    debug_mode = state.get("debug", False)
    
    # 收集所有 AI 回复内容
    all_ai_content = []
    for msg in messages:
        if hasattr(msg, 'content') and msg.content:
            all_ai_content.append(msg.content)
    
    combined_content = "\n".join(all_ai_content)
    
    if debug_mode:
        print("\n" + "="*60)
        print("[DEBUG] 📋 提取候选阶段")
        print("="*60)
        print(f"[DEBUG] 消息总数: {len(messages)}")
        # 统计工具调用次数
        tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
        print(f"[DEBUG] 工具调用轮次: {tool_call_count}")
    
    candidates = []
    
    # 策略1: 提取 ```json 代码块
    json_matches = re.findall(r'```json\s*\n?([\s\S]*?)\n?```', combined_content)
    for json_str in json_matches:
        try:
            parsed = json.loads(json_str.strip())
            if isinstance(parsed, list):
                candidates.extend(parsed)
            elif isinstance(parsed, dict) and parsed:
                candidates.append(parsed)
        except json.JSONDecodeError:
            continue
    
    # 策略2: 普通代码块中的 JSON
    if not candidates:
        code_matches = re.findall(r'```\s*\n?([\s\S]*?)\n?```', combined_content)
        for code_str in code_matches:
            code_str = code_str.strip()
            if code_str.startswith('[') or code_str.startswith('{'):
                try:
                    parsed = json.loads(code_str)
                    if isinstance(parsed, list):
                        candidates.extend(parsed)
                    elif isinstance(parsed, dict) and parsed:
                        candidates.append(parsed)
                except json.JSONDecodeError:
                    continue
    
    # 策略3: 直接搜索 JSON 数组
    if not candidates:
        array_pattern = r'\[\s*\{\s*"(?:aw_id|aw_name)"[\s\S]*?\}\s*\]'
        array_matches = re.findall(array_pattern, combined_content)
        for arr_str in array_matches:
            try:
                parsed = json.loads(arr_str)
                if isinstance(parsed, list):
                    candidates.extend(parsed)
            except json.JSONDecodeError:
                continue
    
    # 策略4: 检测空数组
    if not candidates and '[]' in combined_content:
        if debug_mode:
            print("[DEBUG] ✅ 检测到空数组 []，无匹配候选")
        return {"candidates": []}
    
    if debug_mode:
        print(f"[DEBUG] 🎯 JSON 解析结果: {len(candidates)} 个原始候选")
        if candidates:
            for i, c in enumerate(candidates):
                aw_id = c.get('aw_id', c.get('aw_name', ''))
                if aw_id:
                    print(f"  {i+1}. {aw_id}")
                else:
                    print(f"  {i+1}. (无效候选, 将跳过)")
    
    # 清理和丰富候选数据
    enriched_candidates = []
    for c in candidates:
        # 验证候选有效性 - 必须有 aw_id 或 aw_name
        aw_id = c.get('aw_id', '')
        aw_name = c.get('aw_name', '')
        
        # 过滤无效候选（修复 "unknown" 问题）
        if not aw_id and not aw_name:
            continue
        if aw_id in ('unknown', '', None) and aw_name in ('unknown', '', None):
            continue
        
        # 清理 parameters
        if 'parameters' in c and isinstance(c['parameters'], list):
            cleaned_params = []
            for p in c['parameters']:
                if isinstance(p, dict):
                    cleaned_params.append({
                        'name': p.get('name', ''),
                        'type': p.get('type', '')
                    })
            c['parameters'] = cleaned_params
        
        # 附加步骤信息（来自 current_step）
        enriched = {
            "step_id": current_step.get("step_id", ""),
            "description": current_step.get("description", ""),
            "action_type": current_step.get("action_type", current_step.get("check_type", "")),
            "aw_id": aw_id or aw_name,  # 确保有 aw_id
            "aw_name": aw_name or aw_id,  # 确保有 aw_name
        }
        # 复制其他字段
        for key in ['parameters', 'reason', 'confidence']:
            if key in c:
                enriched[key] = c[key]
        
        enriched_candidates.append(enriched)
    
    if debug_mode:
        print("-"*60)
        print(f"[DEBUG] ✅ 最终输出: {len(enriched_candidates)} 个候选")
        for i, c in enumerate(enriched_candidates):
            confidence = c.get('confidence', 'N/A')
            reason = c.get('reason', 'N/A')[:50]
            print(f"  {i+1}. {c.get('aw_id', 'unknown')}")
            print(f"     置信度: {confidence}")
            print(f"     理由: {reason}...")
        print("="*60)
    
    # 更新 state.candidates（这是核心输出，供下游 Agent 使用）
    return {"candidates": enriched_candidates}


# ============================================================================
# 图构建
# ============================================================================

def create_librarian_graph(model, library_path: str):
    """
    构建 Librarian Agent 的 LangGraph 工作流。
    
    状态流转设计：
    ┌─────────────────────────────────────────────────────────┐
    │  上游 (Parser Agent)                                     │
    │    ↓                                                     │
    │  intent (BDD 步骤信息)                                    │
    │    ↓                                                     │
    │  ┌─────────────────────────────────────────────────┐    │
    │  │ Librarian Agent                                  │    │
    │  │   START → librarian ↔ tools → extract → END     │    │
    │  │              ↓                    ↓              │    │
    │  │           messages            candidates         │    │
    │  └─────────────────────────────────────────────────┘    │
    │    ↓                                                     │
    │  candidates (候选 AW 列表)                               │
    │    ↓                                                     │
    │  下游 (Mapper Agent)                                     │
    │    ↓                                                     │
    │  result (最终映射结果)                                   │
    └─────────────────────────────────────────────────────────┘
    
    工作流：
    1. START → librarian: LLM 分析步骤，决定调用哪些工具
    2. librarian → tools: 如果 LLM 请求工具调用
    3. tools → librarian: 工具执行完毕，结果返回给 LLM
    4. librarian → extract: LLM 不再请求工具，进入提取阶段
    5. extract → END: 提取候选列表，更新 state.candidates
    
    Args:
        model: LangChain ChatModel 实例
        library_path: AW 库的根目录路径（用于创建绑定的工具）
        
    Returns:
        编译后的 LangGraph 应用
    """
    # 创建绑定了 library_path 的工具集
    tools = create_tools(library_path)
    
    # 创建工具名称到工具对象的映射
    tool_map = {tool.name: tool for tool in tools}
    
    def tool_executor_node(state: LibrarianState) -> dict:
        """
        自定义工具执行节点。
        直接从 messages 中提取 tool_calls 并执行，避免 ToolNode 的配置问题。
        """
        debug_mode = state.get("debug", False)
        
        if debug_mode:
            print(f"\n[DEBUG] 🔧 执行工具节点")
            print("-"*40)
        
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        tool_calls = getattr(last_message, 'tool_calls', [])
        
        if not tool_calls:
            return {"messages": []}
        
        # 导入 ToolMessage
        from langchain_core.messages import ToolMessage
        
        result_messages = []
        for tc in tool_calls:
            tool_name = tc.get('name', '')
            tool_args = tc.get('args', {})
            tool_id = tc.get('id', '')
            
            if tool_name not in tool_map:
                error_msg = f"未知工具: {tool_name}"
                if debug_mode:
                    print(f"[DEBUG] ❌ {error_msg}")
                result_messages.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name,
                ))
                continue
            
            try:
                tool = tool_map[tool_name]
                # 执行工具
                result = tool.invoke(tool_args)
                
                if debug_mode:
                    display_result = result[:600] if len(result) > 600 else result
                    print(f"[DEBUG] 📤 工具 [{tool_name}] 返回:")
                    print(display_result)
                    if len(result) > 600:
                        print(f"... (共 {len(result)} 字符)")
                
                result_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tool_id,
                    name=tool_name,
                ))
            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                if debug_mode:
                    print(f"[DEBUG] ❌ {error_msg}")
                result_messages.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name,
                ))
        
        if debug_mode:
            print("-"*40)
        
        return {"messages": result_messages}
    
    # 创建状态图（使用自定义的 LibrarianState）
    workflow = StateGraph(LibrarianState)
    
    # 添加节点
    workflow.add_node("librarian", create_librarian_node(model, tools))
    workflow.add_node("tools", tool_executor_node)  # 使用自定义工具执行节点
    workflow.add_node("extract", extract_candidates_node)
    
    # 定义边
    workflow.add_edge(START, "librarian")
    
    # 条件边：LLM 自主决定是否继续调用工具
    workflow.add_conditional_edges(
        "librarian",
        should_continue,
        {
            "tools": "tools",
            "extract": "extract",
        }
    )
    
    # 工具执行后返回 LLM 继续推理
    workflow.add_edge("tools", "librarian")
    
    # 提取完成后结束
    workflow.add_edge("extract", END)
    
    # 编译并返回
    return workflow.compile()
