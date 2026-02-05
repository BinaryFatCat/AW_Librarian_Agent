"""
Librarian Agent 对外接口模块
提供简化的异步/同步调用接口，用于集成到其他系统
"""

import json
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI

from .graph import create_librarian_graph
from .state import LibrarianState


def extract_all_steps(parser_data: dict) -> list:
    """从 BDD 结构中提取所有步骤"""
    flow = parser_data.get("bdd_flow", {})
    steps = []
    
    for phase in ["given", "when", "then", "cleanup"]:
        phase_steps = flow.get(phase, [])
        for step in phase_steps:
            step["phase"] = phase  # 添加阶段标识
            steps.append(step)
    
    return steps


async def run_librarian_async(
    intent: dict,
    aw_path: str,
    llm: ChatOpenAI,
    top_n: int = 3,
    debug: bool = False,
) -> List[Dict]:
    """
    异步运行 Librarian Agent，为每个 BDD 步骤匹配候选 AW。
    
    这是提供给外部系统调用的主要接口。
    
    Args:
        intent: Parser Agent 输出的 BDD 结构（包含 bdd_flow）
        aw_path: AW 知识库的本地路径（Markdown 文件所在目录）
        llm: LangChain ChatOpenAI 实例
        top_n: 每个步骤返回的最大候选数量（默认 3）
        debug: 是否启用调试输出
        
    Returns:
        候选 AW 列表，格式:
        [
            {
                "step_id": "G1",
                "phase": "given",
                "description": "...",
                "action_type": "...",
                "candidates": [
                    {"aw_id": "...", "aw_name": "...", "parameters": [...], "reason": "..."},
                    ...
                ]
            },
            ...
        ]
    """
    # 创建 LangGraph 工作流
    app = create_librarian_graph(llm, aw_path)
    
    # 提取所有步骤
    all_steps = extract_all_steps(intent)
    
    if debug:
        print(f"[Librarian] 共 {len(all_steps)} 个步骤需要匹配")
    
    # 处理每个步骤
    all_results = []
    
    for i, step in enumerate(all_steps, 1):
        step_id = step.get("step_id", f"S{i}")
        description = step.get("description", "")
        phase = step.get("phase", "unknown")
        
        if debug:
            print(f"[Librarian] 处理步骤 {step_id} ({phase}): {description[:50]}...")
        
        # 构建初始状态
        initial_state: LibrarianState = {
            "intent": intent,
            "messages": [],
            "candidates": [],
            "result": {},
            "library_path": aw_path,
            "current_step": step,
            "debug": debug,
        }
        
        try:
            # 异步运行 Agent
            final_state = await app.ainvoke(initial_state)
            
            candidates = final_state.get("candidates", [])
            
            # 限制返回数量
            if len(candidates) > top_n:
                candidates = candidates[:top_n]
            
            if debug:
                print(f"[Librarian] ✅ {step_id}: 找到 {len(candidates)} 个候选 AW")
            
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": candidates,
            })
            
        except Exception as e:
            if debug:
                print(f"[Librarian] ❌ {step_id}: 处理失败 - {str(e)}")
            
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": [],
                "error": str(e),
            })
    
    return all_results


def run_librarian_sync(
    intent: dict,
    aw_path: str,
    llm: ChatOpenAI,
    top_n: int = 3,
    debug: bool = False,
) -> List[Dict]:
    """
    同步运行 Librarian Agent（阻塞式）。
    
    接口与 run_librarian_async 相同，适用于不需要异步的场景。
    """
    # 创建 LangGraph 工作流
    app = create_librarian_graph(llm, aw_path)
    
    # 提取所有步骤
    all_steps = extract_all_steps(intent)
    
    if debug:
        print(f"[Librarian] 共 {len(all_steps)} 个步骤需要匹配")
    
    # 处理每个步骤
    all_results = []
    
    for i, step in enumerate(all_steps, 1):
        step_id = step.get("step_id", f"S{i}")
        description = step.get("description", "")
        phase = step.get("phase", "unknown")
        
        if debug:
            print(f"[Librarian] 处理步骤 {step_id} ({phase}): {description[:50]}...")
        
        # 构建初始状态
        initial_state: LibrarianState = {
            "intent": intent,
            "messages": [],
            "candidates": [],
            "result": {},
            "library_path": aw_path,
            "current_step": step,
            "debug": debug,
        }
        
        try:
            # 同步运行 Agent
            final_state = app.invoke(initial_state)
            
            candidates = final_state.get("candidates", [])
            
            # 限制返回数量
            if len(candidates) > top_n:
                candidates = candidates[:top_n]
            
            if debug:
                print(f"[Librarian] ✅ {step_id}: 找到 {len(candidates)} 个候选 AW")
            
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": candidates,
            })
            
        except Exception as e:
            if debug:
                print(f"[Librarian] ❌ {step_id}: 处理失败 - {str(e)}")
            
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": [],
                "error": str(e),
            })
    
    return all_results
