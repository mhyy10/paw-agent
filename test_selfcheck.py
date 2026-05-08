#!/usr/bin/env python3
"""Paw v0.3.0 自测脚本"""
import sys
import json

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")

# ========== 1. 模块导入 ==========
print("\n=== 1. 模块导入 ===")
try:
    import paw
    check("paw 包", True)
except Exception as e:
    check("paw 包", False, str(e))

try:
    from paw import __version__
    check("版本号", __version__ == "0.3.0", f"got {__version__}")
except Exception as e:
    check("版本号", False, str(e))

try:
    from paw.config import load_config, CONFIG_FILE, DEFAULT_CONFIG
    check("config 模块", True)
except Exception as e:
    check("config 模块", False, str(e))

try:
    from paw.personas import PERSONAS, list_personas, get_persona
    check("personas 模块", True)
except Exception as e:
    check("personas 模块", False, str(e))

try:
    from paw.core.agent import Agent
    check("agent 模块", True)
except Exception as e:
    check("agent 模块", False, str(e))

try:
    from paw.core.llm import LLMClient, TokenUsage
    check("llm 模块", True)
except Exception as e:
    check("llm 模块", False, str(e))

try:
    from paw.core.memory import Memory
    check("memory 模块", True)
except Exception as e:
    check("memory 模块", False, str(e))

try:
    from paw.core.tools import tool, get_all_tools, get_tools_schema, ToolDef
    check("tools 模块", True)
except Exception as e:
    check("tools 模块", False, str(e))

try:
    from paw.plugins import load_plugins, discover_plugins, PLUGINS_DIR, get_plugin_template
    check("plugins 模块", True)
except Exception as e:
    check("plugins 模块", False, str(e))

# ========== 2. 配置系统 ==========
print("\n=== 2. 配置系统 ===")
try:
    cfg = load_config()
    check("load_config 返回 dict", isinstance(cfg, dict))
    check("默认配置有 llm", "llm" in cfg)
    check("默认配置有 agent", "agent" in cfg)
    check("默认配置有 web", "web" in cfg)
    check("默认配置有 tools", "tools" in cfg)
    check("agent 有 max_retries", "max_retries" in cfg.get("agent", {}))
    check("agent 有 show_token_usage", "show_token_usage" in cfg.get("agent", {}))
    check("tools 有 plugins_enabled", "plugins_enabled" in cfg.get("tools", {}))
except Exception as e:
    check("配置系统", False, str(e))

# ========== 3. 人格系统 ==========
print("\n=== 3. 人格系统 ===")
try:
    personas = list_personas()
    check("list_personas 返回列表", isinstance(personas, list))
    check("至少有 6 个人格", len(personas) >= 6, f"got {len(personas)}")
    p = get_persona("coder")
    check("get_persona 有 system_prompt", "system_prompt" in p)
    check("get_persona 有 name", "name" in p)
    check("get_persona 有 emoji", "emoji" in p)
except Exception as e:
    check("人格系统", False, str(e))

# ========== 4. 工具系统 ==========
print("\n=== 4. 工具系统 ===")
try:
    import paw.tools.builtin
    tools = get_all_tools()
    tool_names = [t.name for t in tools]
    check("工具数量 >= 8", len(tools) >= 8, f"got {len(tools)}")
    check("read_file 工具", "read_file" in tool_names)
    check("write_file 工具", "write_file" in tool_names)
    check("run_command 工具", "run_command" in tool_names)
    check("list_dir 工具", "list_dir" in tool_names)
    check("search_files 工具", "search_files" in tool_names)
    check("edit_file 工具", "edit_file" in tool_names)
    check("web_fetch 工具", "web_fetch" in tool_names)
    check("python_repl 工具", "python_repl" in tool_names)

    schema = get_tools_schema()
    check("OpenAI schema 格式", all(s.get("type") == "function" for s in schema))
    check("schema 有 function.name", all("name" in s.get("function", {}) for s in schema))
except Exception as e:
    check("工具系统", False, str(e))

# ========== 5. 工具执行 ==========
print("\n=== 5. 工具执行 ===")
try:
    from paw.core.tools import get_tool
    import asyncio

    async def test_tools():
        # read_file
        t = get_tool("read_file")
        r = await t.execute(path="/etc/hostname")
        check("read_file 执行", "content" in r or "error" not in r, r[:100])

        # list_dir
        t = get_tool("list_dir")
        r = await t.execute(path="/tmp")
        check("list_dir 执行", "items" in r or "error" not in r, r[:100])

        # write_file + read_file
        t = get_tool("write_file")
        r = await t.execute(path="/tmp/paw_test.txt", content="hello paw")
        check("write_file 执行", "success" in r, r[:100])

        t = get_tool("read_file")
        r = await t.execute(path="/tmp/paw_test.txt")
        check("read_file 验证写入", "hello paw" in str(r), r[:100])

        # run_command
        t = get_tool("run_command")
        r = await t.execute(command="echo paw_test_ok")
        check("run_command 执行", "paw_test_ok" in str(r), r[:100])

        # python_repl
        t = get_tool("python_repl")
        r = await t.execute(code="print(2 + 3)")
        check("python_repl 执行", "5" in str(r), r[:100])

        # search_files
        t = get_tool("search_files")
        r = await t.execute(pattern="paw_test_ok", path="/tmp")
        check("search_files 执行", "matches" in r or "error" not in r, r[:100])

    asyncio.run(test_tools())
except Exception as e:
    check("工具执行", False, str(e))

# ========== 6. Token 追踪 ==========
print("\n=== 6. Token 追踪 ===")
try:
    usage = TokenUsage()
    check("TokenUsage 初始化", usage.total_tokens == 0)

    usage.add({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    check("TokenUsage.add", usage.total_tokens == 150)
    check("TokenUsage prompt", usage.prompt_tokens == 100)
    check("TokenUsage completion", usage.completion_tokens == 50)
    check("TokenUsage requests", usage.requests == 1)

    usage.add({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
    check("TokenUsage 累加", usage.total_tokens == 450)
    check("TokenUsage requests 累加", usage.requests == 2)

    summary = usage.summary()
    check("TokenUsage.summary()", "450" in summary)

    d = usage.to_dict()
    check("TokenUsage.to_dict()", d["total_tokens"] == 450)
except Exception as e:
    check("Token 追踪", False, str(e))

# ========== 7. 记忆系统 ==========
print("\n=== 7. 记忆系统 ===")
try:
    import tempfile, os
    tmp_db = tempfile.mktemp(suffix=".db")
    mem = Memory(tmp_db)

    # 基本操作
    mem.add_message("test_s1", "user", "你好")
    mem.add_message("test_s1", "assistant", "你好！")
    msgs = mem.get_messages("test_s1")
    check("添加和获取消息", len(msgs) == 2)

    # 会话列表
    sessions = mem.get_sessions()
    check("会话列表", len(sessions) >= 1)
    check("会话有 message_count", sessions[0]["message_count"] >= 2)

    # 会话元数据
    mem.set_session_meta("test_s1", title="测试会话")
    sessions = mem.get_sessions()
    check("会话元数据", sessions[0].get("title") == "测试会话")

    # 会话计数
    count = mem.get_session_count()
    check("会话计数", count >= 1)

    # 清空
    mem.clear_session("test_s1")
    msgs = mem.get_messages("test_s1")
    check("清空会话", len(msgs) == 0)

    os.unlink(tmp_db)
except Exception as e:
    check("记忆系统", False, str(e))

# ========== 8. 插件系统 ==========
print("\n=== 8. 插件系统 ===")
try:
    check("插件目录", PLUGINS_DIR.name == "plugins")

    template = get_plugin_template()
    check("插件模板", "@tool" in template)
    check("插件模板有示例", "my_custom_tool" in template)

    plugins = discover_plugins()
    check("discover_plugins 返回 list", isinstance(plugins, list))
except Exception as e:
    check("插件系统", False, str(e))

# ========== 9. LLM 重试配置 ==========
print("\n=== 9. LLM 客户端 ===")
try:
    client = LLMClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        max_retries=5,
    )
    check("LLMClient 初始化", client.max_retries == 5)
    check("LLMClient 有 usage", hasattr(client, "usage"))
    check("LLMClient usage 类型", isinstance(client.usage, TokenUsage))
except Exception as e:
    check("LLM 客户端", False, str(e))

# ========== 10. CLI 入口 ==========
print("\n=== 10. CLI 入口 ===")
try:
    from paw.cli import app as cli_app
    check("CLI app 加载", cli_app is not None)
except Exception as e:
    check("CLI 入口", False, str(e))

# ========== 11. Web 入口 ==========
print("\n=== 11. Web 入口 ===")
try:
    from paw.web.app import create_app
    web_app = create_app({"llm": {"api_key": "test", "base_url": "http://x", "model": "m"},
                          "agent": {"name": "Test"}, "web": {"host": "127.0.0.1", "port": 8765},
                          "tools": {"plugins_enabled": False}})
    check("Web app 创建", web_app is not None)
    check("Web app 有 /health", any(r.path == "/health" for r in web_app.routes))
    check("Web app 有 /api/sessions", any(r.path == "/api/sessions" for r in web_app.routes))
    check("Web app 有 /api/chat", any(r.path == "/api/chat" for r in web_app.routes))
    check("Web app 有 /api/tools", any(r.path == "/api/tools" for r in web_app.routes))
except Exception as e:
    check("Web 入口", False, str(e))

# ========== 结果 ==========
print(f"\n{'='*40}")
print(f"  ✅ 通过: {PASS}  ❌ 失败: {FAIL}")
print(f"{'='*40}")

if FAIL > 0:
    sys.exit(1)
else:
    print("  🎉 全部通过！")
    sys.exit(0)
