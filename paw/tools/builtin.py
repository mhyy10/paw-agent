"""内置工具集 - 文件读写、终端、搜索、网页抓取、Python 执行"""

import os
import subprocess
import sys
import io
import traceback
from pathlib import Path
from paw.core.tools import tool


@tool(
    name="read_file",
    description="读取文件内容。参数：path 文件路径，offset 起始行号（默认1），limit 最大行数（默认200）"
)
def read_file(path: str, offset: int = 1, limit: int = 200) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"文件不存在: {path}"}
    if not p.is_file():
        return {"error": f"不是文件: {path}"}
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        selected = lines[offset-1 : offset-1+limit]
        content = "".join(selected)
        return {"content": content, "total_lines": total, "showing": f"{offset}-{min(offset+limit-1, total)}"}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="write_file",
    description="写入文件（覆盖）。参数：path 文件路径，content 文件内容"
)
def write_file(path: str, content: str) -> dict:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": str(p), "bytes": len(content.encode())}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="run_command",
    description="执行 shell 命令并返回输出。参数：command 命令字符串，timeout 超时秒数（默认30）"
)
def run_command(command: str, timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        return {
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"命令超时 ({timeout}s)"}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="list_dir",
    description="列出目录内容。参数：path 目录路径（默认当前目录）"
)
def list_dir(path: str = ".") -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"目录不存在: {path}"}
    if not p.is_dir():
        return {"error": f"不是目录: {path}"}

    items = []
    try:
        for item in sorted(p.iterdir()):
            prefix = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                s = item.stat().st_size
                if s < 1024:
                    size = f" ({s}B)"
                elif s < 1024 * 1024:
                    size = f" ({s/1024:.1f}KB)"
                else:
                    size = f" ({s/1024/1024:.1f}MB)"
            items.append(f"{prefix} {item.name}{size}")
        return {"path": str(p), "items": items[:100], "total": len(items)}
    except PermissionError:
        return {"error": f"没有权限访问: {path}"}


@tool(
    name="search_files",
    description="在文件中搜索文本。参数：pattern 搜索关键词，path 目录路径（默认当前目录），file_glob 文件名过滤（如 '*.py'）"
)
def search_files(pattern: str, path: str = ".", file_glob: str = "*") -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"目录不存在: {path}"}

    matches = []
    try:
        for f in p.rglob(file_glob):
            if not f.is_file() or f.stat().st_size > 1_000_000:
                continue
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if pattern.lower() in line.lower():
                            matches.append({
                                "file": str(f),
                                "line": i,
                                "text": line.strip()[:200],
                            })
                            if len(matches) >= 50:
                                return {"matches": matches, "truncated": True}
            except (PermissionError, UnicodeDecodeError):
                continue
        return {"matches": matches, "truncated": False}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="edit_file",
    description="编辑文件：查找并替换文本。参数：path 文件路径，old_text 要替换的文本，new_text 新文本"
)
def edit_file(path: str, old_text: str, new_text: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"文件不存在: {path}"}
    try:
        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            return {"error": "未找到要替换的文本"}
        new_content = content.replace(old_text, new_text, 1)
        p.write_text(new_content, encoding="utf-8")
        return {"success": True, "path": str(p)}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="web_fetch",
    description="抓取网页内容。参数：url 网址，max_length 最大返回字符数（默认5000）"
)
def web_fetch(url: str, max_length: int = 5000) -> dict:
    """抓取网页并提取文本内容"""
    try:
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        text = resp.text

        # 简单 HTML 文本提取
        if "html" in content_type:
            import re
            # 移除 script/style
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
            # 移除 HTML 标签
            text = re.sub(r"<[^>]+>", "", text)
            # 清理空白
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = text.strip()

        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容已截断)"

        return {
            "url": str(resp.url),
            "status": resp.status_code,
            "content_type": content_type,
            "content": text,
            "length": len(text),
        }
    except httpx.TimeoutException:
        return {"error": f"请求超时: {url}"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {url}"}
    except Exception as e:
        return {"error": f"抓取失败: {e}"}


@tool(
    name="python_repl",
    description="执行 Python 代码并返回输出。参数：code Python 代码字符串，timeout 超时秒数（默认30）"
)
def python_repl(code: str, timeout: int = 30) -> dict:
    """在隔离的命名空间中执行 Python 代码"""
    # 捕获 stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # 预导入常用模块
    namespace = {
        "__builtins__": __builtins__,
        "os": os,
        "sys": sys,
        "Path": Path,
    }

    try:
        import math, json, re, datetime, collections, itertools
        namespace.update({
            "math": math, "json": json, "re": re,
            "datetime": datetime, "collections": collections,
            "itertools": itertools,
        })
    except ImportError:
        pass

    sys.stdout = stdout_capture
    sys.stderr = stderr_capture

    try:
        # 先尝试 eval（表达式）
        try:
            result = eval(code, namespace)
            if result is not None:
                print(repr(result))
        except SyntaxError:
            # 不是表达式，用 exec
            exec(code, namespace)

        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        return {
            "stdout": stdout_val[:5000] if stdout_val else "(无输出)",
            "stderr": stderr_val[:2000] if stderr_val else "",
            "success": True,
        }
    except Exception:
        stderr_val = stderr_capture.getvalue()
        tb = traceback.format_exc()
        return {
            "stdout": stdout_capture.getvalue()[:2000],
            "stderr": (stderr_val + "\n" + tb)[:5000],
            "success": False,
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
