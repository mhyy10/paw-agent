"""Paw CLI - 纯 ASCII 输出，无 emoji"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from paw import __version__, __app_name__
from paw.config import load_config, save_config, update_config, CONFIG_FILE, DEFAULT_CONFIG
from paw.personas import get_persona, list_personas, PERSONAS


# ANSI 样式
class S:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BOLD_CYAN = "\033[1;36m"
    BOLD_GREEN = "\033[1;32m"


# 输出
app = typer.Typer(name="paw", help=">> Paw - 轻量级 AI 智能体框架", add_completion=False)
console = Console(force_terminal=True)

def _w(text: str):
    sys.stdout.write(text)
    sys.stdout.flush()

def _wl(text: str = ""):
    _w(text + "\n")


# ===== 显示 =====

def _banner():
    console.print(Panel.fit(
        f"[bold cyan]>> {__app_name__}[/] v{__version__}\n"
        "[dim]轻量级 AI 智能体 - Tab 补全 - /help 帮助[/]",
        border_style="cyan",
    ))

def _help():
    _wl(f"""
{S.BOLD_CYAN}聊天命令:{S.RESET}
  {S.CYAN}/help{S.RESET}         显示帮助
  {S.CYAN}/new{S.RESET}          新建会话
  {S.CYAN}/sessions{S.RESET}     查看/切换会话
  {S.CYAN}/switch <id>{S.RESET}  切换会话
  {S.CYAN}/clear{S.RESET}        清空当前会话
  {S.CYAN}/history{S.RESET}      查看历史消息
  {S.CYAN}/export{S.RESET}       导出为 Markdown

{S.BOLD_CYAN}配置命令:{S.RESET}
  {S.CYAN}/config{S.RESET}       查看配置
  {S.CYAN}/model <名称>{S.RESET} 切换模型
  {S.CYAN}/persona <id>{S.RESET} 切换人格
  {S.CYAN}/system <提示>{S.RESET} 修改系统提示
  {S.CYAN}/tools{S.RESET}        列出工具
  {S.CYAN}/plugins{S.RESET}      管理插件
  {S.CYAN}/tokens{S.RESET}       Token 用量

{S.BOLD_CYAN}快捷键:{S.RESET}
  Tab 补全 | 上下历史 | Ctrl+L 清屏 | Ctrl+C 中断
""")

def _show_sessions(memory, cur_id):
    sessions = memory.get_sessions(limit=20)
    if not sessions:
        _wl(f"{S.DIM}暂无历史会话{S.RESET}")
        return
    t = Table(title="会话列表", show_lines=True, border_style="cyan")
    t.add_column("", width=3)
    t.add_column("ID", style="cyan")
    t.add_column("标题", max_width=40)
    t.add_column("人格")
    t.add_column("消息", justify="right")
    t.add_column("最后活跃")
    for s in sessions:
        sid = s["session_id"]
        arrow = ">" if sid == cur_id else " "
        ts = datetime.fromtimestamp(s["last_active"]).strftime("%m-%d %H:%M")
        title = s.get("title", "") or "(无标题)"
        t.add_row(arrow, sid, title, s.get("persona", ""), str(s["message_count"]), ts)
    console.print(t)

def _show_personas():
    t = Table(title="可用人格", show_lines=True, border_style="cyan")
    t.add_column("ID", style="cyan")
    t.add_column("名称")
    t.add_column("描述")
    for p in list_personas():
        t.add_row(p["key"], p["name"], p["description"])
    console.print(t)
    _wl(f"{S.DIM}/persona <id> 切换{S.RESET}")


# ===== 命令处理 =====

def _cmd(line, agent, sid, config, tui):
    parts = line.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        raise SystemExit(0)
    elif cmd == "/help":
        _help()
    elif cmd == "/new":
        old = sid
        sid = str(uuid.uuid4())[:8]
        agent.session_id = sid
        first = agent.memory.get_last_user_message(old)
        if first:
            agent.memory.set_session_meta(old, title=first[:50])
        _wl(f"{S.GREEN}[OK] 新会话: {sid}{S.RESET} {S.DIM}(旧: {old}){S.RESET}")
        if tui: tui.update_session_id(sid)
    elif cmd == "/sessions":
        _show_sessions(agent.memory, sid)
    elif cmd == "/switch":
        if not args:
            _wl(f"{S.YELLOW}用法: /switch <id>{S.RESET}")
        else:
            target = args.strip()
            ids = [s["session_id"] for s in agent.memory.get_sessions()]
            if target in ids:
                sid = target
                agent.session_id = target
                _wl(f"{S.GREEN}[OK] 已切换: {target}{S.RESET}")
                if tui: tui.update_session_id(target)
            else:
                _wl(f"{S.RED}[X] 会话 {target} 不存在{S.RESET}")
    elif cmd == "/clear":
        agent.memory.clear_session(sid)
        _wl(f"{S.YELLOW}[del] 已清空{S.RESET}")
    elif cmd == "/history":
        msgs = agent.memory.get_messages(sid, limit=50)
        if not msgs:
            _wl(f"{S.DIM}无历史消息{S.RESET}")
        else:
            t = Table(title=f"会话 {sid}", show_lines=False)
            t.add_column("角色", style="cyan", width=10)
            t.add_column("内容", max_width=70)
            for m in msgs:
                c = m.get("content", "")
                if c:
                    t.add_row(m.get("role", "?"), (c[:100]+"...") if len(c)>100 else c)
            console.print(t)
    elif cmd == "/config":
        import json
        safe = dict(config)
        k = safe.get("llm",{}).get("api_key","")
        if k: safe["llm"]["api_key"] = k[:8]+"..."+k[-4:] if len(k)>12 else "***"
        console.print_json(json.dumps(safe, ensure_ascii=False, indent=2))
    elif cmd == "/model":
        if args:
            config["llm"]["model"] = args
            agent.llm.model = args
            if tui: tui.update_config(config)
            _wl(f"{S.GREEN}[OK] 模型: {args}{S.RESET}")
        else:
            _wl(f"模型: {S.CYAN}{config['llm']['model']}{S.RESET}")
    elif cmd == "/persona":
        if args:
            p = args.strip()
            if p in PERSONAS:
                info = get_persona(p)
                config["agent"]["system_prompt"] = info["system_prompt"]
                config["agent"]["_persona"] = p
                agent.system_prompt = info["system_prompt"]
                if tui: tui.update_config(config)
                _wl(f"{S.GREEN}[OK] 人格: {info['name']} - {info['description']}{S.RESET}")
            else:
                _wl(f"{S.RED}[X] 未知: {p}{S.RESET}")
                _show_personas()
        else:
            _show_personas()
    elif cmd == "/system":
        if args:
            agent.system_prompt = args
            config["agent"]["system_prompt"] = args
            if tui: tui.update_config(config)
            _wl(f"{S.GREEN}[OK] 系统提示已更新{S.RESET}")
        else:
            _wl(f"系统提示:\n{agent.system_prompt or '(未设置)'}")
    elif cmd == "/export":
        msgs = agent.memory.get_messages(sid, limit=200)
        if msgs:
            d = Path.home()/".paw"/"exports"
            d.mkdir(parents=True, exist_ok=True)
            f = d/f"paw_{sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            lines = [f"# Paw 对话记录\n会话: {sid}\n---\n"]
            for m in msgs:
                r = m.get("role","")
                c = m.get("content","")
                if c: lines.append(f"**{r}:** {c}\n")
            f.write_text("\n".join(lines), encoding="utf-8")
            _wl(f"{S.GREEN}[OK] 导出: {f}{S.RESET}")
        else:
            _wl(f"{S.YELLOW}无内容{S.RESET}")
    elif cmd == "/tools":
        from paw.core.tools import get_all_tools
        t = Table(title="工具", show_lines=True, border_style="cyan")
        t.add_column("名称", style="cyan")
        t.add_column("描述")
        for tool in get_all_tools():
            t.add_row(tool.name, tool.description)
        console.print(t)
    elif cmd == "/plugins":
        from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
        if args == "init":
            from rich.prompt import Prompt
            n = Prompt.ask("名称", default="my_plugin")
            try:
                p = create_plugin_scaffold(n)
                _wl(f"{S.GREEN}[OK] 模板: {p}{S.RESET}")
            except FileExistsError:
                _wl(f"{S.YELLOW}已存在{S.RESET}")
        elif args == "reload":
            _load_plugins(config)
            _wl(f"{S.GREEN}[OK] 重载完成{S.RESET}")
        else:
            files = discover_plugins()
            _wl(f"插件目录: {PLUGINS_DIR}")
            for f in files: _wl(f"  {f.name}")
            if not files: _wl(f"  (空)")
    elif cmd == "/tokens":
        u = agent.get_token_usage()
        _wl(f"\n  Prompt: {u['prompt_tokens']}  Completion: {u['completion_tokens']}  Total: {u['total_tokens']}  Requests: {u['requests']}\n")
    else:
        _wl(f"{S.YELLOW}[!] 未知: {cmd}  /help 帮助{S.RESET}")
    return True, sid, tui


def _load_plugins(config):
    if not config.get("tools",{}).get("plugins_enabled",True): return {}
    try:
        from paw.plugins import load_plugins
        return load_plugins()
    except: return {}


# ===== chat =====

@app.command()
def chat(
    model: str = typer.Option(None, "--model", "-m"),
    session: str = typer.Option(None, "--session", "-s"),
    persona: str = typer.Option(None, "--persona", "-p"),
    no_tokens: bool = typer.Option(False, "--no-tokens"),
    no_tui: bool = typer.Option(False, "--no-tui"),
):
    """开始聊天"""
    import paw.tools.builtin
    config = load_config()
    if not config["llm"].get("api_key"):
        _wl(f"{S.RED}[X] 未配置 API Key! paw init{S.RESET}")
        raise typer.Exit(1)
    if model: config["llm"]["model"] = model
    if persona:
        p = get_persona(persona)
        config["agent"]["system_prompt"] = p["system_prompt"]
        config["agent"]["_persona"] = persona
    sid = session or str(uuid.uuid4())[:8]
    _load_plugins(config)
    from paw.core.agent import Agent
    agent = Agent(config=config, session_id=sid)
    pn = config["agent"].get("_persona", "default")
    pi = get_persona(pn)
    show_tk = config.get("agent",{}).get("show_token_usage",True) and not no_tokens
    _banner()
    _wl(f"{S.DIM}会话: {sid} | 模型: {config['llm']['model']} | 人格: {pi['name']}{S.RESET}\n")

    tui = None
    if not no_tui:
        try:
            from paw.tui import PawInput
            tui = PawInput(config=config, session_id=sid, get_sessions=lambda: agent.memory.get_sessions())
        except Exception as e:
            _wl(f"{S.YELLOW}[!] TUI 失败: {e}{S.RESET}")

    try:
        while True:
            try:
                if tui:
                    user_input = tui.prompt()
                else:
                    _w(f"{S.BOLD_GREEN}you > {S.RESET}")
                    user_input = input().strip()
            except (KeyboardInterrupt, EOFError):
                _wl("\nbye")
                break
            if not user_input: continue

            if user_input.startswith("/"):
                try:
                    _, sid, tui = _cmd(user_input, agent, sid, config, tui)
                except SystemExit:
                    _wl("bye")
                    break
                continue

            _w(f"\n{S.BOLD_CYAN}>>{S.RESET} ")
            try:
                async def _run():
                    ft = ""
                    async for ev in agent.chat_stream(user_input):
                        if ev["type"] == "token":
                            ft += ev["content"]
                            _w(ev["content"])
                        elif ev["type"] == "tool_start":
                            a = ", ".join(f"{k}={repr(v)[:30]}" for k,v in ev["args"].items())
                            _w(f"\n  [tool] {ev['name']}({a})")
                            _w(f"\n{S.BOLD_CYAN}>>{S.RESET} ")
                        elif ev["type"] == "tool_result":
                            _w(f"\n  [OK] {ev['result'][:60]}")
                            _w(f"\n{S.BOLD_CYAN}>>{S.RESET} ")
                        elif ev["type"] == "tool_error":
                            _w(f"\n  [X] {ev['error']}")
                            _w(f"\n{S.BOLD_CYAN}>>{S.RESET} ")
                        elif ev["type"] == "round":
                            _w(f"\n  -- round {ev['number']} --")
                            _w(f"\n{S.BOLD_CYAN}>>{S.RESET} ")
                        elif ev["type"] == "done":
                            break
                    return ft
                asyncio.run(_run())
                _wl()
                if show_tk: _wl(f"{S.DIM}{agent.get_token_summary()}{S.RESET}")
                _wl()
            except KeyboardInterrupt:
                _wl(f"\n{S.YELLOW}interrupted{S.RESET}\n")
            except Exception as e:
                _wl(f"\n{S.RED}[X] {e}{S.RESET}\n")
    finally:
        asyncio.run(agent.close())


# ===== init =====

@app.command()
def init():
    """初始化配置"""
    from rich.prompt import Prompt
    _banner()
    _wl(f"\n{S.BOLD}>> Paw 初始化{S.RESET}\n")
    config = DEFAULT_CONFIG.copy()
    config["llm"]["api_key"] = Prompt.ask("  API Key", password=True)
    config["llm"]["base_url"] = Prompt.ask("  Base URL", default="https://api.openai.com/v1")
    config["llm"]["model"] = Prompt.ask("  模型", default="gpt-4o-mini")
    config["agent"]["name"] = Prompt.ask("  Agent 名称", default="Paw")
    _show_personas()
    pc = Prompt.ask("  人格", default="default")
    if pc in PERSONAS:
        config["agent"]["system_prompt"] = PERSONAS[pc]["system_prompt"]
        config["agent"]["_persona"] = pc
    config["web"]["port"] = int(Prompt.ask("  Web 端口", default="8765"))
    save_config(config)
    from paw.plugins import PLUGINS_DIR
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    _wl(f"\n{S.GREEN}[OK] 配置已保存: {CONFIG_FILE}{S.RESET}")
    _wl(f"  paw chat     开始聊天")
    _wl(f"  paw web      Web UI")
    _wl(f"  paw --help   帮助\n")


# ===== web =====

@app.command()
def web(host: str = typer.Option(None, "--host", "-h"), port: int = typer.Option(None, "--port", "-p")):
    """启动 Web UI"""
    import paw.tools.builtin
    config = load_config()
    if not config["llm"].get("api_key"):
        _wl(f"{S.RED}[X] paw init{S.RESET}")
        raise typer.Exit(1)
    _load_plugins(config)
    h = host or config["web"].get("host","127.0.0.1")
    p = port or config["web"].get("port",8765)
    console.print(Panel.fit(f"[bold cyan]>> Paw Web UI[/]\nhttp://{h}:{p}\n[dim]Ctrl+C 停止[/]", border_style="cyan"))
    from paw.web.app import create_app
    import uvicorn
    uvicorn.run(create_app(config), host=h, port=p, log_level="warning")


# ===== 其他命令 =====

@app.command()
def config_show():
    """查看配置"""
    import json
    cfg = load_config()
    k = cfg.get("llm",{}).get("api_key","")
    if k: cfg["llm"]["api_key"] = k[:8]+"..."+k[-4:] if len(k)>12 else "***"
    console.print_json(json.dumps(cfg, ensure_ascii=False, indent=2))

@app.command()
def config_set(key: str = typer.Argument(...), value: str = typer.Argument(...)):
    """修改配置"""
    if value.lower() in ("true","false"): value = value.lower()=="true"
    elif value.isdigit(): value = int(value)
    update_config(key, value)
    _wl(f"{S.GREEN}[OK] {key} = {value}{S.RESET}")

@app.command()
def plugins(action: str = typer.Argument("list")):
    """管理插件"""
    from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
    if action == "init":
        from rich.prompt import Prompt
        n = Prompt.ask("名称", default="my_plugin")
        try: _wl(f"{S.GREEN}[OK] {create_plugin_scaffold(n)}{S.RESET}")
        except FileExistsError: _wl(f"{S.YELLOW}已存在{S.RESET}")
    elif action == "reload":
        _load_plugins(load_config())
        _wl(f"{S.GREEN}[OK] 重载完成{S.RESET}")
    else:
        files = discover_plugins()
        _wl(f"目录: {PLUGINS_DIR}")
        for f in files: _wl(f"  {f.name}")
        if not files: _wl(f"  (空)")

@app.command()
def version():
    """显示版本"""
    _wl(f">> {__app_name__} v{__version__}")


if __name__ == "__main__":
    app()
