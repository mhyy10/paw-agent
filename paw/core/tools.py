"""工具系统 - 装饰器定义 + 自动发现"""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional

# 全局工具注册表
_tool_registry: Dict[str, "ToolDef"] = {}


class ToolDef:
    """工具定义"""

    def __init__(self, name: str, description: str, parameters: dict, func: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def to_openai_schema(self) -> dict:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> str:
        """执行工具"""
        result = self.func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        return str(result)


def tool(name: str = "", description: str = "", parameters: dict = None):
    """装饰器：将函数注册为工具

    用法:
        @tool(name="read_file", description="读取文件内容")
        def read_file(path: str) -> str:
            ...
    """

    def decorator(func: Callable):
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip().split("\n")[0]

        # 自动从函数签名推断参数
        if parameters is None:
            tool_params = _infer_parameters(func)
        else:
            tool_params = parameters

        tool_def = ToolDef(tool_name, tool_desc, tool_params, func)
        _tool_registry[tool_name] = tool_def
        return func

    return decorator


def get_all_tools() -> List[ToolDef]:
    """获取所有已注册的工具"""
    return list(_tool_registry.values())


def get_tool(name: str) -> Optional[ToolDef]:
    """按名称获取工具"""
    return _tool_registry.get(name)


def get_tools_schema() -> List[dict]:
    """获取所有工具的 OpenAI schema"""
    return [t.to_openai_schema() for t in _tool_registry.values()]


def _infer_parameters(func: Callable) -> dict:
    """从函数签名自动推断 JSON Schema 参数"""
    sig = inspect.signature(func)
    props = {}
    required = []

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        prop = {}
        # 推断类型
        if param.annotation != inspect.Parameter.empty:
            prop["type"] = type_map.get(param.annotation, "string")
        else:
            prop["type"] = "string"

        # 从参数名生成描述
        prop["description"] = name.replace("_", " ")

        props[name] = prop

        # 必填参数（没有默认值的）
        if param.default == inspect.Parameter.empty:
            required.append(name)

    schema = {
        "type": "object",
        "properties": props,
    }
    if required:
        schema["required"] = required

    return schema
