import os
import json
import httpx
import re
import operator
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, TypedDict, Annotated, Union  # 修改点：导入 Union

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END, START

# --- 动态添加路径以导入 librarian_agent ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from librarian_agent.librarian import run_librarian_async
except ImportError:
    print("❌ 未找到 librarian_agent 模块，请检查目录结构。")
    print("预期结构: ./librarian_agent/librarian.py")
    sys.exit(1)

# ==========================================
# 1. 基础工具配置
# ==========================================

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk--"
DEEPSEEK_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

client = ChatOpenAI(
    model="deepseek-r1",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
    http_client=httpx.Client(trust_env=False),
    http_async_client=httpx.AsyncClient(trust_env=False)
)


def remove_json_comments(json_str: str) -> str:
    """去除 JSON 中的 // 和 /* ... */ 注释"""
    json_str = re.sub(r"//.*", "", json_str)
    json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
    return json_str.strip()


# ==========================================
# 2. 定义 State
# ==========================================

class AgentState(TypedDict):
    intent: Dict
    candidates: List[Dict]
    result: Dict
    # 修改点：使用 Union[A, B, C] 替代 A | B | C，兼容 Python 3.9
    messages: Annotated[List[Union[SystemMessage, HumanMessage, AIMessage]], operator.add]
    iteration: int


# ==========================================
# 3. Architect Agent (核心编排)
# ==========================================

def architect_node(state: AgentState):
    print(f"\n>>> Architect 介入 (第 {state.get('iteration', 1)} 次尝试)")

    intent_str = json.dumps(state["intent"], ensure_ascii=False, indent=2)
    candidates_str = json.dumps(state["candidates"], ensure_ascii=False, indent=2)

    system_prompt = """你是一个测试脚本架构师 (The Architect)。
任务：根据 [BDD 意图] 和 [AW 候选列表]，生成最终的可执行 DSL JSON。

【核心能力要求】
1. **多动作编排**：一个 BDD 步骤可能对应多个 AW，请按逻辑顺序排列。
2. **循环展开**：
   - 如果 BDD 意图中包含数量词（如“复制3本书”、“创建5个用户”），而 AW 只能处理单个对象，**你必须显式生成多个重复的 AW 调用**。
   - 例如：意图“添加3个商品”，应生成 3 个 `addToCart` 动作。
3. **变量链路**：使用 `${var_name}` 传递参数 (例如从 Login 提取 token 传给后续步骤)。
4. **断言合并**：将 BDD 的 `then` 部分转换为 Execution 阶段最后一个 AW 的 `checkpoints`。

【严格输出 Schema】
{
  "test_case_name": "String",
  "given": [ { "step_id": "G1", "aws": [ { "aw_id": "...", "input_args": {...}, "extract": {...} } ] } ],
  "execution": [ ... ],
  "cleanup": [ ... ]
}

**严禁输出任何 Markdown 标记或 // 注释，只输出纯 JSON 文本。**
"""
    user_content = f"【BDD 输入】:\n{intent_str}\n\n【AW 候选列表】:\n{candidates_str}\n\n请生成 DSL JSON。"

    # 构造消息历史
    messages = [SystemMessage(content=system_prompt)]
    if state.get("messages"):
        messages.extend(state["messages"])
    messages.append(HumanMessage(content=user_content))

    print(f"{'=' * 10} 正在调用 DeepSeek-R1 (LangChain) {'=' * 10}")

    response = client.invoke(messages)
    content = response.content

    print("--- 思考与回复 ---")
    print(content)
    print("=" * 30)

    clean_json_str = content.replace("```json", "").replace("```", "").strip()
    if "</think>" in clean_json_str:
        clean_json_str = clean_json_str.split("</think>")[-1].strip()
    clean_json_str = remove_json_comments(clean_json_str)

    try:
        result_json = json.loads(clean_json_str)
    except json.JSONDecodeError as e:
        result_json = {"error": "Invalid JSON", "raw": clean_json_str}

    return {
        "result": result_json,
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=content)]
    }


# ==========================================
# 4. Critic Agent (质量审计)
# ==========================================

def critic_node(state: AgentState):
    print("\n>>> Critic 介入审计")
    generated_json = state["result"]
    candidates_str = json.dumps(state["candidates"], ensure_ascii=False, indent=2)

    if "error" in generated_json:
        return {"messages": [HumanMessage(content="严重错误：生成了无效的 JSON，请检查语法。")]}

    system_prompt = """你是一个质量审计员 (The Critic)。
任务：严格审计 Architect 生成的 DSL JSON。

【审计清单】
1. **结构检查**：必须包含 given, execution, cleanup。
2. **AW 合法性**：JSON 中的 aw_id 必须严格存在于【AW 候选列表】中。
3. **变量闭环**：引用的变量必须在之前的步骤中定义。
4. **参数完整性**：input_args 必须符合参数定义。

回复规则：
- 通过：仅回复 "APPROVE"。
- 驳回：简短列出具体错误。
"""
    user_content = f"【待审计 JSON】:\n{json.dumps(generated_json, indent=2, ensure_ascii=False)}\n\n【参考依据：AW 候选列表】:\n{candidates_str}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content)
    ]

    print(f"{'=' * 10} Critic 正在审计 {'=' * 10}")
    response = client.invoke(messages)
    print(response.content)
    print("=" * 30)

    return {"messages": [HumanMessage(content=f"质量审计反馈: {response.content}")]}


def router(state: AgentState):
    last_message = state["messages"][-1]
    if "APPROVE" in last_message.content.upper():
        print("\n*** 🟢 审计通过 ***")
        return END
    if state["iteration"] >= 3:
        print("\n*** 🔴 超过重试上限 ***")
        return END
    print(f"\n*** 🟡 审计驳回，重写中... ***")
    return "architect"


# ==========================================
# 5. 主程序入口
# ==========================================

async def main():
    # --- 1. 定义 Parser 输出 (模拟输入) ---
    mock_parser_output = {
        "scenario_metadata": {
            "intent_summary": "创建项目并获取分支列表",
            "complexity": "medium"
        },
        "bdd_flow": {
            "given": [
                {"step_id": "G1", "description": "创建一个新的项目", "action_type": "CREATE"}
            ],
            "when": [
                {"step_id": "W1", "description": "根据项目ID获取分支列表", "action_type": "FETCH_LIST"}
            ],
            "then": [
                {"step_id": "T1", "description": "列表不为空", "check_type": "NOT_NULL"}
            ],
            "cleanup": [
                {"step_id": "C1", "description": "删除该项目", "action_type": "DELETE"}
            ]
        }
    }

    # --- 2. 调用真实的 Librarian Agent ---
    print("\n>>> 正在调用 Librarian 检索 AW 库...")

    # test_samples 位于项目根目录 (与 src/ 同级)
    project_root = Path(__file__).parent.parent
    aw_lib_path = str(project_root / "test_samples")

    # 这里的 llm 专门传给 Librarian 使用
    librarian_llm = ChatOpenAI(
        model="deepseek-r1",
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0,
        http_client=httpx.Client(trust_env=False),
        http_async_client=httpx.AsyncClient(trust_env=False)
    )

    real_librarian_output = await run_librarian_async(
        intent=mock_parser_output,
        aw_path=aw_lib_path,
        llm=librarian_llm,
        top_n=3
    )

    print(f"✅ Librarian 检索完成，找到 {sum(len(s['candidates']) for s in real_librarian_output)} 个候选 AW。")

    # --- 3. 启动 Architect + Critic 工作流 ---
    print("\n>>> 启动 Architect & Critic 编排...")

    workflow = StateGraph(AgentState)
    workflow.add_node("architect", architect_node)
    workflow.add_node("critic", critic_node)
    workflow.add_edge(START, "architect")
    workflow.add_edge("architect", "critic")
    workflow.add_conditional_edges("critic", router, {"architect": "architect", END: END})
    app = workflow.compile()

    final_state = await app.ainvoke({
        "intent": mock_parser_output,
        "candidates": real_librarian_output,
        "iteration": 0,
        "messages": []
    })

    if "result" in final_state and "error" not in final_state["result"]:
        print("\n################ 最终 DSL JSON ################")
        print(json.dumps(final_state["result"], indent=2, ensure_ascii=False))
    else:
        print("\n################ 生成失败 ################")
        print(final_state.get("result"))


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())