from __future__ import annotations

import json
import asyncio
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END


class State(TypedDict):
    intent: dict
    candidates: list[dict]
    result: dict


@dataclass
class AwRecord:
    aw_id: str
    name: str
    category: str
    description: str
    keywords: list[str]
    tags: list[str]
    parameters: list[dict]
    source_path: str


def _parse_front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    front = parts[1]
    data: dict[str, str] = {}
    for line in front.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _extract_between(text: str, start_marker: str, end_markers: Iterable[str]) -> str:
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    slice_text = text[start_idx:]
    end_idx = len(slice_text)
    for marker in end_markers:
        marker_idx = slice_text.find(marker)
        if marker_idx != -1:
            end_idx = min(end_idx, marker_idx)
    return slice_text[:end_idx].strip()


def _extract_line_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _parse_parameters(text: str) -> list[dict]:
    params: list[dict] = []
    table_start = None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().startswith("| 参数名"):
            table_start = idx + 2
            break
    if table_start is None:
        return params
    for line in lines[table_start:]:
        if not line.strip().startswith("|"):
            break
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 5:
            continue
        name = cols[0].strip("`")
        if not name or "{{" in name:
            continue
        params.append(
            {
                "name": name,
                "type": cols[1],
                "required": cols[2],
                "default": cols[3],
                "description": cols[4],
            }
        )
    return params


def _parse_aw_text(text: str, source_path: str) -> AwRecord | None:
    if "{{" in text:
        return None
    front = _parse_front_matter(text)
    aw_id = front.get("id", "").strip()
    name = front.get("name", "").strip()
    category = front.get("category", "").strip()
    description = front.get("description", "").strip()
    keywords_line = _extract_line_value(text, "> 关键词:")
    tags_line = _extract_line_value(text, "> 场景标签:")
    keywords = [k.strip() for k in re.split(r"[,，;；]", keywords_line) if k.strip()]
    tags = [t.strip() for t in re.split(r"[,，;；]", tags_line) if t.strip()]
    brief_desc = _extract_between(text, "**简要描述**:", ["## 2.", "## 3.", "## 4."])
    if brief_desc:
        description = brief_desc
    parameters = _parse_parameters(text)
    if not aw_id and not name:
        return None
    return AwRecord(
        aw_id=aw_id or name,
        name=name,
        category=category,
        description=description,
        keywords=keywords,
        tags=tags,
        parameters=parameters,
        source_path=source_path,
    )


def _split_aw_documents(text: str) -> list[str]:
    lines = text.splitlines()
    docs: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "---":
            i += 1
            continue
        i += 1
        front_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "---":
            front_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            break
        i += 1
        body_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "---":
            body_lines.append(lines[i])
            i += 1
        doc = "---\n" + "\n".join(front_lines) + "\n---\n" + "\n".join(body_lines)
        docs.append(doc)
    return docs


def load_aw_library(path_str: str) -> list[AwRecord]:
    path = Path(path_str)
    files: list[Path] = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.rglob("*.md"))
    print(f"[Librarian] 发现 AW 文件数: {len(files)}", flush=True)
    records: list[AwRecord] = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        docs = _split_aw_documents(text)
        if not docs:
            docs = [text]
        for doc in docs:
            record = _parse_aw_text(doc, str(file))
            if record:
                records.append(record)
    print(f"[Librarian] 解析 AW 记录数: {len(records)}", flush=True)
    return records


def _rg_search(path: str, query: str) -> set[str]:
    if not shutil.which("rg"):
        return set()
    try:
        result = subprocess.run(
            ["rg", "-l", query, path],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if result.returncode not in (0, 1):
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _simple_overlap_score(query: str, record: AwRecord) -> float:
    query = query.lower()
    text = " ".join(record.keywords + [record.description, record.name]).lower()
    tokens = [t for t in re.split(r"\W+", query) if t]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in text)
    return hits / max(len(tokens), 1)


def _prefilter_records(records: list[AwRecord], query: str, aw_path: str) -> list[AwRecord]:
    matches = _rg_search(aw_path, query)
    if matches:
        filtered = [r for r in records if r.source_path in matches]
        if filtered:
            return filtered
    scored = sorted(records, key=lambda r: _simple_overlap_score(query, r), reverse=True)
    return scored[:20]


def _build_prompt(step: dict, records: list[AwRecord], top_n: int) -> list:
    system = (
        "你是知识库专家 The Librarian。请根据候选 AW 列表，优先使用 keywords 与 description "
        "判断匹配度，必须返回 Top-{top_n} 个最相关候选（不足时也要补足为 {top_n} 个）。"
        "候选只能从提供列表中选择，禁止虚构 aw_id。"
        "参数类型只能从 step 的 description 推断，若无法确定则给出最可能类型并说明理由。"
        "仅返回 JSON，不要输出多余文本。"
    ).format(top_n=top_n)

    aw_payload = []
    for r in records:
        aw_payload.append(
            {
                "aw_id": r.aw_id,
                "name": r.name,
                "category": r.category,
                "keywords": r.keywords,
                "description": r.description,
                "parameters": r.parameters,
            }
        )

    user = {
        "step": step,
        "candidates": aw_payload,
        "output_schema": {
            "step_id": "string",
            "description": "string",
            "action_type_or_check_type": "string",
            "candidates": [
                {
                    "aw_id": "string",
                    "parameters": [
                        {"name": "string", "type": "string", "reason": "string"}
                    ],
                    "reason": "string"
                }
            ]
        },
        "rules": {
            "top_n": top_n,
            "focus": ["keywords", "description"],
            "must_return_top_n": True,
        },
    }

    return [SystemMessage(content=system), HumanMessage(content=json.dumps(user, ensure_ascii=False))]


def _call_llm(llm: ChatOpenAI, messages: list) -> dict | None:
    response = llm.invoke(messages)
    text = response.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


async def _call_llm_async(llm: ChatOpenAI, messages: list) -> dict | None:
    response = await llm.ainvoke(messages)
    text = response.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _fallback_candidates(step: dict, records: list[AwRecord], top_n: int) -> dict:
    query = step.get("description", "")
    ranked = sorted(records, key=lambda r: _simple_overlap_score(query, r), reverse=True)[:top_n]
    return {
        "step_id": step.get("step_id"),
        "description": step.get("description"),
        "action_type_or_check_type": step.get("action_type") or step.get("check_type"),
        "candidates": [
            {
                "aw_id": r.aw_id,
                "parameters": [
                    {
                        "name": p.get("name", ""),
                        "type": p.get("type", "string"),
                        "reason": "无法从描述推断，沿用AW参数类型",
                    }
                    for p in r.parameters
                ],
                "reason": "回退策略：关键词/描述覆盖度最高",
            }
            for r in ranked
        ],
    }


def _ensure_top_n(result: dict, records: list[AwRecord], step: dict, top_n: int) -> dict:
    allowed = {r.aw_id: r for r in records}
    raw = result.get("candidates", []) or []
    cleaned: list[dict] = []
    seen: set[str] = set()

    for item in raw:
        aw_id = item.get("aw_id")
        if aw_id not in allowed or aw_id in seen:
            continue
        record = allowed[aw_id]
        params = item.get("parameters") or []
        if not params:
            params = [
                {
                    "name": p.get("name", ""),
                    "type": p.get("type", "string"),
                    "reason": "沿用AW参数类型",
                }
                for p in record.parameters
            ]
        cleaned.append(
            {
                "aw_id": aw_id,
                "parameters": params,
                "reason": item.get("reason") or "候选匹配",
            }
        )
        seen.add(aw_id)

    target_n = min(top_n, len(records)) if records else 0
    if len(cleaned) < target_n:
        remaining = [r for r in records if r.aw_id not in seen]
        remaining_sorted = sorted(
            remaining,
            key=lambda r: _simple_overlap_score(step.get("description", ""), r),
            reverse=True,
        )
        for r in remaining_sorted:
            if len(cleaned) >= target_n:
                break
            cleaned.append(
                {
                    "aw_id": r.aw_id,
                    "parameters": [
                        {
                            "name": p.get("name", ""),
                            "type": p.get("type", "string"),
                            "reason": "补齐候选：沿用AW参数类型",
                        }
                        for p in r.parameters
                    ],
                    "reason": "补齐 Top-N 候选",
                }
            )
            seen.add(r.aw_id)

    if not cleaned and records:
        cleaned = _fallback_candidates(step, records, target_n).get("candidates", [])

    result["candidates"] = cleaned
    result["step_id"] = result.get("step_id") or step.get("step_id")
    result["description"] = result.get("description") or step.get("description")
    if "scenario_id" in step and "scenario_id" not in result:
        result["scenario_id"] = step.get("scenario_id")
    if "action_type_or_check_type" not in result:
        result["action_type_or_check_type"] = step.get("action_type") or step.get("check_type")
    return result

def _normalize_intents(intent_input: Any) -> list[dict]:
    if isinstance(intent_input, list):
        return [i for i in intent_input if isinstance(i, dict)]
    if isinstance(intent_input, dict) and isinstance(intent_input.get("scenarios"), list):
        return [i for i in intent_input["scenarios"] if isinstance(i, dict)]
    return [intent_input] if isinstance(intent_input, dict) else []


def _iterate_steps(intent_input: Any) -> list[dict]:
    steps: list[dict] = []
    intents = _normalize_intents(intent_input)
    for idx, intent in enumerate(intents, start=1):
        scenario_meta = intent.get("scenario_metadata", {}) if isinstance(intent, dict) else {}
        scenario_id = scenario_meta.get("id") or f"scenario_{idx}"
        bdd_flow = intent.get("bdd_flow", {}) if isinstance(intent, dict) else {}
        for phase in ("given", "when", "then", "cleanup"):
            for step in bdd_flow.get(phase, []) or []:
                step_copy = dict(step)
                step_copy["phase"] = phase
                step_copy["scenario_id"] = scenario_id
                steps.append(step_copy)
    return steps


def build_candidates(state: State, llm: ChatOpenAI, aw_records: list[AwRecord], aw_path: str, top_n: int) -> dict:
    intent = state.get("intent", {})
    steps = _iterate_steps(intent)
    print(f"[Librarian] 同步模式步骤数: {len(steps)}", flush=True)
    results: list[dict] = []
    for idx, step in enumerate(steps, start=1):
        desc = step.get("description", "")
        print(f"[Librarian] 处理步骤 {idx}/{len(steps)}: {desc[:60]}", flush=True)
        query = step.get("description", "")
        prefiltered = _prefilter_records(aw_records, query, aw_path)
        messages = _build_prompt(step, prefiltered, top_n)
        llm_result = _call_llm(llm, messages)
        if not llm_result:
            llm_result = _fallback_candidates(step, prefiltered, top_n)
        llm_result = _ensure_top_n(llm_result, prefiltered, step, top_n)
        results.append(llm_result)
    return {"candidates": results}


async def build_candidates_async(
    state: State,
    llm: ChatOpenAI,
    aw_records: list[AwRecord],
    aw_path: str,
    top_n: int,
    max_concurrency: int = 4,
) -> dict:
    intent = state.get("intent", {})
    steps = _iterate_steps(intent)
    print(
        f"[Librarian] 异步模式步骤数: {len(steps)} (并发={max(1, max_concurrency)})",
        flush=True,
    )
    results: list[dict] = []
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _process_step(step: dict) -> dict:
        async with semaphore:
            desc = step.get("description", "")
            print(f"[Librarian] 开始处理: {desc[:60]}", flush=True)
            query = step.get("description", "")
            prefiltered = _prefilter_records(aw_records, query, aw_path)
            messages = _build_prompt(step, prefiltered, top_n)
            llm_result = await _call_llm_async(llm, messages)
            if not llm_result:
                llm_result = _fallback_candidates(step, prefiltered, top_n)
            result = _ensure_top_n(llm_result, prefiltered, step, top_n)
            print(f"[Librarian] 完成处理: {desc[:60]}", flush=True)
            return result

    if steps:
        results = list(await asyncio.gather(*[_process_step(step) for step in steps]))
    return {"candidates": results}


def make_graph(llm: ChatOpenAI, aw_records: list[AwRecord], aw_path: str, top_n: int) -> StateGraph:
    graph = StateGraph(State)

    def _build(state: State) -> dict:
        return build_candidates(state, llm, aw_records, aw_path, top_n)

    graph.add_node("build_candidates", _build)
    graph.set_entry_point("build_candidates")
    graph.add_edge("build_candidates", END)
    return graph


def make_graph_async(
    llm: ChatOpenAI,
    aw_records: list[AwRecord],
    aw_path: str,
    top_n: int,
    max_concurrency: int,
) -> StateGraph:
    graph = StateGraph(State)

    async def _build(state: State) -> dict:
        return await build_candidates_async(state, llm, aw_records, aw_path, top_n, max_concurrency)

    graph.add_node("build_candidates", _build)
    graph.set_entry_point("build_candidates")
    graph.add_edge("build_candidates", END)
    return graph


def run_librarian(intent: dict, aw_path: str, llm: ChatOpenAI, top_n: int = 3) -> list[dict]:
    aw_records = load_aw_library(aw_path)
    print("[Librarian] 构建同步图", flush=True)
    graph = make_graph(llm, aw_records, aw_path, top_n)
    app = graph.compile()
    state: State = {"intent": intent, "candidates": [], "result": {}}
    print("[Librarian] 执行同步图", flush=True)
    output = app.invoke(state)
    return output.get("candidates", [])


async def run_librarian_async(
    intent: dict,
    aw_path: str,
    llm: ChatOpenAI,
    top_n: int = 3,
    max_concurrency: int = 4,
) -> list[dict]:
    aw_records = load_aw_library(aw_path)
    print("[Librarian] 构建异步图", flush=True)
    graph = make_graph_async(llm, aw_records, aw_path, top_n, max_concurrency)
    app = graph.compile()
    state: State = {"intent": intent, "candidates": [], "result": {}}
    print("[Librarian] 执行异步图", flush=True)
    output = await app.ainvoke(state)
    return output.get("candidates", [])
