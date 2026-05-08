"""Paw CLI v3 - 会话管理、插件系统、Token 追踪、流式 Markdown"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax

from paw import __version__, __app_name__
from paw.config import load_config, save_config, update_config, CONFIG_FILE, DEFAULT_CONFIG
from paw.personas import get_persona, list_personas, PERSONAS

app = typer.Typer(
    name="paw",
    help="🐾 Paw - 轻量级 AI 智能体框架",
    add_completion=False,
)
console = Console()


def _print_banner():
    console.print(Panel.fit(
        f"[bold cyan]🐾 {__app_name__}[/] v{__version__}\n"
        "[dim]轻量级 AI 智能体 · 输入消息开始对话 · /help 查看命令[/]",
        border_style="cyan",
    ))


def _print_help():
    console.print("""
[bold]聊天命令:[/]
  [cyan]/help[/]         显示帮助
  [cyan]/new[/]          新建会话
  [cyan]/sessions[/]     查看/切换会话
  [cyan]/clear[/]        清空当前会话
  [cyan]/history[/]      查看历史消息
  [cyan]/export[/]       导出当前会话为 Markdown

[bold]配置命令:[/]
  [cyan]/config[/]       查看当前配置
  [cyan]/model[/]        切换模型
  [cyan]/persona[/]      切换/查看人格
  [cyan]/system[/]       查看/修改系统提示
  [cyan]/tools[/]        列出可用工具
  [cyan]/plugins[/]      管理插件
  [cyan]/tokens[/]       查看 Token 用量

[bold]直接输入消息即可与 AI 对话[/]
""")


def _export_session(agent, session_id: str) -> str:
    """导出会话为 Markdown"""
    messages = agent.memory.get_messages(session_id, limit=200)
    if not messages:
        return ""

    lines = [f"# 🐾 Paw 对话记录\n"]
    lines.append(f"会话 ID: {session_id}")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    role_map = {
        "user": "👤 用户",
        "assistant": "🐾 Paw",
        "tool": "🔧 工具",
        "system": "⚙️ 系统",
    }

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_name = msg.get("name", "")

        role_display = role_map.get(role, role)

        if role == "tool" and tool_name:
            lines.append(f"### 🔧 工具: {tool_name}\n")
            lines.append(f"```\n{content}\n```\n")
        elif role == "assistant":
            lines.append(f"### {role_display}\n")
            lines.append(f"{content}\n")
        elif role == "user":
            lines.append(f"### {role_display}\n")
            lines.append(f"{content}\n")
        else:
            lines.append(f"**{role_display}:** {content}\n")

    return "\n".join(lines)


def _load_plugins(config: dict):
    """加载插件"""
    if not config.get("tools", {}).get("plugins_enabled", True):
        return {}
    try:
        from paw.plugins import load_plugins
        return load_plugins()
    except Exception as e:
        console.print(f"[yellow]⚠️ 插件加载失败: {e}[/]")
        return {}


def _show_personas():
    """显示可用人格列表"""
    table = Table(title="可用人格", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("表情")
    table.add_column("名称")
    table.add_column("描述")
    for p in list_personas():
        table.add_row(p["key"], p["emoji"], p["name"], p["description"])
    console.print(table)
    console.print("[dim]使用 /persona <id> 切换人格[/]")


def _show_sessions(memory, current_session_id: str):
    """显示会话列表"""
    sessions = memory.get_sessions(limit=20)
    if not sessions:
        console.print("[dim]暂无历史会话[/]")
        return

    table = Table(title="会话列表", show_lines=True)
    table.add_column("", width=3)
    table.add_column("会话 ID", style="cyan")
    table.add_column("标题", max_width=40)
    table.add_column("人格")
    table.add_column("消息数", justify="right")
    table.add_column("最后活跃")

    for s in sessions:
        sid = s["session_id"]
        is_current = "▶" if sid == current_session_id else " "
        ts = datetime.fromtimestamp(s["last_active"]).strftime("%m-%d %H:%M")
        title = s.get("title", "") or "(无标题)"
        persona = s.get("persona", "default")
        table.add_row(is_current, sid, title, persona, str(s["message_count"]), ts)

    console.print(table)
    console.print("[dim]使用 /switch <会话ID> 切换会话[/]")


@app.command()
def chat(
    model: str = typer.Option(None, "--model", "-m", help="指定模型"),
    session: str = typer.Option(None, "--session", "-s", help="会话 ID"),
    persona: str = typer.Option(None, "--persona", "-p", help="人格"),
    no_tokens: bool = typer.Option(False, "--no-tokens", help="不显示 token 用量"),
):
    """开始聊天"""
    import paw.tools.builtin

    config = load_config()

    if not config["llm"].get("api_key"):
        console.print("[red]❌ 未配置 API Key！[/]")
        console.print(f"请运行 [cyan]paw init[/] 或编辑 [cyan]{CONFIG_FILE}[/]")
        raise typer.Exit(1)

    if model:
        config["llm"]["model"] = model

    # 设置人格
    if persona:
        p = get_persona(persona)
        config["agent"]["system_prompt"] = p["system_prompt"]
        config["agent"]["_persona"] = persona

    session_id = session or str(uuid.uuid4())[:8]

    # 加载插件
    plugin_results = _load_plugins(config)
    if plugin_results:
        loaded = sum(1 for r in plugin_results.values() if r["tools"] and not r["errors"])
        if loaded:
            console.print(f"[dim]🔌 已加载 {loaded} 个插件[/]")

    from paw.core.agent import Agent
    agent = Agent(config=config, session_id=session_id)

    # 显示人格信息
    persona_name = config["agent"].get("_persona", "default")
    persona_info = get_persona(persona_name)

    _print_banner()
    console.print(
        f"[dim]会话: {session_id} · "
        f"模型: {config['llm']['model']} · "
        f"人格: {persona_info['emoji']} {persona_info['name']}[/]\n"
    )

    show_tokens = config.get("agent", {}).get("show_token_usage", True) and not no_tokens

    try:
        while True:
            try:
                user_input = console.input("[bold green]你> [/]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]再见 👋[/]")
                break

            if not user_input:
                continue

            # 内置命令
            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                args = user_input.split(maxsplit=1)[1] if " " in user_input else ""

                if cmd in ("/quit", "/exit", "/q"):
                    console.print("[dim]再见 👋[/]")
                    break

                elif cmd == "/help":
                    _print_help()
                    continue

                elif cmd == "/new":
                    # 新建会话
                    old_id = session_id
                    session_id = str(uuid.uuid4())[:8]
                    agent.session_id = session_id
                    console.print(f"[green]✅ 新会话: {session_id}[/] (旧会话 {old_id} 已保留)")
                    continue

                elif cmd == "/sessions":
                    _show_sessions(agent.memory, session_id)
                    continue

                elif cmd == "/switch":
                    if not args:
                        console.print("[yellow]用法: /switch <会话ID>[/]")
                        continue
                    target = args.strip()
                    # 验证会话存在
                    sessions = agent.memory.get_sessions()
                    valid_ids = [s["session_id"] for s in sessions]
                    if target in valid_ids:
                        session_id = target
                        agent.session_id = target
                        msg_count = len(agent.memory.get_messages(target, limit=999))
                        console.print(f"[green]✅ 已切换到会话 {target} ({msg_count} 条消息)[/]")
                    else:
                        console.print(f"[red]❌ 会话 {target} 不存在[/]")
                    continue

                elif cmd == "/clear":
                    agent.memory.clear_session(session_id)
                    console.print("[yellow]会话已清空[/]")
                    continue

                elif cmd == "/history":
                    messages = agent.memory.get_messages(session_id, limit=50)
                    if not messages:
                        console.print("[dim]当前会话无历史消息[/]")
                    else:
                        table = Table(title=f"会话 {session_id} 的历史", show_lines=False)
                        table.add_column("角色", style="cyan", width=10)
                        table.add_column("内容", max_width=70)
                        for msg in messages:
                            role = msg.get("role", "?")
                            content = msg.get("content", "")
                            if content:
                                display = content[:100] + "..." if len(content) > 100 else content
                                table.add_row(role, display.replace("\n", " "))
                        console.print(table)
                    continue

                elif cmd == "/config":
                    safe = dict(config)
                    if safe.get("llm", {}).get("api_key"):
                        key = safe["llm"]["api_key"]
                        safe["llm"]["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                    import json
                    console.print_json(json.dumps(safe, ensure_ascii=False, indent=2))
                    continue

                elif cmd == "/model":
                    if args:
                        config["llm"]["model"] = args
                        agent.llm.model = args
                        console.print(f"[green]模型已切换: {args}[/]")
                    else:
                        console.print(f"当前模型: [cyan]{config['llm']['model']}[/]")
                    continue

                elif cmd == "/persona":
                    if args:
                        pname = args.strip()
                        if pname in PERSONAS:
                            p = get_persona(pname)
                            config["agent"]["system_prompt"] = p["system_prompt"]
                            config["agent"]["_persona"] = pname
                            agent.system_prompt = p["system_prompt"]
                            console.print(f"[green]人格已切换: {p['emoji']} {p['name']} - {p['description']}[/]")
                        else:
                            console.print(f"[red]未知人格: {pname}[/]")
                            _show_personas()
                    else:
                        _show_personas()
                    continue

                elif cmd == "/system":
                    if args:
                        agent.system_prompt = args
                        config["agent"]["system_prompt"] = args
                        console.print(f"[green]✅ 系统提示已更新[/]")
                        console.print(f"[dim]{args[:100]}{'...' if len(args) > 100 else ''}[/]")
                    else:
                        current = agent.system_prompt or "(未设置)"
                        console.print(f"[bold]当前系统提示:[/]\n{current}")
                        console.print("\n[dim]用法: /system <新的系统提示>[/]")
                    continue

                elif cmd == "/export":
                    content = _export_session(agent, session_id)
                    if content:
                        export_dir = Path.home() / ".paw" / "exports"
                        export_dir.mkdir(parents=True, exist_ok=True)
                        filename = f"paw_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                        export_path = export_dir / filename
                        export_path.write_text(content, encoding="utf-8")
                        console.print(f"[green]✅ 已导出到: {export_path}[/]")
                    else:
                        console.print("[yellow]当前会话无内容可导出[/]")
                    continue

                elif cmd == "/tools":
                    from paw.core.tools import get_all_tools
                    tools = get_all_tools()
                    table = Table(title="可用工具", show_lines=True)
                    table.add_column("工具名", style="cyan")
                    table.add_column("描述")
                    for t in tools:
                        table.add_row(t.name, t.description)
                    console.print(table)
                    continue

                elif cmd == "/plugins":
                    from paw.plugins import PLUGINS_DIR, discover_plugins, get_plugin_template
                    plugin_files = discover_plugins()
                    if args == "init":
                        # 创建插件模板
                        name = Prompt.ask("插件名称", default="my_plugin")
                        from paw.plugins import create_plugin_scaffold
                        try:
                            path = create_plugin_scaffold(name)
                            console.print(f"[green]✅ 插件模板已创建: {path}[/]")
                            console.print("[dim]编辑后重启 paw chat 即可生效[/]")
                        except FileExistsError:
                            console.print(f"[yellow]插件 {name} 已存在[/]")
                    elif args == "reload":
                        results = _load_plugins(config)
                        if results:
                            for name, r in results.items():
                                status = "✅" if r["tools"] and not r["errors"] else "❌"
                                console.print(f"  {status} {name}: {r['tools']}")
                        else:
                            console.print("[dim]无插件[/]")
                    else:
                        console.print(f"[bold]插件目录:[/] {PLUGINS_DIR}")
                        if plugin_files:
                            for f in plugin_files:
                                console.print(f"  📄 {f.name}")
                        else:
                            console.print("[dim]  (空)[/]")
                        console.print("\n[dim]用法: /plugins init 创建模板 | /plugins reload 重载[/]")
                    continue

                elif cmd == "/tokens":
                    usage = agent.get_token_usage()
                    console.print(Panel(
                        f"Prompt tokens:     {usage['prompt_tokens']}\n"
                        f"Completion tokens: {usage['completion_tokens']}\n"
                        f"Total tokens:      {usage['total_tokens']}\n"
                        f"请求次数:          {usage['requests']}",
                        title="📊 Token 用量",
                        border_style="cyan",
                    ))
                    continue

                else:
                    console.print(f"[yellow]未知命令: {cmd}，输入 /help 查看帮助[/]")
                    continue

            # 调用 Agent — 流式输出（修复双重打印）
            try:
                async def _run():
                    full_text = ""

                    async for event in agent.chat_stream(user_input):
                        if event["type"] == "token":
                            full_text += event["content"]
                            # 直接用 console 输出，保持颜色
                            console.print(event["content"], end="", highlight=False)

                        elif event["type"] == "tool_start":
                            name = event["name"]
                            args = event["args"]
                            args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
                            console.print(f"\n  [dim]🔧 {name}({args_str})[/]")

                        elif event["type"] == "tool_result":
                            result_preview = event["result"][:100].replace("\n", " ")
                            console.print(f"  [dim]   ✓ {result_preview}...[/]")

                        elif event["type"] == "tool_error":
                            console.print(f"  [red]   ✗ {event['error']}[/]")

                        elif event["type"] == "round":
                            console.print(f"\n  [dim]--- 第 {event['number']} 轮 ---[/]")

                        elif event["type"] == "done":
                            break

                    return full_text

                result = asyncio.run(_run())

                # 流式结束后换行，显示 token 用量
                console.print()  # 换行
                if show_tokens:
                    console.print(f"[dim]{agent.get_token_summary()}[/]")
                console.print()  # 空行分隔

            except KeyboardInterrupt:
                console.print("\n[yellow]已中断[/]")
            except Exception as e:
                console.print(f"\n[red]错误: {e}[/]")

    finally:
        asyncio.run(agent.close())


@app.command()
def init():
    """初始化配置（新手引导）"""
    _print_banner()
    console.print("\n[bold]🐾 欢迎使用 Paw！让我们来配置一下。\n[/]")

    config = DEFAULT_CONFIG.copy()

    console.print("[bold]1. LLM API 配置[/]")
    console.print("[dim]支持 OpenAI、DeepSeek、通义千问等 OpenAI 兼容 API[/]\n")

    api_key = Prompt.ask("   API Key", password=True)
    config["llm"]["api_key"] = api_key

    base_url = Prompt.ask(
        "   API Base URL",
        default="https://api.openai.com/v1"
    )
    config["llm"]["base_url"] = base_url

    model = Prompt.ask("   模型名称", default="gpt-4o-mini")
    config["llm"]["model"] = model

    console.print("\n[bold]2. Agent 配置[/]")
    name = Prompt.ask("   给你的 Agent 起个名字", default="Paw")
    config["agent"]["name"] = name

    # 选择人格
    console.print("\n[bold]3. 选择人格[/]")
    _show_personas()
    persona_choice = Prompt.ask("   选择人格", default="default")
    if persona_choice in PERSONAS:
        p = get_persona(persona_choice)
        config["agent"]["system_prompt"] = p["system_prompt"]
        config["agent"]["_persona"] = persona_choice
        console.print(f"   [green]已选择: {p['emoji']} {p['name']}[/]")

    console.print("\n[bold]4. Web UI 配置[/]")
    port = Prompt.ask("   Web UI 端口", default="8765")
    config["web"]["port"] = int(port)

    save_config(config)

    # 创建插件目录
    from paw.plugins import PLUGINS_DIR
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[green]✅ 配置已保存到 {CONFIG_FILE}[/]")
    console.print(f"[green]✅ 插件目录: {PLUGINS_DIR}[/]")
    console.print("\n[bold]现在可以开始使用了：[/]")
    console.print("  [cyan]paw chat[/]              开始聊天")
    console.print("  [cyan]paw chat -p coder[/]     以编程专家身份聊天")
    console.print("  [cyan]paw web[/]               启动 Web UI")
    console.print("  [cyan]paw --help[/]            查看所有命令\n")


@app.command()
def web(
    host: str = typer.Option(None, "--host", "-h", help="监听地址"),
    port: int = typer.Option(None, "--port", "-p", help="监听端口"),
):
    """启动 Web UI"""
    import paw.tools.builtin

    config = load_config()

    if not config["llm"].get("api_key"):
        console.print("[red]❌ 未配置 API Key！请运行 paw init[/]")
        raise typer.Exit(1)

    web_host = host or config["web"].get("host", "127.0.0.1")
    web_port = port or config["web"].get("port", 8765)

    # 加载插件
    plugin_results = _load_plugins(config)
    if plugin_results:
        loaded = sum(1 for r in plugin_results.values() if r["tools"] and not r["errors"])
        if loaded:
            console.print(f"[dim]🔌 已加载 {loaded} 个插件[/]")

    console.print(Panel.fit(
        f"[bold cyan]🐾 Paw Web UI[/]\n\n"
        f"访问地址: [link=http://{web_host}:{web_port}]http://{web_host}:{web_port}[/link]\n"
        f"[dim]按 Ctrl+C 停止[/]",
        border_style="cyan",
    ))

    from paw.web.app import create_app
    import uvicorn

    app_instance = create_app(config)
    uvicorn.run(app_instance, host=web_host, port=web_port, log_level="warning")


@app.command()
def config_show():
    """查看当前配置"""
    cfg = load_config()
    safe = dict(cfg)
    if safe.get("llm", {}).get("api_key"):
        key = safe["llm"]["api_key"]
        safe["llm"]["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    import json
    console.print_json(json.dumps(safe, ensure_ascii=False, indent=2))


@app.command()
def config_set(
    key: str = typer.Argument(..., help="配置键（如 llm.model）"),
    value: str = typer.Argument(..., help="配置值"),
):
    """修改配置项"""
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)

    update_config(key, value)
    console.print(f"[green]✅ 已设置 {key} = {value}[/]")


@app.command()
def plugins(
    action: str = typer.Argument("list", help="操作: list / init / reload"),
):
    """管理插件"""
    from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
    import paw.tools.builtin

    if action == "init":
        name = Prompt.ask("插件名称", default="my_plugin")
        try:
            path = create_plugin_scaffold(name)
            console.print(f"[green]✅ 插件模板已创建: {path}[/]")
        except FileExistsError:
            console.print(f"[yellow]插件 {name} 已存在[/]")

    elif action == "reload":
        config = load_config()
        results = _load_plugins(config)
        if results:
            for name, r in results.items():
                status = "✅" if r["tools"] and not r["errors"] else "❌"
                tools_str = ", ".join(r["tools"]) if r["tools"] else "(无)"
                errors_str = f" [red]{r['errors'][0]}[/]" if r["errors"] else ""
                console.print(f"  {status} {name}: {tools_str}{errors_str}")
        else:
            console.print("[dim]无插件[/]")

    else:  # list
        plugin_files = discover_plugins()
        console.print(f"[bold]插件目录:[/] {PLUGINS_DIR}")
        if plugin_files:
            for f in plugin_files:
                console.print(f"  📄 {f.name}")
        else:
            console.print("[dim]  (空)[/]")
        console.print("\n[dim]paw plugins init  创建插件模板[/]")
        console.print("[dim]paw plugins reload  重载插件[/]")


@app.command()
def version():
    """显示版本"""
    console.print(f"🐾 {__app_name__} v{__version__}")


if __name__ == "__main__":
    app()
