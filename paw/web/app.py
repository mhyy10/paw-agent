"""Web UI v3 - FastAPI + WebSocket + REST API"""

import json
import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from jinja2 import Environment, FileSystemLoader

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"


class ChatRequest(BaseModel):
    """REST API 聊天请求"""
    message: str
    session_id: Optional[str] = None
    persona: Optional[str] = None
    model: Optional[str] = None


class SessionMetaRequest(BaseModel):
    """会话元数据更新请求"""
    title: Optional[str] = None
    persona: Optional[str] = None


def create_app(config: dict = None) -> FastAPI:
    """创建 FastAPI 应用"""
    if config is None:
        from paw.config import load_config
        config = load_config()

    # 加载内置工具
    import paw.tools.builtin

    # 加载插件
    if config.get("tools", {}).get("plugins_enabled", True):
        try:
            from paw.plugins import load_plugins
            load_plugins()
        except Exception:
            pass

    app = FastAPI(title="Paw Agent", version="0.3.0", docs_url="/docs")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    template_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    # ========== 页面路由 ==========

    @app.get("/", response_class=HTMLResponse)
    async def index():
        template = template_env.get_template("index.html")
        return template.render(
            agent_name=config.get("agent", {}).get("name", "Paw"),
            model=config.get("llm", {}).get("model", "unknown"),
        )

    # ========== WebSocket ==========

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        session_id = str(uuid.uuid4())[:8]

        from paw.core.agent import Agent
        agent = Agent(config=config, session_id=session_id)

        try:
            await ws.send_json({
                "type": "system",
                "content": f"🐾 {config.get('agent', {}).get('name', 'Paw')} 已连接 · 会话 {session_id}",
            })

            while True:
                data = await ws.receive_text()
                msg = json.loads(data)

                if msg.get("type") == "chat":
                    user_input = msg.get("content", "").strip()
                    if not user_input:
                        continue

                    # 处理命令
                    if user_input.startswith("/"):
                        cmd_result = _handle_command(user_input, agent, session_id, config)
                        await ws.send_json({"type": "command_result", "content": cmd_result})
                        continue

                    # 调用 Agent
                    try:
                        async for event in agent.chat_stream(user_input):
                            etype = event["type"]

                            if etype == "token":
                                await ws.send_json({
                                    "type": "stream",
                                    "content": event["content"],
                                })

                            elif etype == "tool_start":
                                await ws.send_json({
                                    "type": "tool_start",
                                    "name": event["name"],
                                    "args": event.get("args", {}),
                                })

                            elif etype == "tool_result":
                                await ws.send_json({
                                    "type": "tool_result",
                                    "name": event["name"],
                                    "result": event["result"],
                                })

                            elif etype == "tool_error":
                                await ws.send_json({
                                    "type": "tool_error",
                                    "name": event["name"],
                                    "error": event["error"],
                                })

                            elif etype == "round":
                                await ws.send_json({
                                    "type": "round",
                                    "number": event["number"],
                                })

                            elif etype == "done":
                                pass

                        # 发送 token 用量
                        usage = agent.get_token_usage()
                        await ws.send_json({
                            "type": "token_usage",
                            "usage": usage,
                        })

                        await ws.send_json({"type": "stream_end"})

                    except Exception as e:
                        await ws.send_json({
                            "type": "error",
                            "content": f"出错了: {e}",
                        })

                elif msg.get("type") == "switch_session":
                    new_sid = msg.get("session_id", "")
                    sessions = agent.memory.get_sessions()
                    valid_ids = [s["session_id"] for s in sessions]
                    if new_sid in valid_ids:
                        session_id = new_sid
                        agent.session_id = new_sid
                        await ws.send_json({
                            "type": "system",
                            "content": f"✅ 已切换到会话 {new_sid}",
                        })
                    else:
                        await ws.send_json({
                            "type": "error",
                            "content": f"会话 {new_sid} 不存在",
                        })

                elif msg.get("type") == "new_session":
                    old_sid = session_id
                    session_id = str(uuid.uuid4())[:8]
                    agent.session_id = session_id
                    await ws.send_json({
                        "type": "system",
                        "content": f"✅ 新会话: {session_id}",
                        "session_id": session_id,
                    })

        except WebSocketDisconnect:
            pass
        finally:
            await agent.close()

    # ========== REST API ==========

    @app.get("/api/sessions")
    async def list_sessions():
        """列出所有会话"""
        from paw.core.memory import Memory
        from paw.config import DB_FILE
        memory = Memory(str(DB_FILE))
        sessions = memory.get_sessions(limit=50)
        return JSONResponse(content=sessions)

    @app.get("/api/sessions/{session_id}/messages")
    async def get_session_messages(session_id: str, limit: int = 100):
        """获取会话消息"""
        from paw.core.memory import Memory
        from paw.config import DB_FILE
        memory = Memory(str(DB_FILE))
        messages = memory.get_messages(session_id, limit=limit)
        return JSONResponse(content=messages)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str):
        """删除会话"""
        from paw.core.memory import Memory
        from paw.config import DB_FILE
        memory = Memory(str(DB_FILE))
        memory.delete_session(session_id)
        return {"status": "ok", "deleted": session_id}

    @app.post("/api/chat")
    async def chat_api(req: ChatRequest):
        """REST API 聊天（非流式）"""
        from paw.core.agent import Agent

        session_id = req.session_id or str(uuid.uuid4())[:8]
        cfg = dict(config)

        if req.model:
            cfg["llm"]["model"] = req.model
        if req.persona:
            from paw.personas import get_persona
            p = get_persona(req.persona)
            cfg["agent"]["system_prompt"] = p["system_prompt"]

        agent = Agent(config=cfg, session_id=session_id)
        try:
            response = await agent.chat(req.message)
            usage = agent.get_token_usage()
            return {
                "session_id": session_id,
                "response": response,
                "usage": usage,
            }
        finally:
            await agent.close()

    @app.get("/api/tools")
    async def list_tools():
        """列出所有可用工具"""
        from paw.core.tools import get_all_tools
        tools = get_all_tools()
        return [
            {"name": t.name, "description": t.description}
            for t in tools
        ]

    @app.get("/api/personas")
    async def list_personas_api():
        """列出所有人格"""
        from paw.personas import list_personas
        return list_personas()

    @app.get("/api/config")
    async def get_config():
        """获取当前配置（脱敏）"""
        safe = dict(config)
        if safe.get("llm", {}).get("api_key"):
            key = safe["llm"]["api_key"]
            safe["llm"]["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return safe

    @app.get("/health")
    async def health():
        """健康检查"""
        return {"status": "ok", "version": "0.3.0"}

    return app


def _handle_command(cmd: str, agent, session_id: str, config: dict = None) -> str:
    """处理 Web 端的命令"""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == "/clear":
        agent.memory.clear_session(session_id)
        return "🗑️ 会话已清空"

    elif command == "/new":
        import uuid as uuid_mod
        old_id = session_id
        new_id = str(uuid_mod.uuid4())[:8]
        agent.session_id = new_id
        return f"✅ 新会话: {new_id} (旧会话 {old_id} 已保留)"

    elif command == "/model":
        if args:
            agent.llm.model = args
            return f"✅ 模型已切换: {args}"
        return f"当前模型: {agent.llm.model}"

    elif command == "/system":
        if args:
            agent.system_prompt = args
            return f"✅ 系统提示已更新"
        current = agent.system_prompt or "(未设置)"
        return f"当前系统提示:\n{current}\n\n用法: /system <新的系统提示>"

    elif command == "/persona":
        if args:
            from paw.personas import get_persona, PERSONAS
            pname = args.strip()
            if pname in PERSONAS:
                p = get_persona(pname)
                agent.system_prompt = p["system_prompt"]
                if config:
                    config["agent"]["system_prompt"] = p["system_prompt"]
                    config["agent"]["_persona"] = pname
                return f"✅ 人格已切换: {p['emoji']} {p['name']} - {p['description']}"
            return f"❌ 未知人格: {pname}"
        from paw.personas import list_personas
        personas = list_personas()
        return "可用人格:\n" + "\n".join(
            f"  {p['emoji']} {p['key']} - {p['description']}" for p in personas
        )

    elif command == "/tokens":
        usage = agent.get_token_usage()
        return (
            f"📊 Token 用量:\n"
            f"  Prompt: {usage['prompt_tokens']}\n"
            f"  Completion: {usage['completion_tokens']}\n"
            f"  Total: {usage['total_tokens']}\n"
            f"  请求次数: {usage['requests']}"
        )

    elif command == "/help":
        return (
            "可用命令:\n"
            "/clear - 清空会话\n"
            "/new - 新建会话\n"
            "/model <名称> - 切换模型\n"
            "/persona <id> - 切换人格\n"
            "/system <提示> - 修改系统提示\n"
            "/tokens - 查看 Token 用量\n"
            "/help - 显示帮助"
        )

    return f"未知命令: {command}"
