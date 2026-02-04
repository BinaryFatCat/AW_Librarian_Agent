# The Librarian (LangGraph)

基于 LangGraph 的知识库专家 Agent，只读取 `intent`（BDD JSON），输出每个步骤的 Top‑3 AW 候选到 `candidates`。

## 依赖与运行（uv）

1. 安装依赖

```bash
uv sync
```

2. 运行

```bash
uv run python .\src\run_librarian.py
```

运行后会在终端提示：

- LLM API Base
- LLM API Key
- LLM Model（默认 deepseek-r1）
- 是否禁用系统代理（可选）
- AW 库路径（文件或目录）
- intent JSON 路径
- Top‑N（默认 3）
- 输出 JSON 路径（可选）
- 是否使用异步 LLM（可选）
- 并发限制（异步模式，默认 4）

## 输出

输出为 `candidates` 列表，按 step_id 对应候选 AW：

```json
[
  {
    "step_id": "W1",
    "description": "请求获取该项目的全量分支列表",
    "action_type_or_check_type": "FETCH_LIST",
    "candidates": [
      {
        "aw_id": "com.scm.GitAW#listBranchesByProjectId",
        "parameters": [
          { "name": "pid", "type": "Long", "reason": "描述中包含项目ID" }
        ],
        "reason": "关键词与描述高度匹配"
      }
    ]
  }
]
```

## 说明

- 候选筛选优先使用 AW 的 `keywords` 与 `description`。
- 参数类型由 LLM **仅根据 step 的 `description` 推断**，无法确定时给出最可能类型与理由。
- `State` 结构：只读 `intent`，只写 `candidates`，`result` 不写。
- 默认使用阿里云兼容模式 Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`。
