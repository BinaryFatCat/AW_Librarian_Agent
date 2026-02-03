from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx
from langchain_openai import ChatOpenAI

from librarian_agent.librarian import run_librarian, run_librarian_async


def _prompt(text: str, default: str | None = None) -> str:
    tip = f" [{default}]" if default else ""
    value = input(f"{text}{tip}: ").strip()
    return value or (default or "")


def main() -> None:
    print("=== The Librarian (LangGraph) ===")
    api_base = _prompt(
        "请输入 LLM API Base",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    api_key = _prompt("请输入 LLM API Key")
    model = _prompt("请输入 LLM Model", "deepseek-r1")
    disable_proxy = _prompt("是否禁用系统代理 (y/N)", "N").lower().startswith("y")

    aw_path = _prompt("请输入 AW 库路径（文件或目录）", str(Path(".").resolve()))
    intent_path = _prompt("请输入 intent JSON 路径")
    top_n_text = _prompt("请输入 Top-N", "3")
    output_path = _prompt("请输入输出 JSON 路径（可选）", "")
    use_async = _prompt("是否使用异步 LLM (y/N)", "N").lower().startswith("y")
    max_concurrency_text = _prompt("请输入并发限制（异步模式）", "4")

    try:
        top_n = int(top_n_text)
    except ValueError:
        top_n = 3

    try:
        max_concurrency = int(max_concurrency_text)
    except ValueError:
        max_concurrency = 4

    intent = json.loads(Path(intent_path).read_text(encoding="utf-8"))

    http_client = httpx.Client(proxies={}) if disable_proxy else None

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=api_base,
        temperature=0,
        http_client=http_client,
    )

    if use_async:
        results = asyncio.run(
            run_librarian_async(
                intent=intent,
                aw_path=aw_path,
                llm=llm,
                top_n=top_n,
                max_concurrency=max_concurrency,
            )
        )
    else:
        results = run_librarian(intent=intent, aw_path=aw_path, llm=llm, top_n=top_n)
    output_text = json.dumps(results, ensure_ascii=False, indent=2)
    if output_path:
        out_path = Path(output_path)
        if out_path.exists() and out_path.is_dir():
            out_path = out_path / "candidates.json"
        elif out_path.suffix.lower() != ".json":
            out_path = out_path.with_suffix(".json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        print(f"\n=== candidates 已写入: {out_path} ===")
    else:
        print("\n=== candidates 输出 ===")
        print(output_text)


if __name__ == "__main__":
    main()
