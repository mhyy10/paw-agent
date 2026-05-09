"""Paw CLI v5 - 修复乱码：统一输出，隔离 Rich 和 prompt_toolkit"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from paw import __version__, __app_name__
from paw.config import load_config, save_config, update_config, CONFIG_FILE, DEFAULT_CONFIG
from paw.personas import get_persona, list_personas, PERSONAS

app = typer.Typer(
    name="paw",
    help="🐾 Paw - 轻量级 AI 智能体框架",
    add_completion=False,
)

# 关键: force_terminal=True 确保 Rich 始终输出 ANSI 码
# 即使 stdout 被 prompt_toolkit 临时接管也不会丢失颜色
console = Console(force_terminal=True)


# ========== ANSI 转义码工具 ==========
# 用于在 prompt_toolkit 和流式输出中直接写入颜色

class S:
    """ANSI 样式常量"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # 组合样式
    BOLD_CYAN = "\033[1;36m"
    BOLD_GREEN = "\033[1;32m"
    DIM_CYAN = "\033[2;36m"
    BRIGHT_BLACK = "\033[90m"


def _write(text: str):
    """直接写入 stdout 并刷新"""
    sys.stdout.write(text)
    sys.stdout.flush()


def _write_line(text: str = ""):
    """写入一行"""
    _write(text + "\n")


def _print(text: str):
    """用 Rich 打印 (带颜色)"""
    console.print(text)


def _print_plain(text: str):
    """纯文本打印 (无 Rich 格式化，避免冲突)"""
    _write_line(text)


# ========== 显示函数 ==========

def _print_banner():
    _print(Panel.fit(
        f"[bold cyan]🐾 {__app_name__}[/] v{__version__}\n"
        "[dim]轻量级 AI 智能体 · Tab 补全 · Ctrl+L 清屏 · /help 帮助[/]",
        border_style="cyan",
    ))


def _print_help():
    _write_line(f"""
{S.BOLD_CYAN}聊天命令:{S.RESET}
  {S.CYAN}/help{S.RESET}         显示帮助
  {S.CYAN}/new{S.RESET}          新建会话
  {S.CYAN}/sessions{S.RESET}     查看/切换会话
  {S.CYAN}/switch <id>{S.RESET}  切换到指定会话
  {S.CYAN}/clear{S.RESET}        清空当前会话
  {S.CYAN}/history{S.RESET}      查看历史消息
  {S.CYAN}/export{S.RESET}       导出为 Markdown

{S.BOLD_CYAN}配置命令:{S.RESET}
  {S.CYAN}/config{S.RESET}       查看当前配置
  {S.CYAN}/model <名称>{S.RESET} 切换模型
  {S.CYAN}/persona <id>{S.RESET} 切换人格
  {S.CYAN}/system <提示>{S.RESET} 查看/修改系统提示
  {S.CYAN}/tools{S.RESET}        列出可用工具
  {S.CYAN}/plugins{S.RESET}      管理插件
  {S.CYAN}/tokens{S.RESET}       查看 Token 用量

{S.BOLD_CYAN}快捷键:{S.RESET}
  {S.CYAN}Tab{S.RESET}           自动补全
  {S.CYAN}↑/↓{S.RESET}           浏览历史输入
  {S.CYAN}Ctrl+L{S.RESET}        清屏
  {S.CYAN}Ctrl+C{S.RESET}        中断/清空输入
  {S.CYAN}Ctrl+D{S.RESET}        退出 (空输入时)

{S.BOLD}直接输入消息即可与 AI 对话{S.RESET}
""")


def _show_sessions(memory, current_session_id: str):
    sessions = memory.get_sessions(limit=20)
    if not sessions:
        _write_line(f"{S.DIM}暂无历史会话{S.RESET}")
        return

    table = Table(title="会话列表", show_lines=True, border_style="cyan")
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

    _print(table)
    _write_line(f"{S.DIM}使用 /switch <会话ID> 切换会话{S.RESET}")


def _show_personas():
    table = Table(title="可用人格", show_lines=True, border_style="cyan")
    table.add_column("ID", style="cyan")
    table.add_column("表情")
    table.add_column("名称")
    table.add_column("描述")
    for p in list_personas():
        table.add_row(p["key"], p["emoji"], p["name"], p["description"])
    _print(table)
    _write_line(f"{S.DIM}使用 /persona <id> 切换人格{S.RESET}")


def _export_session(agent, session_id: str) -> str:
    messages = agent.memory.get_messages(session_id, limit=200)
    if not messages:
        return ""

    lines = [f"# 🐾 Paw 对话记录\n"]
    lines.append(f"会话 ID: {session_id}")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    role_map = {"user": "👤 用户", "assistant": "🐾 Paw", "tool": "🔧 工具", "system": "⚙️ 系统"}

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_name = msg.get("name", "")
        role_display = role_map.get(role, role)

        if role == "tool" and tool_name:
            lines.append(f"### 🔧 工具: {tool_name}\n")
            lines.append(f"```\n{content}\n```\n")
        elif role in ("assistant", "user"):
            lines.append(f"### {role_display}\n")
            lines.append(f"{content}\n")
        else:
            lines.append(f"**{role_display}:** {content}\n")

    return "\n".join(lines)


def _load_plugins(config: dict):
    if not config.get("tools", {}).get("plugins_enabled", True):
        return {}
    try:
        from paw.plugins import load_plugins
        return load_plugins()
    except Exception as e:
        _write_line(f"{S.YELLOW}⚠️ 插件加载失败: {e}{S.RESET}")
        return {}


# ========== 命令处理 ==========

def handle_command(cmd_line: str, agent, session_id: str, config: dict,
                   paw_input=None) -> tuple:
    parts = cmd_line.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        raise SystemExit(0)

    elif cmd == "/help":
        _print_help()

    elif cmd == "/new":
        old_id = session_id
        session_id = str(uuid.uuid4())[:8]
        agent.session_id = session_id
        first_msg = agent.memory.get_last_user_message(old_id)
        if first_msg:
            agent.memory.set_session_meta(old_id, title=first_msg[:50])
        _write_line(f"{S.GREEN}✅ 新会话: {session_id}{S.RESET} {S.DIM}(旧会话 {old_id} 已保留){S.RESET}")
        if paw_input:
            paw_input.update_session_id(session_id)

    elif cmd == "/sessions":
        _show_sessions(agent.memory, session_id)

    elif cmd == "/switch":
        if not args:
            _write_line(f"{S.YELLOW}用法: /switch <会话ID>{S.RESET}")
        else:
            target = args.strip()
            sessions = agent.memory.get_sessions()
            valid_ids = [s["session_id"] for s in sessions]
            if target in valid_ids:
                session_id = target
                agent.session_id = target
                msg_count = len(agent.memory.get_messages(target, limit=999))
                _write_line(f"{S.GREEN}✅ 已切换到会话 {target}{S.RESET} {S.DIM}({msg_count} 条消息){S.RESET}")
                if paw_input:
                    paw_input.update_session_id(target)
            else:
                _write_line(f"{S.RED}❌ 会话 {target} 不存在{S.RESET}")

    elif cmd == "/clear":
        agent.memory.clear_session(session_id)
        _write_line(f"{S.YELLOW}🗑️ 会话已清空{S.RESET}")

    elif cmd == "/history":
        messages = agent.memory.get_messages(session_id, limit=50)
        if not messages:
            _write_line(f"{S.DIM}当前会话无历史消息{S.RESET}")
        else:
            table = Table(title=f"会话 {session_id}", show_lines=False, border_style="dim")
            table.add_column("角色", style="cyan", width=10)
            table.add_column("内容", max_width=70)
            for msg in messages:
                role = msg.get("role", "?")
                content = msg.get("content", "")
                if content:
                    display = content[:100] + "..." if len(content) > 100 else content
                    table.add_row(role, display.replace("\n", " "))
            _print(table)

    elif cmd == "/config":
        import json
        safe = dict(config)
        if safe.get("llm", {}).get("api_key"):
            key = safe["llm"]["api_key"]
            safe["llm"]["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        _print_json(json.dumps(safe, ensure_ascii=False, indent=2))

    elif cmd == "/model":
        if args:
            config["llm"]["model"] = args
            agent.llm.model = args
            if paw_input:
                paw_input.update_config(config)
            _write_line(f"{S.GREEN}✅ 模型已切换: {args}{S.RESET}")
        else:
            _write_line(f"当前模型: {S.CYAN}{config['llm']['model']}{S.RESET}")

    elif cmd == "/persona":
        if args:
            pname = args.strip()
            if pname in PERSONAS:
                p = get_persona(pname)
                config["agent"]["system_prompt"] = p["system_prompt"]
                config["agent"]["_persona"] = pname
                agent.system_prompt = p["system_prompt"]
                if paw_input:
                    paw_input.update_config(config)
                _write_line(f"{S.GREEN}✅ 人格已切换: {p['emoji']} {p['name']}{S.RESET} {S.DIM}- {p['description']}{S.RESET}")
            else:
                _write_line(f"{S.RED}❌ 未知人格: {pname}{S.RESET}")
                _show_personas()
        else:
            _show_personas()

    elif cmd == "/system":
        if args:
            agent.system_prompt = args
            config["agent"]["system_prompt"] = args
            if paw_input:
                paw_input.update_config(config)
            _write_line(f"{S.GREEN}✅ 系统提示已更新{S.RESET}")
            _write_line(f"{S.DIM}{args[:100]}{'...' if len(args) > 100 else ''}{S.RESET}")
        else:
            current = agent.system_prompt or "(未设置)"
            _write_line(f"{S.BOLD}当前系统提示:{S.RESET}\n{current}")
            _write_line(f"\n{S.DIM}用法: /system <新的系统提示>{S.RESET}")

    elif cmd == "/export":
        content = _export_session(agent, session_id)
        if content:
            export_dir = Path.home() / ".paw" / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"paw_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            export_path = export_dir / filename
            export_path.write_text(content, encoding="utf-8")
            _write_line(f"{S.GREEN}✅ 已导出: {export_path}{S.RESET}")
        else:
            _write_line(f"{S.YELLOW}当前会话无内容{S.RESET}")

    elif cmd == "/tools":
        from paw.core.tools import get_all_tools
        tools = get_all_tools()
        table = Table(title="可用工具", show_lines=True, border_style="cyan")
        table.add_column("工具名", style="cyan")
        table.add_column("描述")
        for t in tools:
            table.add_row(t.name, t.description)
        _print(table)

    elif cmd == "/plugins":
        from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
        if args == "init":
            from rich.prompt import Prompt
            name = Prompt.ask("插件名称", default="my_plugin")
            try:
                path = create_plugin_scaffold(name)
                _write_line(f"{S.GREEN}✅ 插件模板: {path}{S.RESET}")
            except FileExistsError:
                _write_line(f"{S.YELLOW}插件 {name} 已存在{S.RESET}")
        elif args == "reload":
            results = _load_plugins(config)
            if results:
                for n, r in results.items():
                    status = "✅" if r["tools"] and not r["errors"] else "❌"
                    _write_line(f"  {status} {n}: {r['tools']}")
            else:
                _write_line(f"{S.DIM}无插件{S.RESET}")
        else:
            plugin_files = discover_plugins()
            _write_line(f"{S.BOLD}插件目录:{S.RESET} {PLUGINS_DIR}")
            if plugin_files:
                for f in plugin_files:
                    _write_line(f"  📄 {f.name}")
            else:
                _write_line(f"{S.DIM}  (空){S.RESET}")
            _write_line(f"\n{S.DIM}/plugins init 创建模板 | /plugins reload 重载{S.RESET}")

    elif cmd == "/tokens":
        usage = agent.get_token_usage()
        _write_line(f"""
{S.BOLD_CYAN}📊 Token 用量{S.RESET}
  Prompt tokens:     {S.CYAN}{usage['prompt_tokens']}{S.RESET}
  Completion tokens: {S.CYAN}{usage['completion_tokens']}{S.RESET}
  Total tokens:      {S.BOLD_CYAN}{usage['total_tokens']}{S.RESET}
  请求次数:          {usage['requests']}
""")

    else:
        _write_line(f"{S.YELLOW}❓ 未知命令: {cmd}{S.RESET}  {S.DIM}输入 /help 查看帮助{S.RESET}")

    return True, session_id, paw_input


def _print_json(text: str):
    """打印 JSON (用 Rich)"""
    console.print_json(text)


# ========== 主聊天循环 ==========

@app.command()
def chat(
    model: str = typer.Option(None, "--model", "-m", help="指定模型"),
    session: str = typer.Option(None, "--session", "-s", help="会话 ID"),
    persona: str = typer.Option(None, "--persona", "-p", help="人格"),
    no_tokens: bool = typer.Option(False, "--no-tokens", help="不显示 token 用量"),
    no_tui: bool = typer.Option(False, "--no-tui", help="使用传统输入 (无补全)"),
):
    """开始聊天"""
    import paw.tools.builtin

    config = load_config()

    if not config["llm"].get("api_key"):
        _write_line(f"{S.RED}❌ 未配置 API Key！{S.RESET}")
        _write_line(f"请运行 {S.CYAN}paw init{S.RESET} 或编辑 {S.CYAN}{CONFIG_FILE}{S.RESET}")
        raise typer.Exit(1)

    if model:
        config["llm"]["model"] = model

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
            _write_line(f"{S.DIM}🔌 已加载 {loaded} 个插件{S.RESET}")

    from paw.core.agent import Agent
    agent = Agent(config=config, session_id=session_id)

    persona_name = config["agent"].get("_persona", "default")
    persona_info = get_persona(persona_name)
    show_tokens = config.get("agent", {}).get("show_token_usage", True) and not no_tokens

    _print_banner()
    _write_line(
        f"{S.DIM}会话: {session_id} · "
        f"模型: {config['llm']['model']} · "
        f"人格: {persona_info['emoji']} {persona_info['name']}{S.RESET}\n"
    )

    # 初始化智能输入
    paw_input = None
    use_tui = not no_tui

    if use_tui:
        try:
            from paw.tui import PawInput
            paw_input = PawInput(
                config=config,
                session_id=session_id,
                get_sessions=lambda: agent.memory.get_sessions(),
            )
        except Exception as e:
            _write_line(f"{S.YELLOW}⚠️ 智能输入初始化失败: {e}，使用传统输入{S.RESET}")
            use_tui = False

    try:
        while True:
            # ========== 获取输入 ==========
            try:
                if use_tui and paw_input:
                    user_input = paw_input.prompt()
                else:
                    _write(f"{S.BOLD_GREEN}你 › {S.RESET}")
                    user_input = input().strip()
            except KeyboardInterrupt:
                _write_line(f"\n{S.DIM}再见 👋{S.RESET}")
                break
            except EOFError:
                _write_line(f"\n{S.DIM}再见 👋{S.RESET}")
                break

            if not user_input:
                continue

            # ========== 处理命令 ==========
            if user_input.startswith("/"):
                try:
                    _, session_id, paw_input = handle_command(
                        user_input, agent, session_id, config, paw_input
                    )
                except SystemExit:
                    _write_line(f"{S.DIM}再见 👋{S.RESET}")
                    break
                continue

            # ========== AI 对话 (流式) ==========
            # 关键: 流式输出全部用 sys.stdout.write，不混用 Rich
            # 这样避免 ANSI 码冲突导致乱码

            # AI 回复前缀
            _write(f"\n{S.BOLD_CYAN}🐾{S.RESET} ")

            try:
                async def _run():
                    full_text = ""

                    async for event in agent.chat_stream(user_input):
                        if event["type"] == "token":
                            full_text += event["content"]
                            _write(event["content"])

                        elif event["type"] == "tool_start":
                            name = event["name"]
                            args = event["args"]
                            args_str = ", ".join(
                                f"{k}={repr(v)[:40]}" for k, v in args.items()
                            )
                            _write(f"\n  {S.DIM}🔧 {name}({args_str}){S.RESET}")
                            _write(f"\n{S.BOLD_CYAN}🐾{S.RESET} ")

                        elif event["type"] == "tool_result":
                            preview = event["result"][:80].replace("\n", " ")
                            _write(f"\n  {S.DIM}   ✓ {preview}{S.RESET}")
                            _write(f"\n{S.BOLD_CYAN}🐾{S.RESET} ")

                        elif event["type"] == "tool_error":
                            _write(f"\n  {S.RED}   ✗ {event['error']}{S.RESET}")
                            _write(f"\n{S.BOLD_CYAN}🐾{S.RESET} ")

                        elif event["type"] == "round":
                            _write(f"\n  {S.DIM}--- 第 {event['number']} 轮 ---{S.RESET}")
                            _write(f"\n{S.BOLD_CYAN}🐾{S.RESET} ")

                        elif event["type"] == "done":
                            break

                    return full_text

                result = asyncio.run(_run())
                _write_line()  # 换行

                # Token 用量
                if show_tokens:
                    _write_line(f"{S.DIM}{agent.get_token_summary()}{S.RESET}")

                _write_line()  # 空行分隔

            except KeyboardInterrupt:
                _write_line(f"\n{S.YELLOW}⚡ 已中断{S.RESET}\n")
            except Exception as e:
                _write_line(f"\n{S.RED}❌ 错误: {e}{S.RESET}\n")

    finally:
        asyncio.run(agent.close())


# ========== 其他命令 ==========

@app.command()
def init():
    """初始化配置（新手引导）"""
    _print_banner()
    _write_line(f"\n{S.BOLD}🐾 欢迎使用 Paw！让我们来配置一下。\n{S.RESET}")

    from rich.prompt import Prompt

    config = DEFAULT_CONFIG.copy()

    _write_line(f"{S.BOLD}1. LLM API 配置{S.RESET}")
    _write_line(f"{S.DIM}支持 OpenAI、DeepSeek、通义千问等 OpenAI 兼容 API{S.RESET}\n")

    api_key = Prompt.ask("   API Key", password=True)
    config["llm"]["api_key"] = api_key

    base_url = Prompt.ask("   API Base URL", default="https://api.openai.com/v1")
    config["llm"]["base_url"] = base_url

    model = Prompt.ask("   模型名称", default="gpt-4o-mini")
    config["llm"]["model"] = model

    _write_line(f"\n{S.BOLD}2. Agent 配置{S.RESET}")
    name = Prompt.ask("   给你的 Agent 起个名字", default="Paw")
    config["agent"]["name"] = name

    _write_line(f"\n{S.BOLD}3. 选择人格{S.RESET}")
    _show_personas()
    persona_choice = Prompt.ask("   选择人格", default="default")
    if persona_choice in PERSONAS:
        p = get_persona(persona_choice)
        config["agent"]["system_prompt"] = p["system_prompt"]
        config["agent"]["_persona"] = persona_choice
        _write_line(f"   {S.GREEN}已选择: {p['emoji']} {p['name']}{S.RESET}")

    _write_line(f"\n{S.BOLD}4. Web UI 配置{S.RESET}")
    port = Prompt.ask("   Web UI 端口", default="8765")
    config["web"]["port"] = int(port)

    save_config(config)

    from paw.plugins import PLUGINS_DIR
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    _write_line(f"\n{S.GREEN}✅ 配置已保存到 {CONFIG_FILE}{S.RESET}")
    _write_line(f"{S.GREEN}✅ 插件目录: {PLUGINS_DIR}{S.RESET}")
    _write_line(f"\n{S.BOLD}现在可以开始使用了：{S.RESET}")
    _write_line(f"  {S.CYAN}paw chat{S.RESET}              开始聊天")
    _write_line(f"  {S.CYAN}paw chat -p coder{S.RESET}     以编程专家身份聊天")
    _write_line(f"  {S.CYAN}paw web{S.RESET}               启动 Web UI")
    _write_line(f"  {S.CYAN}paw --help{S.RESET}            查看所有命令\n")


@app.command()
def web(
    host: str = typer.Option(None, "--host", "-h", help="监听地址"),
    port: int = typer.Option(None, "--port", "-p", help="监听端口"),
):
    """启动 Web UI"""
    import paw.tools.builtin

    config = load_config()

    if not config["llm"].get("api_key"):
        _write_line(f"{S.RED}❌ 未配置 API Key！请运行 paw init{S.RESET}")
        raise typer.Exit(1)

    web_host = host or config["web"].get("host", "127.0.0.1")
    web_port = port or config["web"].get("port", 8765)

    _load_plugins(config)

    _print(Panel.fit(
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
    import json
    cfg = load_config()
    safe = dict(cfg)
    if safe.get("llm", {}).get("api_key"):
        key = safe["llm"]["api_key"]
        safe["llm"]["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    _print_json(json.dumps(safe, ensure_ascii=False, indent=2))


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
    _write_line(f"{S.GREEN}✅ 已设置 {key} = {value}{S.RESET}")


@app.command()
def plugins(
    action: str = typer.Argument("list", help="操作: list / init / reload"),
):
    """管理插件"""
    from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
    import paw.tools.builtin

    if action == "init":
        from rich.prompt import Prompt
        name = Prompt.ask("插件名称", default="my_plugin")
        try:
            path = create_plugin_scaffold(name)
            _write_line(f"{S.GREEN}✅ 插件模板: {path}{S.RESET}")
        except FileExistsError:
            _write_line(f"{S.YELLOW}插件 {name} 已存在{S.RESET}")
    elif action == "reload":
        config = load_config()
        results = _load_plugins(config)
        if results:
            for name, r in results.items():
                status = "✅" if r["tools"] and not r["errors"] else "❌"
                tools_str = ", ".join(r["tools"]) if r["tools"] else "(无)"
                errors_str = f" {S.RED}{r['errors'][0]}{S.RESET}" if r["errors"] else ""
                _write_line(f"  {status} {name}: {tools_str}{errors_str}")
        else:
            _write_line(f"{S.DIM}无插件{S.RESET}")
    else:
        plugin_files = discover_plugins()
        _write_line(f"{S.BOLD}插件目录:{S.RESET} {PLUGINS_DIR}")
        if plugin_files:
            for f in plugin_files:
                _write_line(f"  📄 {f.name}")
        else:
            _write_line(f"{S.DIM}  (空){S.RESET}")
        _write_line(f"\n{S.DIM}paw plugins init  创建模板{S.RESET}")
        _write_line(f"{S.DIM}paw plugins reload  重载{S.RESET}")


@app.command()
def version():
    """显示版本"""
    _write_line(f"🐾 {__app_name__} v{__version__}")


if __name__ == "__main__":
    app()
