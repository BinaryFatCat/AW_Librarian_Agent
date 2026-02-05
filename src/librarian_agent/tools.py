"""
工具集模块
提供多种搜索工具供 LLM 选择使用

注意：工具使用工厂模式创建，library_path 在创建时绑定。
"""

import os
import re
import subprocess
from typing import Optional, List
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


# ============================================================================
# 工具参数 Schema
# ============================================================================

class RgSearchInput(BaseModel):
    """ripgrep 搜索参数"""
    keywords: str = Field(
        description="要搜索的关键词，多个关键词用逗号分隔（如 'project,create,项目'）"
    )


class GrepSearchInput(BaseModel):
    """grep 模式搜索参数"""
    pattern: str = Field(
        description="搜索模式（支持简单正则）"
    )
    file_pattern: str = Field(
        default="*.md",
        description="文件匹配模式，默认 *.md"
    )


class FindFilesInput(BaseModel):
    """文件列表参数"""
    name_contains: Optional[str] = Field(
        default=None,
        description="可选，过滤文件名包含的字符串"
    )


class ReadFileInput(BaseModel):
    """读取文件参数"""
    file_path: str = Field(
        description="AW 文件路径（可以是相对于库根目录的路径，如 'aw_createProject.md'）"
    )


class ExtractMetadataInput(BaseModel):
    """提取元数据参数"""
    file_path: str = Field(
        description="AW 文件路径（可以是相对于库根目录的路径）"
    )


# ============================================================================
# 工具实现函数
# ============================================================================

def _rg_search(keywords: str, library_path: str) -> str:
    """使用 ripgrep (rg) 在 AW 库中搜索关键词"""
    try:
        # 支持多关键词搜索（用 | 分隔）
        search_pattern = keywords.replace(',', '|').replace('，', '|')
        
        cmd = [
            "rg", "-i", 
            "--max-columns", "200",
            "--max-count", "5",
            "-n",
            "-e", search_pattern,
            library_path
        ]
        output = subprocess.check_output(
            cmd, 
            text=True, 
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace'
        )
        lines = output.strip().split('\n')[:25]
        return f"=== rg 搜索结果 [{keywords}] ===\n" + '\n'.join(lines)
    except subprocess.CalledProcessError:
        return f"未找到包含关键词 '{keywords}' 的内容。请尝试其他关键词（如同义词、英文/中文）。"
    except FileNotFoundError:
        return _fallback_findstr(keywords, library_path)


def _fallback_findstr(keywords: str, library_path: str) -> str:
    """当 rg 不可用时，使用 findstr 作为回退"""
    try:
        keyword = keywords.split(',')[0].split('|')[0].strip()
        cmd = f'findstr /S /I /N "{keyword}" "{library_path}\\*.md"'
        output = subprocess.check_output(
            cmd, 
            shell=True, 
            text=True, 
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace'
        )
        lines = output.strip().split('\n')[:20]
        return f"=== findstr 搜索结果 [{keyword}] ===\n" + '\n'.join(lines)
    except subprocess.CalledProcessError:
        return f"未找到包含关键词 '{keywords}' 的内容。"


def _grep_search(pattern: str, library_path: str, file_pattern: str = "*.md") -> str:
    """使用 grep/PowerShell 进行模式匹配搜索"""
    try:
        cmd = f'Get-ChildItem -Path "{library_path}" -Filter "{file_pattern}" -Recurse | Select-String -Pattern "{pattern}" -CaseSensitive:$false | Select-Object -First 15'
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, 
            text=True, 
            timeout=30,
            encoding='utf-8',
            errors='replace'
        )
        if result.stdout.strip():
            return f"=== grep 模式搜索 [{pattern}] ===\n{result.stdout.strip()}"
        return f"未找到匹配模式 '{pattern}' 的内容。"
    except Exception as e:
        return f"搜索出错: {str(e)}"


def _find_files(library_path: str, name_contains: Optional[str] = None) -> str:
    """列出 AW 库中的所有 Markdown 文件"""
    try:
        files = []
        for root, _, filenames in os.walk(library_path):
            for fname in filenames:
                if fname.endswith('.md'):
                    if name_contains is None or name_contains.lower() in fname.lower():
                        rel_path = os.path.relpath(os.path.join(root, fname), library_path)
                        files.append(rel_path)
        
        if not files:
            return f"未找到{'包含 ' + name_contains + ' 的' if name_contains else ''} AW 文件。"
        
        result = f"=== AW 库文件列表 ===\n共 {len(files)} 个文件:\n"
        for f in sorted(files)[:30]:
            result += f"  - {f}\n"
        if len(files) > 30:
            result += f"  ... 还有 {len(files) - 30} 个文件\n"
        return result
    except Exception as e:
        return f"列出文件失败: {str(e)}"


def _read_file(file_path: str, library_path: str) -> str:
    """读取 AW 文件内容"""
    try:
        # 尝试多种路径组合
        candidates = [
            file_path,
            os.path.join(library_path, file_path),
            os.path.join(library_path, os.path.basename(file_path)),
        ]
        
        target_path = None
        for p in candidates:
            if os.path.exists(p):
                target_path = p
                break
        
        if not target_path:
            # 尝试模糊匹配
            basename = os.path.basename(file_path).replace('.md', '')
            for root, _, filenames in os.walk(library_path):
                for fname in filenames:
                    if basename.lower() in fname.lower():
                        target_path = os.path.join(root, fname)
                        break
                if target_path:
                    break
        
        if not target_path:
            return f"文件不存在: {file_path}。请使用 find_aw_files 查看可用文件列表。"
        
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"=== 文件内容: {os.path.basename(target_path)} ===\n{content}"
    except Exception as e:
        return f"读取文件失败: {str(e)}"


def _extract_metadata(file_path: str, library_path: str) -> str:
    """从 AW 文件中提取结构化元数据"""
    try:
        # 解析文件路径
        candidates = [
            file_path,
            os.path.join(library_path, file_path),
            os.path.join(library_path, os.path.basename(file_path)),
        ]
        
        target_path = None
        for p in candidates:
            if os.path.exists(p):
                target_path = p
                break
        
        if not target_path:
            return f"文件不存在: {file_path}"
        
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = {'file': os.path.basename(target_path)}
        
        # 提取 YAML frontmatter
        yaml_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
            for line in yaml_content.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
        
        # 提取关键词
        kw_match = re.search(r'关键词:\s*(.+)', content)
        if kw_match:
            metadata['keywords'] = kw_match.group(1).strip()
            
        # 提取场景标签
        tag_match = re.search(r'场景标签:\s*(.+)', content)
        if tag_match:
            metadata['tags'] = tag_match.group(1).strip()
            
        # 提取参数表
        param_section = re.search(r'\| 参数名.*?\n\|.*?\n((?:\|.*\n)*)', content)
        if param_section:
            params = []
            for line in param_section.group(1).strip().split('\n'):
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) >= 3:
                    params.append({
                        'name': cells[0].replace('`', ''),
                        'type': cells[1],
                        'required': cells[2]
                    })
            if params:
                metadata['parameters'] = params
        
        result = f"=== AW 元数据: {metadata.get('file', 'unknown')} ===\n"
        for k, v in metadata.items():
            if k == 'parameters':
                result += f"  parameters:\n"
                for p in v:
                    result += f"    - {p['name']} ({p['type']}, {p['required']})\n"
            else:
                result += f"  {k}: {v}\n"
        return result
        
    except Exception as e:
        return f"提取元数据失败: {str(e)}"


# ============================================================================
# 工具工厂函数
# ============================================================================

def create_tools(library_path: str) -> List:
    """
    创建绑定了 library_path 的工具集。
    
    这样 LLM 调用工具时不需要手动指定 library_path。
    
    Args:
        library_path: AW 库的根目录路径
        
    Returns:
        工具列表
    """
    
    # 使用闭包绑定 library_path
    def rg_search_keywords(keywords: str) -> str:
        """
        使用 ripgrep 在 AW 库中搜索关键词。
        快速定位包含特定关键词的 AW 文件。
        
        Args:
            keywords: 要搜索的关键词，多个关键词用逗号分隔（如 'project,create,项目'）
        """
        return _rg_search(keywords, library_path)
    
    def grep_search_pattern(pattern: str, file_pattern: str = "*.md") -> str:
        """
        使用模式匹配搜索 AW 库。
        适用于搜索 YAML frontmatter 中的特定字段。
        
        Args:
            pattern: 搜索模式（支持简单正则）
            file_pattern: 文件匹配模式，默认 *.md
        """
        return _grep_search(pattern, library_path, file_pattern)
    
    def find_aw_files(name_contains: Optional[str] = None) -> str:
        """
        列出 AW 库中的所有 Markdown 文件。
        了解 AW 库的整体结构和可用的 AW 列表。首次调用时推荐使用。
        
        Args:
            name_contains: 可选，过滤文件名包含的字符串（如 'project'）
        """
        return _find_files(library_path, name_contains)
    
    def cat_read_file(file_path: str) -> str:
        """
        读取 AW Markdown 文件的完整内容。
        验证 AW 的参数类型和功能描述是否匹配测试步骤。
        
        Args:
            file_path: AW 文件路径（如 'aw_createProject.md'）
        """
        return _read_file(file_path, library_path)
    
    def extract_aw_metadata(file_path: str) -> str:
        """
        从 AW 文件中提取结构化元数据。
        快速获取 AW 的 id、name、关键词、参数等关键信息。
        
        Args:
            file_path: AW 文件路径
        """
        return _extract_metadata(file_path, library_path)
    
    # 使用 StructuredTool 创建工具
    tools = [
        StructuredTool.from_function(
            func=rg_search_keywords,
            name="rg_search_keywords",
            description="使用 ripgrep 在 AW 库中搜索关键词。快速定位包含特定关键词的 AW 文件。支持多关键词（逗号分隔）。",
            args_schema=RgSearchInput,
        ),
        StructuredTool.from_function(
            func=grep_search_pattern,
            name="grep_search_pattern",
            description="使用模式匹配搜索 AW 库。适用于搜索 YAML frontmatter 中的特定字段。",
            args_schema=GrepSearchInput,
        ),
        StructuredTool.from_function(
            func=find_aw_files,
            name="find_aw_files",
            description="列出 AW 库中的所有 Markdown 文件。了解 AW 库的整体结构。首次调用时推荐使用。",
            args_schema=FindFilesInput,
        ),
        StructuredTool.from_function(
            func=cat_read_file,
            name="cat_read_file",
            description="读取 AW Markdown 文件的完整内容。验证 AW 的参数和功能是否匹配。",
            args_schema=ReadFileInput,
        ),
        StructuredTool.from_function(
            func=extract_aw_metadata,
            name="extract_aw_metadata",
            description="从 AW 文件中提取结构化元数据（id, name, keywords, parameters）。",
            args_schema=ExtractMetadataInput,
        ),
    ]
    
    return tools


# 向后兼容：默认工具列表（不推荐使用）
# 注意：新代码应使用 create_tools(library_path) 工厂函数
ALL_TOOLS = []  # 空列表，强制使用 create_tools()
