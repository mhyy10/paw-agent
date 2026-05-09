"""Agent 核心 - 真流式 + 多轮工具调用 + Token 追踪"""

import json
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from paw.config import load_config
from paw.core.llm import LLMClient
from paw.core.memory import Memory
from paw.core.tools import get_all_tools, get_tools_schema, get_tool


class Agent:
    """Paw 智能体核心"""

    def __init__(self, config: dict = None, session_id: str = None):
        self.config = config or load_config()
        self.session_id = session_id or str(uuid.uuid4())[:8]

        # 初始化 LLM（带重试）
        llm_cfg = self.config["llm"]
        agent_cfg = self.config.get("agent", {})
        self.llm = LLMClient(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg["base_url"],
            model=llm_cfg["model"],
            max_tokens=llm_cfg.get("max_tokens", 4096),
            temperature=llm_cfg.get("temperature", 0.7),
            max_retries=agent_cfg.get("max_retries", 3),
        )

        # 初始化记忆
        from paw.config import DB_FILE
        self.memory = Memory(str(DB_FILE))

        # 系统提示词
        self.system_prompt = agent_cfg.get("system_prompt", "")
        self.max_tool_rounds = agent_cfg.get("max_tool_rounds", 10)

    def _build_messages(self, user_input: str) -> List[Dict]:
        """构建完整的消息列表"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        history = self.memory.get_messages(self.session_id, limit=30)
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})
        return messages

    async def chat(self, user_input: str, on_tool_call: Callable = None) -> str:
        """处理用户输入，返回回复（非流式）"""
        self.memory.add_message(self.session_id, "user", user_input)

        tools_schema = get_tools_schema()
        messages = self._build_messages(user_input)

        for round_num in range(self.max_tool_rounds):
            response = await self.llm.chat(messages, tools=tools_schema or None)
            choice = response["choices"][0]
            message = choice["message"]

            if not message.get("tool_calls"):
                assistant_content = message.get("content", "")
                self.memory.add_message(self.session_id, "assistant", assistant_content)
                return assistant_content

            # 有工具调用
            self.memory.add_message(
                self.session_id, "assistant",
                message.get("content"),
                tool_calls=message["tool_calls"],
            )
            messages.append(message)

            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = tool_call["function"].get("arguments", "{}")
                call_id = tool_call["id"]

                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except json.JSONDecodeError:
                        func_args = {}

                if on_tool_call:
                    on_tool_call(func_name, func_args)

                tool_def = get_tool(func_name)
                if tool_def:
                    try:
                        result = await tool_def.execute(**func_args)
                    except Exception as e:
                        result = f"工具执行出错: {e}"
                else:
                    result = f"未知工具: {func_name}"

                self.memory.add_message(
                    self.session_id, "tool", result,
                    tool_call_id=call_id, tool_name=func_name,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                })

        return "达到工具调用上限，请简化你的请求。"

    async def chat_stream(
        self,
        user_input: str,
        on_tool_call: Callable = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """真正的流式聊天

        Yields 事件字典:
          {"type": "token", "content": "..."}           — 文本 token
          {"type": "tool_start", "name": "...", "args": {...}}  — 工具开始执行
          {"type": "tool_result", "name": "...", "result": "..."} — 工具执行结果
          {"type": "tool_error", "name": "...", "error": "..."}  — 工具执行错误
          {"type": "round", "number": N}                — 当前工具轮次
          {"type": "done"}                              — 全部完成
        """
        self.memory.add_message(self.session_id, "user", user_input)

        tools_schema = get_tools_schema()
        messages = self._build_messages(user_input)

        for round_num in range(self.max_tool_rounds):
            content_buf = ""
            tool_calls_done = []

            async for event in self.llm.chat_stream(messages, tools=tools_schema or None):
                if event["type"] == "token":
                    content_buf += event["content"]
                    yield {"type": "token", "content": event["content"]}

                elif event["type"] == "tool_call_done":
                    tool_calls_done.append(event)

                elif event["type"] == "done":
                    finish_reason = event.get("finish_reason", "stop")
                    if finish_reason == "stop" and not tool_calls_done:
                        self.memory.add_message(self.session_id, "assistant", content_buf)
                        yield {"type": "done"}
                        return

            if not tool_calls_done:
                if content_buf:
                    self.memory.add_message(self.session_id, "assistant", content_buf)
                yield {"type": "done"}
                return

            # 有工具调用 — 保存 assistant 消息
            tool_calls_for_memory = []
            for tc in tool_calls_done:
                tool_calls_for_memory.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })

            self.memory.add_message(
                self.session_id, "assistant",
                content_buf if content_buf else None,
                tool_calls=tool_calls_for_memory,
            )

            assistant_msg = {"role": "assistant", "content": content_buf or None}
            if tool_calls_for_memory:
                assistant_msg["tool_calls"] = tool_calls_for_memory
            messages.append(assistant_msg)

            if round_num > 0:
                yield {"type": "round", "number": round_num + 1}

            for tc in tool_calls_done:
                func_name = tc["name"]
                func_args_str = tc["arguments"]
                call_id = tc["id"]

                try:
                    func_args = json.loads(func_args_str) if func_args_str else {}
                except json.JSONDecodeError:
                    func_args = {}

                yield {"type": "tool_start", "name": func_name, "args": func_args}

                if on_tool_call:
                    on_tool_call(func_name, func_args)

                tool_def = get_tool(func_name)
                if tool_def:
                    try:
                        result = await tool_def.execute(**func_args)
                    except Exception as e:
                        result = f"工具执行出错: {e}"
                        yield {"type": "tool_error", "name": func_name, "error": str(e)}
                else:
                    result = f"未知工具: {func_name}"
                    yield {"type": "tool_error", "name": func_name, "error": result}

                if len(result) > 5000:
                    result = result[:5000] + "\n...(结果已截断)"

                yield {"type": "tool_result", "name": func_name, "result": result}

                self.memory.add_message(
                    self.session_id, "tool", result,
                    tool_call_id=call_id, tool_name=func_name,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                })

        yield {"type": "token", "content": "\n[!] 达到工具调用上限，请简化你的请求。"}
        yield {"type": "done"}

    def get_token_usage(self) -> dict:
        """获取当前 token 用量"""
        return self.llm.usage.to_dict()

    def get_token_summary(self) -> str:
        """获取 token 用量摘要"""
        return self.llm.usage.summary()

    async def close(self):
        await self.llm.close()

