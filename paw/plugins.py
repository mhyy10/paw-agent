"""插件系统 - 从 ~/.paw/plugins/ 自动加载自定义工具"""

import importlib.util
import sys
from pathlib import Path
from typing import List

from paw.core.tools import tool, get_all_tools, _tool_registry

PLUGINS_DIR = Path.home() / ".paw" / "plugins"


def discover_plugins() -> List[Path]:
    """发现所有插件文件"""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(PLUGINS_DIR.glob("*.py"))


def load_plugins() -> dict:
    """加载所有插件，返回 {filename: {tools: [...], errors: [...]}}"""
    results = {}
    plugin_files = discover_plugins()

    for plugin_path in plugin_files:
        plugin_name = plugin_path.stem
        result = {"tools": [], "errors": [], "path": str(plugin_path)}

        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"paw_plugin_{plugin_name}", str(plugin_path)
            )
            if spec is None or spec.loader is None:
                result["errors"].append(f"无法加载模块 spec")
                results[plugin_name] = result
                continue

            module = importlib.util.module_from_spec(spec)

            # 注入常用模块到插件命名空间
            module.__builtins__ = __builtins__
            spec.loader.exec_module(module)

            # 记录加载前的工具数量
            before = set(_tool_registry.keys())
            after = set(_tool_registry.keys())
            new_tools = after - before

            # 如果插件没有使用 @tool 装饰器，尝试扫描函数
            if not new_tools:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and not attr_name.startswith("_"):
                        # 检查是否有 _paw_tool 标记
                        if hasattr(attr, "_paw_tool"):
                            new_tools.add(attr_name)

            result["tools"] = list(new_tools)
            results[plugin_name] = result

        except Exception as e:
            result["errors"].append(str(e))
            results[plugin_name] = result

    return results


def get_plugin_template() -> str:
    """返回插件模板代码"""
    return '''"""Paw 自定义工具插件

将此文件放入 ~/.paw/plugins/ 目录即可自动加载。

使用 @tool 装饰器定义工具，工具会自动注册到 Paw。
"""

import os
from paw.core.tools import tool


@tool(
    name="my_custom_tool",
    description="这是一个自定义工具示例。描述工具的功能。",
    parameters={
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "输入参数说明",
            }
        },
        "required": ["input"],
    },
)
def my_custom_tool(input: str) -> dict:
    """自定义工具的实现"""
    # 在这里写你的逻辑
    result = f"处理了: {input}"
    return {"result": result}


# 你可以定义多个工具，每个都用 @tool 装饰器
# @tool(name="another_tool", description="另一个工具")
# def another_tool(param: str) -> str:
#     return "..."
'''


def create_plugin_scaffold(name: str) -> Path:
    """创建插件脚手架文件"""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    plugin_path = PLUGINS_DIR / f"{name}.py"
    if plugin_path.exists():
        raise FileExistsError(f"插件已存在: {plugin_path}")
    plugin_path.write_text(get_plugin_template(), encoding="utf-8")
    return plugin_path
