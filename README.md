# 📚 Librarian Agent

> 基于 LangGraph 的智能 AW (Action Word) 知识库匹配 Agent

## 🎯 项目概述

Librarian Agent 是一个自主搜索和匹配的 AI Agent，用于将 BDD 测试步骤（由上游 Parser Agent 解析）与 AW 知识库中的定义进行匹配。它采用 **ReAct (Reasoning + Acting)** 模式，让 LLM 自主决定搜索策略、调用工具、验证结果，最终输出候选 AW 列表。

### 核心特性

- 🧠 **ReAct 自主推理** - LLM 自主选择工具，多轮探索 AW 库
- 🔧 **多工具协作** - ripgrep/grep/find/cat 等工具链
- 🔄 **状态流转** - 基于 LangGraph StateGraph 的状态管理
- 🛡️ **容错机制** - 处理 DeepSeek R1 的特殊格式、消息配对修复
- 📊 **Debug 模式** - 详细的推理过程可视化

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  上游: Parser Agent                                          │
│    ↓ (intent: BDD 步骤信息)                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Librarian Agent                            ││
│  │                                                         ││
│  │   ┌─────────┐     ┌───────┐     ┌─────────┐            ││
│  │   │librarian│ ←→  │ tools │  →  │ extract │            ││
│  │   │  (LLM)  │     │(执行器)│     │(提取器) │            ││
│  │   └─────────┘     └───────┘     └─────────┘            ││
│  │        ↓                              ↓                 ││
│  │    messages                      candidates             ││
│  └─────────────────────────────────────────────────────────┘│
│    ↓ (candidates: 候选 AW 列表)                              │
│  下游: Mapper Agent                                          │
└─────────────────────────────────────────────────────────────┘
```

### 工作流程

```
START → librarian → [有tool_calls?]
                         │
          ┌──── Yes ─────┤
          ↓              │
       tools ───────→ librarian
                         │
          ┌──── No ──────┤
          ↓
       extract → END
```

1. **START → librarian**: LLM 分析 BDD 步骤，决定调用哪些工具
2. **librarian ↔ tools**: 循环执行工具调用（最多 20 轮）
3. **librarian → extract**: LLM 完成搜索，输出 JSON 候选列表
4. **extract → END**: 解析 JSON，更新 `state.candidates`

## 📁 项目结构

```
Librarian_Agent/
├── src/
│   ├── main.py                 # 多 Agent 主入口（集成 Architect + Critic）
│   └── librarian_agent/        # Librarian Agent 包
│       ├── __init__.py         # 包导出
│       ├── librarian.py        # 对外接口 (run_librarian_async/sync)
│       ├── graph.py            # LangGraph 工作流核心
│       ├── state.py            # 状态定义 (LibrarianState)
│       ├── tools.py            # 搜索工具集
│       └── main.py             # 独立 CLI 入口
├── test_samples/               # 测试数据
│   ├── aws/                    # AW 知识库示例
│   │   ├── aw_createProject.md
│   │   ├── aw_listProjects.md
│   │   └── ...
│   ├── intent_sample.json
│   └── intent_sample_multi.json
├── pyproject.toml              # 项目配置
├── aw库模板.md                  # AW 文件模板
└── README.md
```

## 🔧 模块详解

### 1. `state.py` - 状态定义

定义 `LibrarianState` TypedDict，管理 Agent 的全部状态：

```python
class LibrarianState(TypedDict):
    intent: dict            # 上游 Parser 输入的 BDD 步骤
    messages: List[Message] # 对话历史（自动累加）
    candidates: List[dict]  # 输出：候选 AW 列表
    result: dict            # 下游 Mapper 填充
    library_path: str       # AW 库路径
    current_step: dict      # 当前处理的步骤
    debug: bool             # 调试开关
```

### 2. `tools.py` - 工具集

使用**工厂模式**创建绑定了 `library_path` 的工具：

| 工具名                | 功能                  | 使用场景              |
| --------------------- | --------------------- | --------------------- |
| `find_aw_files`       | 列出库中所有 .md 文件 | 首次探索库结构        |
| `rg_search_keywords`  | ripgrep 关键词搜索    | 快速定位 AW 文件      |
| `grep_search_pattern` | 正则模式搜索          | 搜索 YAML frontmatter |
| `cat_read_file`       | 读取文件完整内容      | 验证 AW 参数和功能    |
| `extract_aw_metadata` | 提取 YAML 元数据      | 获取结构化信息        |

#### 核心函数

| 函数                         | 功能说明                                   |
| ---------------------------- | ------------------------------------------ |
| `create_tools(library_path)` | 工厂函数：创建绑定了 library_path 的工具集 |
| `_rg_search()`               | ripgrep 搜索实现，支持多关键词             |
| `_grep_search()`             | PowerShell Select-String 搜索              |
| `_find_files()`              | 遍历目录列出 .md 文件                      |
| `_read_file()`               | 读取文件内容，支持模糊路径匹配             |
| `_extract_metadata()`        | 解析 YAML frontmatter 和参数表             |

### 3. `librarian.py` - 对外接口

提供简化的异步/同步调用接口，用于集成到其他系统：

```python
async def run_librarian_async(
    intent: dict,       # Parser Agent 输出的 BDD 结构
    aw_path: str,       # AW 知识库路径
    llm: ChatOpenAI,    # LangChain ChatOpenAI 实例
    top_n: int = 3,     # 每步返回的最大候选数
    debug: bool = False
) -> List[Dict]:
    """异步运行 Librarian，为每个 BDD 步骤匹配候选 AW"""

def run_librarian_sync(...) -> List[Dict]:
    """同步版本"""
```

### 4. `graph.py` - LangGraph 核心

#### 配置参数

```python
MAX_CONTEXT_TOKENS = 8000   # 最大上下文 Token 数
MAX_TOOL_ITERATIONS = 20    # 最大工具调用轮次
```

#### 核心函数

| 函数                                          | 功能                               |
| --------------------------------------------- | ---------------------------------- |
| `create_librarian_graph(model, library_path)` | 构建并编译 LangGraph 工作流        |
| `create_librarian_node(model, tools)`         | 创建 LLM 推理节点（核心）          |
| `tool_executor_node(state)`                   | 自定义工具执行节点                 |
| `extract_candidates_node(state)`              | 从 LLM 输出解析候选列表            |
| `should_continue(state)`                      | 条件路由：继续工具调用 or 提取结果 |

#### 容错函数

| 函数                                       | 处理问题                                        |
| ------------------------------------------ | ----------------------------------------------- |
| `call_llm_raw(model, messages, tools)`     | 绕过 LangChain Pydantic 验证，直接调用 API      |
| `parse_tool_calls_from_response(response)` | 安全解析 tool_calls（处理 args 为 JSON 字符串） |
| `extract_tool_calls_from_content(content)` | 从 content 中提取工具调用 JSON                  |
| `fix_message_pairs(messages)`              | 修复 Tool/AI 消息配对（防止 API 400 错误）      |
| `create_safe_ai_message(response)`         | 创建安全的 AIMessage                            |

#### LLM 调用流程

```python
try:
    response = model_with_tools.invoke(messages)
    safe_response = create_safe_ai_message(response)
except Exception as e:
    if "validation error" in str(e):
        # Pydantic 验证失败，使用原始 API 调用
        safe_response = call_llm_raw(model, messages, tools)
```

### 5. `src/main.py` - 多 Agent 主入口

集成 Librarian + Architect + Critic 的完整工作流：

```
Parser Output → Librarian → Architect ↔ Critic → DSL JSON
                   ↓             ↓
              候选 AW        生成/审计循环
```

#### Agent 职责

| Agent         | 职责                            |
| ------------- | ------------------------------- |
| **Librarian** | 搜索 AW 库，返回候选列表        |
| **Architect** | 根据候选 AW 生成可执行 DSL JSON |
| **Critic**    | 审计 DSL 质量，驳回或通过       |

#### 运行完整流程

```bash
cd src
uv run python main.py
```

### 6. `librarian_agent/main.py` - 独立 CLI 入口

单独运行 Librarian Agent：

#### 命令行模式

```bash
uv run python -m librarian_agent.main \
  --intent test_samples/intent_sample.json \
  --library test_samples/aws \
  --output librarian_output.json \
  --debug
```

#### 交互模式

```bash
uv run python -m librarian_agent.main
```

#### 核心函数

| 函数                                          | 功能                           |
| --------------------------------------------- | ------------------------------ |
| `main()`                                      | 入口，解析命令行参数           |
| `run_librarian(config)`                       | 同步模式执行                   |
| `run_librarian_async(config)`                 | 异步模式执行（使用 `ainvoke`） |
| `extract_all_steps(parser_data)`              | 从 BDD 结构提取所有步骤        |
| `_save_results(config, parser_data, results)` | 保存结果到 JSON 文件           |
| `get_user_config()`                           | 交互式获取用户配置             |

## 🚀 快速开始

### 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 配置环境变量

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY = "your-api-key"
$env:MODEL_NAME = "deepseek-r1"  # 可选

# Linux/macOS
export DASHSCOPE_API_KEY="your-api-key"
```

### 运行

```bash
# 基本运行
uv run python -m librarian_agent.main \
  --intent test_samples/intent_sample.json \
  --library test_samples/aws

# 启用调试模式（查看 LLM 推理过程）
uv run python -m librarian_agent.main \
  --intent test_samples/intent_sample.json \
  --library test_samples/aws \
  --debug

# 异步模式
uv run python -m librarian_agent.main \
  --intent test_samples/intent_sample.json \
  --library test_samples/aws \
  --async
```

## 📤 输入/输出格式

### 输入：Parser Agent 输出

```json
{
  "scenario_metadata": {
    "feature": "项目管理",
    "scenario": "创建新项目"
  },
  "bdd_flow": {
    "given": [
      {
        "step_id": "G1",
        "description": "用户已登录系统",
        "action_type": "API_CALL"
      }
    ],
    "when": [...],
    "then": [...],
    "cleanup": [...]
  }
}
```

### 输出：候选 AW 列表

```json
{
  "metadata": {
    "generated_at": "2024-01-01T12:00:00",
    "model": "deepseek-r1",
    "library_path": "/path/to/aws"
  },
  "librarian_output": [
    {
      "step_id": "G1",
      "description": "用户已登录系统",
      "action_type": "API_CALL",
      "candidates": [
        {
          "aw_id": "aw_login",
          "aw_name": "用户登录",
          "parameters": [
            { "name": "username", "type": "string" },
            { "name": "password", "type": "string" }
          ],
          "reason": "步骤描述登录操作，与 AW 功能完全匹配"
        }
      ]
    }
  ]
}
```

## 🐛 调试模式

启用 `--debug` 查看详细的推理过程：

```
============================================================
[DEBUG] 🚀 Librarian Agent 启动
============================================================
[DEBUG] 📥 输入步骤: G1
[DEBUG] 📝 描述: 调用项目列表 API 获取所有项目

[DEBUG] 🤖 第 1 轮 LLM 推理
----------------------------------------
[DEBUG] 💭 LLM 思考:
分析步骤：action_type 是 API_CALL，关键词包括"项目列表"...

[DEBUG] 🔧 工具调用 (2 个):
  ├─ find_aw_files
  │   └─ name_contains: None
  ├─ rg_search_keywords
  │   └─ keywords: project,list,项目,列表

[DEBUG] 🔧 执行工具节点
----------------------------------------
[DEBUG] 📤 工具 [find_aw_files] 返回:
=== AW 库文件列表 ===
共 9 个文件:
  - aw_createProject.md
  - aw_listProjects.md
  ...
```

## ⚙️ 配置说明

### 环境变量

| 变量名              | 说明                | 默认值                                              |
| ------------------- | ------------------- | --------------------------------------------------- |
| `DASHSCOPE_API_KEY` | DashScope API Key   | -                                                   |
| `OPENAI_API_KEY`    | OpenAI 格式 API Key | -                                                   |
| `OPENAI_API_BASE`   | API Base URL        | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME`        | 模型名称            | `deepseek-r1`                                       |

### 内部参数

在 `graph.py` 中可调整：

```python
MAX_CONTEXT_TOKENS = 8000   # 增大以支持更长对话
MAX_TOOL_ITERATIONS = 20    # 增大允许更多搜索轮次
```

## 🔧 技术细节

### DeepSeek R1 兼容性处理

DeepSeek R1 通过 DashScope API 返回的 `tool_calls.args` 是 **JSON 字符串**而非字典，导致 LangChain Pydantic 验证失败：

```python
# DeepSeek 返回格式
{"args": '{"keywords": "project"}'}  # ❌ 字符串

# 标准格式
{"args": {"keywords": "project"}}    # ✅ 字典
```

**解决方案**：

1. 捕获 Pydantic 验证错误
2. 使用 `call_llm_raw()` 直接调用 API
3. 手动解析 `args`：`json.loads(args)`

### 消息配对修复

DashScope 要求 `ToolMessage` 必须紧跟带 `tool_calls` 的 `AIMessage`。消息修剪可能破坏配对：

```python
def fix_message_pairs(messages):
    """移除孤立的 ToolMessage"""
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if 前一条是带tool_calls的AIMessage:
                保留
            else:
                跳过  # 防止 API 400 错误
```

### 工具调用解析策略

`parse_tool_calls_from_response()` 采用多策略解析：

1. **策略 1**: 直接从 `response.tool_calls` 解析
2. **策略 2**: 从 `additional_kwargs.tool_calls` 解析（OpenAI 格式）
3. **策略 3.1**: 匹配 ` ```json [...] ``` ` 代码块
4. **策略 3.2**: 匹配 `function<>tool_name` 格式
5. **策略 3.3**: 直接查找 JSON 数组

## 📝 AW 库格式

参考 `aw库模板.md`：

```markdown
---
id: aw_createProject
name: 创建项目
---

# 创建项目

## 功能描述

调用 API 创建新项目

## 参数

| 参数名        | 类型   | 必填 | 说明     |
| ------------- | ------ | ---- | -------- |
| `projectName` | string | 是   | 项目名称 |

## 关键词

创建, 项目, create, project
```

## 🔗 多 Agent 架构

本项目是测试自动化 Multi-Agent 系统的核心组件：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Parser    │ →   │  Librarian  │ →   │  Architect  │ ↔   │   Critic    │
│   Agent     │     │   Agent     │     │   Agent     │     │   Agent     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      ↓                   ↓                   ↓                   ↓
  BDD 解析          AW 候选匹配         DSL 生成            质量审计
```

| Agent     | 输入          | 输出            |
| --------- | ------------- | --------------- |
| Parser    | 测试用例文本  | BDD 结构 (JSON) |
| Librarian | BDD 结构      | 候选 AW 列表    |
| Architect | BDD + 候选 AW | 可执行 DSL JSON |
| Critic    | DSL JSON      | APPROVE / 驳回  |

## 📄 License

MIT License
