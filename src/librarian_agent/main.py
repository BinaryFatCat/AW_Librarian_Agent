"""
CLI 入口模块
提供命令行交互界面，支持同步和异步执行
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import List

from langchain_openai import ChatOpenAI

from .graph import create_librarian_graph
from .state import LibrarianState


def print_banner():
    """打印欢迎横幅"""
    print("\n" + "=" * 60)
    print("  📚 The Librarian Agent - 知识库专家")
    print("  基于 LangGraph 框架 | 支持 DeepSeek R1/V3")
    print("=" * 60)


def get_user_config():
    """交互式获取用户配置"""
    print("\n📋 请配置以下参数:\n")
    
    # API 配置
    api_key = input("🔑 API Key: ").strip()
    if not api_key:
        print("❌ API Key 不能为空!")
        sys.exit(1)
    
    base_url = input("🌐 Base URL (回车使用默认 https://dashscope.aliyuncs.com/compatible-mode/v1): ").strip()
    if not base_url:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    model_name = input("🤖 模型名称 (回车使用默认 deepseek-r1): ").strip()
    if not model_name:
        model_name = "deepseek-r1"
    
    # 路径配置
    print("\n📂 路径配置:")
    lib_path = input("   AW 库路径 (Markdown 文件所在目录): ").strip()
    if not lib_path or not os.path.isdir(lib_path):
        print(f"❌ AW 库路径无效: {lib_path}")
        sys.exit(1)
    
    input_json = input("   Parser 输出的 JSON 文件路径: ").strip()
    if not input_json or not os.path.isfile(input_json):
        print(f"❌ JSON 文件不存在: {input_json}")
        sys.exit(1)
    
    output_path = input("   输出文件路径 (回车使用默认 librarian_output.json): ").strip()
    if not output_path:
        output_path = "librarian_output.json"
    
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
        "library_path": os.path.abspath(lib_path),
        "input_json": input_json,
        "output_path": output_path,
    }


def load_parser_output(file_path: str) -> dict:
    """加载 Parser Agent 的输出 JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


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


def run_librarian(config: dict):
    """运行 Librarian Agent（同步模式）"""
    
    # 初始化 LLM
    print(f"\n🔧 正在初始化 LLM ({config['model_name']})...")
    model = ChatOpenAI(
        model=config["model_name"],
        openai_api_key=config["api_key"],
        openai_api_base=config["base_url"],
        temperature=0,
        max_tokens=4096,
    )
    
    # 创建 Graph（传入 library_path）
    print("🔧 正在构建 LangGraph 工作流...")
    app = create_librarian_graph(model, config["library_path"])
    
    # 加载输入数据
    print(f"📄 正在加载: {config['input_json']}")
    parser_data = load_parser_output(config["input_json"])
    all_steps = extract_all_steps(parser_data)
    
    print(f"\n📊 共发现 {len(all_steps)} 个步骤需要匹配 AW")
    print("-" * 50)
    
    # 处理每个步骤
    all_results = []
    
    for i, step in enumerate(all_steps, 1):
        step_id = step.get("step_id", f"S{i}")
        description = step.get("description", "未知描述")
        phase = step.get("phase", "unknown")
        
        print(f"\n🔍 [{i}/{len(all_steps)}] 正在处理步骤 {step_id} ({phase})")
        print(f"   📝 {description}")
        
        # 构建初始状态
        initial_state: LibrarianState = {
            "intent": parser_data,  # 完整的 Parser 输出
            "messages": [],
            "candidates": [],
            "result": {},
            "library_path": config["library_path"],
            "current_step": step,
            "debug": config.get("debug", False),  # 传递调试标志
        }
        
        try:
            # 运行 Agent（同步）
            final_state = app.invoke(initial_state)
            
            candidates = final_state.get("candidates", [])
            print(f"   ✅ 找到 {len(candidates)} 个候选 AW")
            
            for j, c in enumerate(candidates, 1):
                aw_id = c.get("aw_id", c.get("aw_name", "未知"))
                reason = c.get("reason", "")[:50]
                print(f"      {j}. {aw_id}")
                if reason:
                    print(f"         └─ {reason}...")
            
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": candidates,
            })
            
        except Exception as e:
            print(f"   ❌ 处理失败: {str(e)}")
            all_results.append({
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "error": str(e),
                "candidates": [],
            })
    
    return _save_results(config, parser_data, all_results)


async def run_librarian_async(config: dict):
    """
    运行 Librarian Agent（异步模式）
    使用 LangGraph 的 ainvoke 实现异步执行
    """
    
    # 初始化 LLM
    print(f"\n🔧 正在初始化 LLM ({config['model_name']})... [异步模式]")
    model = ChatOpenAI(
        model=config["model_name"],
        openai_api_key=config["api_key"],
        openai_api_base=config["base_url"],
        temperature=0,
        max_tokens=4096,
    )
    
    # 创建 Graph（传入 library_path）
    print("🔧 正在构建 LangGraph 工作流...")
    app = create_librarian_graph(model, config["library_path"])
    
    # 加载输入数据
    print(f"📄 正在加载: {config['input_json']}")
    parser_data = load_parser_output(config["input_json"])
    all_steps = extract_all_steps(parser_data)
    
    print(f"\n📊 共发现 {len(all_steps)} 个步骤需要匹配 AW")
    print("-" * 50)
    
    # 异步处理每个步骤
    all_results = []
    
    async def process_step(i: int, step: dict) -> dict:
        """异步处理单个步骤"""
        step_id = step.get("step_id", f"S{i}")
        description = step.get("description", "未知描述")
        phase = step.get("phase", "unknown")
        
        print(f"\n🔍 [{i}/{len(all_steps)}] 正在处理步骤 {step_id} ({phase})")
        print(f"   📝 {description}")
        
        # 构建初始状态
        initial_state: LibrarianState = {
            "intent": parser_data,
            "messages": [],
            "candidates": [],
            "result": {},
            "library_path": config["library_path"],
            "current_step": step,
            "debug": config.get("debug", False),  # 传递调试标志
        }
        
        try:
            # 使用 ainvoke 异步运行 Agent
            final_state = await app.ainvoke(initial_state)
            
            candidates = final_state.get("candidates", [])
            print(f"   ✅ 找到 {len(candidates)} 个候选 AW")
            
            for j, c in enumerate(candidates, 1):
                aw_id = c.get("aw_id", c.get("aw_name", "未知"))
                reason = c.get("reason", "")[:50]
                print(f"      {j}. {aw_id}")
                if reason:
                    print(f"         └─ {reason}...")
            
            return {
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "action_type": step.get("action_type", step.get("check_type", "")),
                "candidates": candidates,
            }
            
        except Exception as e:
            print(f"   ❌ 处理失败: {str(e)}")
            return {
                "step_id": step_id,
                "phase": phase,
                "description": description,
                "error": str(e),
                "candidates": [],
            }
    
    # 顺序异步执行（保持输出顺序）
    for i, step in enumerate(all_steps, 1):
        result = await process_step(i, step)
        all_results.append(result)
    
    return _save_results(config, parser_data, all_results)


def _save_results(config: dict, parser_data: dict, all_results: List[dict]) -> dict:
    """保存结果到文件"""
    output_payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "model": config["model_name"],
            "library_path": config["library_path"],
        },
        "scenario_metadata": parser_data.get("scenario_metadata", {}),
        "librarian_output": all_results,
    }
    
    # 保存结果
    with open(config["output_path"], 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"✅ 处理完成! 结果已保存至: {config['output_path']}")
    print("=" * 50)
    
    return output_payload


def main():
    """主入口函数（支持同步/异步模式选择）"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Librarian Agent - 知识库专家")
    parser.add_argument("--debug", action="store_true", help="启用调试模式，显示详细的 LLM 和工具调用信息")
    parser.add_argument("--intent", type=str, help="Parser 输出的 JSON 文件路径")
    parser.add_argument("--library", type=str, help="AW 库路径 (Markdown 文件所在目录)")
    parser.add_argument("--output", type=str, help="输出文件路径")
    parser.add_argument("--async", dest="use_async", action="store_true", help="使用异步模式")
    args = parser.parse_args()
    
    print_banner()
    
    try:
        # 如果提供了命令行参数，使用命令行模式
        if args.intent and args.library:
            if not os.path.isfile(args.intent):
                print(f"❌ JSON 文件不存在: {args.intent}")
                sys.exit(1)
            if not os.path.isdir(args.library):
                print(f"❌ AW 库路径无效: {args.library}")
                sys.exit(1)
            
            # 从环境变量获取 API 配置
            api_key = os.environ.get("OPENAI_API_KEY", os.environ.get("DASHSCOPE_API_KEY", ""))
            if not api_key:
                print("❌ 请设置环境变量 OPENAI_API_KEY 或 DASHSCOPE_API_KEY")
                sys.exit(1)
            
            config = {
                "api_key": api_key,
                "base_url": os.environ.get("OPENAI_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                "model_name": os.environ.get("MODEL_NAME", "deepseek-r1"),
                "library_path": os.path.abspath(args.library),
                "input_json": args.intent,
                "output_path": args.output or "librarian_output.json",
                "debug": args.debug,
            }
            
            print(f"📂 AW 库: {config['library_path']}")
            print(f"📄 Intent: {config['input_json']}")
            print(f"🤖 模型: {config['model_name']}")
        else:
            # 交互模式
            config = get_user_config()
            config["debug"] = args.debug
        
        if args.debug:
            print("\n🔍 [调试模式已启用] - 将显示详细的推理和工具调用过程")
        
        # 判断是否使用异步模式
        if args.intent and args.library:
            use_async = args.use_async
        else:
            use_async = input("\n🔄 是否使用异步模式? (y/N): ").strip().lower() == 'y'
        
        if use_async:
            print("📡 启用异步模式...")
            asyncio.run(run_librarian_async(config))
        else:
            print("📡 使用同步模式...")
            run_librarian(config)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 运行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
