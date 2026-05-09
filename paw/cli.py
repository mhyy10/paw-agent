"""Paw CLI v5 - 纯 ASCII 输出，无 emoji"""

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


class S:
    """ANSI 样式 + ASCII 符号"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BOLD_CYAN = "\033[1;36m"
    BOLD_GREEN = "\033[1;32m"
    DIM_CYAN = "\033[2;36m"

    # ASCII 符号
    PAW = ">>"
    CHECK = "[OK]"
    CROSS = "[X]"
    WARN = "[!]"
    WRENCH = "[tool]"
    FOLDER = "[dir]"
    FILE = "[file]"
    CHART = "[#]"
    TRASH = "[del]"
    PLUG = "[plug]"
    ARROW = ">"


# ========== 输出函数 ==========

app = typer.Typer(
    name="paw",
    help=f"{S.PAW} Paw - 轻量级 AI 智能体框架",
    add_completion=False,
)

console = Console(force_terminal=True)


def _write(text: str):
    sys.stdout.write(text)
    sys.stdout.flush()


def _write_line(text: str = ""):
    _write(text + "\n")


def _print(text: str):
    console.print(text)


# ========== 显示函数 ==========

def _print_banner():
    _print(Panel.fit(
        f"[bold cyan]{S.PAW} {__app_name__}[/] v{__version__}\n"
        f"[dim]轻量级 AI 智能体 · Tab 补全 · Ctrl+L 清屏 · /help 帮助[/]",
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
        is_current = S.ARROW if sid == current_session_id else " "
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
        table.add_row(p["key"], "", p["name"], p["description"])
    _print(table)
    _write_line(f"{S.DIM}使用 /persona <id> 切换人格{S.RESET}")


def _export_session(agent, session_id: str) -> str:
    messages = agent.memory.get_messages(session_id, limit=200)
    if not messages:
        return ""

    lines = [f"# {S.PAW} Paw 对话记录\n"]
    lines.append(f"会话 ID: {session_id}")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    role_map = {"user": "用户", "assistant": "Paw", "tool": "工具", "system": "系统"}

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_name = msg.get("name", "")
        role_display = role_map.get(role, role)

        if role == "tool" and tool_name:
            lines.append(f"### 工具: {tool_name}\n")
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
        _write_line(f"{S.WARN}插件加载失败: {e}")
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
        _write_line(f"{S.GREEN}{S.CHECK} 新会话: {session_id}{S.RESET} {S.DIM}(旧会话 {old_id} 已保留){S.RESET}")
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
                _write_line(f"{S.GREEN}{S.CHECK} 已切换到会话 {target}{S.RESET} {S.DIM}({msg_count} 条消息){S.RESET}")
                if paw_input:
                    paw_input.update_session_id(target)
            else:
                _write_line(f"{S.RED}{S.CROSS} 会话 {target} 不存在{S.RESET}")

    elif cmd == "/clear":
        agent.memory.clear_session(session_id)
        _write_line(f"{S.YELLOW}{S.TRASH} 会话已清空{S.RESET}")

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
            _write_line(f"{S.GREEN}{S.CHECK} 模型已切换: {args}{S.RESET}")
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
                _write_line(f"{S.GREEN}{S.CHECK} 人格已切换: {p['name']}{S.RESET} {S.DIM}- {p['description']}{S.RESET}")
            else:
                _write_line(f"{S.RED}{S.CROSS} 未知人格: {pname}{S.RESET}")
                _show_personas()
        else:
            _show_personas()

    elif cmd == "/system":
        if args:
            agent.system_prompt = args
            config["agent"]["system_prompt"] = args
            if paw_input:
                paw_input.update_config(config)
            _write_line(f"{S.GREEN}{S.CHECK} 系统提示已更新{S.RESET}")
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
            _write_line(f"{S.GREEN}{S.CHECK} 已导出: {export_path}{S.RESET}")
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
                _write_line(f"{S.GREEN}{S.CHECK} 插件模板: {path}{S.RESET}")
            except FileExistsError:
                _write_line(f"{S.YELLOW}插件 {name} 已存在{S.RESET}")
        elif args == "reload":
            results = _load_plugins(config)
            if results:
                for n, r in results.items():
                    status = S.CHECK if r["tools"] and not r["errors"] else S.CROSS
                    _write_line(f"  {status} {n}: {r['tools']}")
            else:
                _write_line(f"{S.DIM}无插件{S.RESET}")
        else:
            plugin_files = discover_plugins()
            _write_line(f"{S.BOLD}插件目录:{S.RESET} {PLUGINS_DIR}")
            if plugin_files:
                for f in plugin_files:
                    _write_line(f"  {S.FILE} {f.name}")
            else:
                _write_line(f"{S.DIM}  (空){S.RESET}")
            _write_line(f"\n{S.DIM}/plugins init 创建模板 | /plugins reload 重载{S.RESET}")

    elif cmd == "/tokens":
        usage = agent.get_token_usage()
        _write_line(f"""
{S.BOLD_CYAN}{S.CHART} Token 用量{S.RESET}
  Prompt tokens:     {S.CYAN}{usage['prompt_tokens']}{S.RESET}
  Completion tokens: {S.CYAN}{usage['completion_tokens']}{S.RESET}
  Total tokens:      {S.BOLD_CYAN}{usage['total_tokens']}{S.RESET}
  请求次数:          {usage['requests']}
""")

    else:
        _write_line(f"{S.YELLOW}{S.WARN} 未知命令: {cmd}{S.RESET}  {S.DIM}输入 /help 查看帮助{S.RESET}")

    return True, session_id, paw_input


def _print_json(text: str):
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
        _write_line(f"{S.RED}{S.CROSS} 未配置 API Key！{S.RESET}")
        _write_line(f"请运行 {S.CYAN}paw init{S.RESET} 或编辑 {S.CYAN}{CONFIG_FILE}{S.RESET}")
        raise typer.Exit(1)

    if model:
        config["llm"]["model"] = model

    if persona:
        p = get_persona(persona)
        config["agent"]["system_prompt"] = p["system_prompt"]
        config["agent"]["_persona"] = persona

    session_id = session or str(uuid.uuid4())[:8]

    plugin_results = _load_plugins(config)
    if plugin_results:
        loaded = sum(1 for r in plugin_results.values() if r["tools"] and not r["errors"])
        if loaded:
            _write_line(f"{S.DIM}{S.PLUG} 已加载 {loaded} 个插件{S.RESET}")

    from paw.core.agent import Agent
    agent = Agent(config=config, session_id=session_id)

    persona_name = config["agent"].get("_persona", "default")
    persona_info = get_persona(persona_name)
    show_tokens = config.get("agent", {}).get("show_token_usage", True) and not no_tokens

    _print_banner()
    _write_line(
        f"{S.DIM}会话: {session_id} · "
        f"模型: {config['llm']['model']} · "
        f"人格: {persona_info['name']}{S.RESET}\n"
    )

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
            _write_line(f"{S.WARN}智能输入初始化失败: {e}，使用传统输入")
            use_tui = False

