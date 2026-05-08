"""LLM 客户端 - OpenAI 兼容 API，支持 SSE 流式、自动重试、Token 追踪"""

import json
import asyncio
import httpx
from typing import AsyncIterator, List, Dict, Any, Optional


class TokenUsage:
    """Token 用量统计"""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.requests = 0

    def add(self, usage: dict):
        """累加一次请求的 token 用量"""
        if not usage:
            return
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)
        self.requests += 1

    def summary(self) -> str:
        """返回用量摘要"""
        return (
            f"📊 Tokens: {self.total_tokens} "
            f"(prompt: {self.prompt_tokens}, completion: {self.completion_tokens}) "
            f"| 请求次数: {self.requests}"
        )

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "requests": self.requests,
        }


class LLMClient:
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(self, api_key: str, base_url: str, model: str,
                 max_tokens: int = 4096, temperature: float = 0.7,
                 max_retries: int = 3):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=120.0)
        self.usage = TokenUsage()

    async def _request_with_retry(self, payload: dict, headers: dict, stream: bool = False):
        """带自动重试的请求"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                if stream:
                    return self._client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                else:
                    resp = await self._client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503, 504):
                    # 可重试的错误
                    wait = (2 ** attempt) * 1.0  # 指数退避: 1s, 2s, 4s
                    await asyncio.sleep(wait)
                    continue
                else:
                    raise  # 不可重试的错误直接抛出
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                wait = (2 ** attempt) * 1.0
                await asyncio.sleep(wait)
                continue

        # 所有重试都失败
        raise last_error

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        """发送聊天请求（非流式）"""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = await self._request_with_retry(payload, headers)
        data = resp.json()

        # 追踪 token 用量
        if "usage" in data:
            self.usage.add(data["usage"])

        return data

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """真正的 SSE 流式聊天，带自动重试

        Yields 事件字典:
          {"type": "token", "content": "..."}          — 文本 token
          {"type": "tool_call_start", "index": 0, "id": "...", "name": "..."}  — 工具调用开始
          {"type": "tool_call_delta", "index": 0, "arguments_delta": "..."}    — 工具参数增量
          {"type": "tool_call_done", "index": 0, "id": "...", "name": "...", "arguments": "..."} — 工具调用完成
          {"type": "done", "finish_reason": "stop|tool_calls"}  — 流结束
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 用于累积 tool_call 片段
        tool_calls_acc = {}  # index -> {id, name, arguments_chunks}
        stream_usage = None

        # 带重试的流式请求
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with self._client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    resp.raise_for_status()
                    finish_reason = None

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason") or finish_reason

                        # 追踪流式 token 用量（部分 API 支持）
                        if chunk.get("usage"):
                            stream_usage = chunk["usage"]

                        # 文本内容
                        if delta.get("content"):
                            yield {"type": "token", "content": delta["content"]}

                        # 工具调用
                        if delta.get("tool_calls"):
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)

                                if idx not in tool_calls_acc:
                                    tool_calls_acc[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "name": "",
                                        "arguments": "",
                                    }
                                    yield {
                                        "type": "tool_call_start",
                                        "index": idx,
                                        "id": tc_delta.get("id", ""),
                                        "name": tc_delta.get("function", {}).get("name", ""),
                                    }

                                acc = tool_calls_acc[idx]

                                if tc_delta.get("function", {}).get("name"):
                                    acc["name"] = tc_delta["function"]["name"]
                                if tc_delta.get("id"):
                                    acc["id"] = tc_delta["id"]

                                arg_delta = tc_delta.get("function", {}).get("arguments", "")
                                if arg_delta:
                                    acc["arguments"] += arg_delta
                                    yield {
                                        "type": "tool_call_delta",
                                        "index": idx,
                                        "arguments_delta": arg_delta,
                                    }

                    # 流结束，发出完成事件
                    for idx in sorted(tool_calls_acc.keys()):
                        acc = tool_calls_acc[idx]
                        yield {
                            "type": "tool_call_done",
                            "index": idx,
                            "id": acc["id"],
                            "name": acc["name"],
                            "arguments": acc["arguments"],
                        }

                    # 追踪 token 用量
                    if stream_usage:
                        self.usage.add(stream_usage)

                    yield {"type": "done", "finish_reason": finish_reason or "stop"}
                    return  # 成功，退出重试循环

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    wait = (2 ** attempt) * 1.0
                    yield {"type": "token", "content": f"\n⚠️ API 错误 ({e.response.status_code})，{wait}s 后重试...\n"}
                    await asyncio.sleep(wait)
                    tool_calls_acc.clear()  # 重置工具调用状态
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = (2 ** attempt) * 1.0
                    yield {"type": "token", "content": f"\n⚠️ 连接失败，{wait}s 后重试...\n"}
                    await asyncio.sleep(wait)
                    tool_calls_acc.clear()
                    continue
                raise

        raise last_error

    async def close(self):
        await self._client.aclose()
