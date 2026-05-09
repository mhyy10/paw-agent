"""Paw CLI - 对话框风格 UI"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from paw import __version__, __app_name__
from paw.config import load_config, save_config, update_config, CONFIG_FILE, DEFAULT_CONFIG
from paw.personas import get_persona, list_personas, PERSONAS


# ===== 样式 =====
# 用一套柔和的配色: 紫蓝系 + 暖灰

class C:
    """颜色常量 - 紫蓝配色"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    # 主色调 - 紫蓝渐变
    PURPLE  = "\033[38;5;141m"   # 淡紫
    VIOLET  = "\033[38;5;99m"    # 紫罗兰
    BLUE    = "\033[38;5;75m"    # 天蓝
    CYAN    = "\033[38;5;80m"    # 青

    # 辅助色
    GREEN   = "\033[38;5;114m"   # 薄荷绿
    RED     = "\033[38;5;203m"   # 柔红
    YELLOW  = "\033[38;5;221m"   # 暖黄
    ORANGE  = "\033[38;5;215m"   # 橙

    # 中性色
    GRAY    = "\033[38;5;245m"   # 灰
    LGRAY   = "\033[38;5;250m"   # 浅灰
    WHITE   = "\033[38;5;255m"   # 白
    BG      = "\033[38;5;236m"   # 深灰背景

    # 组合
    PROMPT  = "\033[1;38;5;141m" # 粗紫 (输入提示)
    AI_TAG  = "\033[1;38;5;75m"  # 粗蓝 (AI 标签)
    ARROW   = "\033[1;38;5;141m" # 粗紫箭头


# 输出
app = typer.Typer(name="paw", help=">> Paw Agent", add_completion=False)
console = Console(force_terminal=True)

def _w(t): sys.stdout.write(t); sys.stdout.flush()
def _wl(t=""): _w(t + "\n")


# ===== 框线字符 =====

BOX = {
    "tl": "\u256d",  # ┌
    "tr": "\u256e",  # ┐
    "bl": "\u2570",  # └
    "br": "\u256f",  # ┘
    "h":  "\u2500",  # ─
    "v":  "\u2502",  # │
    "ml": "\u251c",  # ├
    "mr": "\u2524",  # ┤
}

def _box_line(left, content, right, width=60):
    """生成一行框线"""
    # 计算可见宽度 (去掉 ANSI 码)
    import re
    visible = re.sub(r'\033\[[0-9;]*m', '', content)
    pad = max(0, width - len(visible.encode('utf-8').decode('utf-8', errors='replace')) + 2)
    # 简单用空格填充
    return f"{C.GRAY}{left}{C.RESET} {content}{C.GRAY}{' ' * max(0, pad - len(visible))}{right}{C.RESET}"


# ===== 显示 =====

def _banner():
    console.print(Panel.fit(
        f"[bold purple]>>[/] [bold white]{__app_name__}[/] [dim]v{__version__}[/]\n"
        "[dim]Tab 补全 | 上下历史 | Ctrl+L 清屏 | /help 帮助[/]",
        border_style="bright_black",
    ))

def _chat_header(model, persona_name, sid):
    """聊天框头部"""
    _wl(f"{C.GRAY}{BOX['tl']}{BOX['h'] * 58}{BOX['tr']}{C.RESET}")
    _wl(f"{C.GRAY}{BOX['v']}{C.RESET} {C.DIM}Paw Agent  {C.GRAY}|  {C.LGRAY}model:{C.WHITE} {model}  {C.GRAY}|  {C.LGRAY}persona:{C.WHITE} {persona_name}  {C.GRAY}|  {C.LGRAY}session:{C.WHITE} {sid}  {C.GRAY}{BOX['v']}{C.RESET}")
    _wl(f"{C.GRAY}{BOX['ml']}{BOX['h'] * 58}{BOX['mr']}{C.RESET}")

def _help():
    _wl(f"""
{C.PURPLE}{C.BOLD}chat commands{C.RESET}
  {C.BLUE}/help{C.RESET}         show help
  {C.BLUE}/new{C.RESET}          new session
  {C.BLUE}/sessions{C.RESET}     list sessions
  {C.BLUE}/switch <id>{C.RESET}  switch session
  {C.BLUE}/clear{C.RESET}        clear session
  {C.BLUE}/history{C.RESET}      show history
  {C.BLUE}/export{C.RESET}       export as markdown

{C.PURPLE}{C.BOLD}config commands{C.RESET}
  {C.BLUE}/config{C.RESET}       show config
  {C.BLUE}/model <name>{C.RESET} switch model
  {C.BLUE}/persona <id>{C.RESET} switch persona
  {C.BLUE}/system <text>{C.RESET} set system prompt
  {C.BLUE}/tools{C.RESET}        list tools
  {C.BLUE}/plugins{C.RESET}      manage plugins
  {C.BLUE}/tokens{C.RESET}       token usage

{C.PURPLE}{C.BOLD}shortcuts{C.RESET}
  {C.GRAY}Tab complete | Up/Down history | Ctrl+L clear | Ctrl+C cancel{C.RESET}
""")

def _show_sessions(memory, cur_id):
    sessions = memory.get_sessions(limit=20)
    if not sessions:
        _wl(f"{C.DIM}  no sessions{C.RESET}")
        return
    t = Table(show_lines=False, border_style="bright_black", padding=(0,1))
    t.add_column("", width=2)
    t.add_column("id", style="cyan")
    t.add_column("title", max_width=35)
    t.add_column("persona")
    t.add_column("msgs", justify="right")
    t.add_column("last active")
    for s in sessions:
        sid = s["session_id"]
        arrow = ">" if sid == cur_id else ""
        ts = datetime.fromtimestamp(s["last_active"]).strftime("%m-%d %H:%M")
        title = (s.get("title","") or "")[:35] or "-"
        t.add_row(arrow, sid, title, s.get("persona",""), str(s["message_count"]), ts)
    console.print(t)

def _show_personas():
    t = Table(show_lines=False, border_style="bright_black", padding=(0,1))
    t.add_column("id", style="cyan")
    t.add_column("name")
    t.add_column("description")
    for p in list_personas():
        t.add_row(p["key"], p["name"], p["description"])
    console.print(t)
    _wl(f"{C.DIM}  /persona <id> to switch{C.RESET}")


# ===== 命令 =====

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
        if first: agent.memory.set_session_meta(old, title=first[:50])
        _wl(f"  {C.GREEN}>> new session: {sid}{C.RESET}  {C.DIM}(old: {old}){C.RESET}")
        if tui: tui.update_session_id(sid)
    elif cmd == "/sessions":
        _show_sessions(agent.memory, sid)
    elif cmd == "/switch":
        if not args:
            _wl(f"  {C.YELLOW}usage: /switch <id>{C.RESET}")
        else:
            target = args.strip()
            ids = [s["session_id"] for s in agent.memory.get_sessions()]
            if target in ids:
                sid = target; agent.session_id = target
                _wl(f"  {C.GREEN}>> switched: {target}{C.RESET}")
                if tui: tui.update_session_id(target)
            else:
                _wl(f"  {C.RED}>> session not found: {target}{C.RESET}")
    elif cmd == "/clear":
        agent.memory.clear_session(sid)
        _wl(f"  {C.YELLOW}>> cleared{C.RESET}")
    elif cmd == "/history":
        msgs = agent.memory.get_messages(sid, limit=50)
        if not msgs:
            _wl(f"  {C.DIM}no history{C.RESET}")
        else:
            for m in msgs:
                r = m.get("role","?")
                c = m.get("content","")
                if c:
                    tag = f"{C.BLUE}{r}{C.RESET}" if r == "user" else f"{C.PURPLE}{r}{C.RESET}"
                    preview = (c[:80]+"...") if len(c)>80 else c
                    _wl(f"  {tag}  {C.LGRAY}{preview}{C.RESET}")
    elif cmd == "/config":
        import json
        safe = dict(config)
        k = safe.get("llm",{}).get("api_key","")
        if k: safe["llm"]["api_key"] = k[:8]+"..."+k[-4:] if len(k)>12 else "***"
        console.print_json(json.dumps(safe, ensure_ascii=False, indent=2))
    elif cmd == "/model":
        if args:
            config["llm"]["model"] = args; agent.llm.model = args
            if tui: tui.update_config(config)
            _wl(f"  {C.GREEN}>> model: {args}{C.RESET}")
        else:
            _wl(f"  model: {C.CYAN}{config['llm']['model']}{C.RESET}")
    elif cmd == "/persona":
        if args:
            p = args.strip()
            if p in PERSONAS:
                info = get_persona(p)
                config["agent"]["system_prompt"] = info["system_prompt"]
                config["agent"]["_persona"] = p
                agent.system_prompt = info["system_prompt"]
                if tui: tui.update_config(config)
                _wl(f"  {C.GREEN}>> persona: {info['name']}{C.RESET}  {C.DIM}{info['description']}{C.RESET}")
            else:
                _wl(f"  {C.RED}>> unknown: {p}{C.RESET}")
                _show_personas()
        else:
            _show_personas()
    elif cmd == "/system":
        if args:
            agent.system_prompt = args; config["agent"]["system_prompt"] = args
            if tui: tui.update_config(config)
            _wl(f"  {C.GREEN}>> system prompt updated{C.RESET}")
        else:
            _wl(f"  {agent.system_prompt or '(not set)'}")
    elif cmd == "/export":
        msgs = agent.memory.get_messages(sid, limit=200)
        if msgs:
            d = Path.home()/".paw"/"exports"; d.mkdir(parents=True, exist_ok=True)
            fp = d/f"paw_{sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            lines = [f"# Paw Chat\nsession: {sid}\n---\n"]
            for m in msgs:
                r = m.get("role",""); c = m.get("content","")
                if c: lines.append(f"**{r}:** {c}\n")
            fp.write_text("\n".join(lines), encoding="utf-8")
            _wl(f"  {C.GREEN}>> exported: {fp}{C.RESET}")
        else:
            _wl(f"  {C.DIM}nothing to export{C.RESET}")
    elif cmd == "/tools":
        from paw.core.tools import get_all_tools
        t = Table(show_lines=False, border_style="bright_black")
        t.add_column("name", style="cyan"); t.add_column("description")
        for tool in get_all_tools(): t.add_row(tool.name, tool.description)
        console.print(t)
    elif cmd == "/plugins":
        from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
        if args == "init":
            from rich.prompt import Prompt
            n = Prompt.ask("name", default="my_plugin")
            try: _wl(f"  {C.GREEN}>> {create_plugin_scaffold(n)}{C.RESET}")
            except FileExistsError: _wl(f"  {C.YELLOW}already exists{C.RESET}")
        elif args == "reload":
            _load_plugins(config)
            _wl(f"  {C.GREEN}>> reloaded{C.RESET}")
        else:
            files = discover_plugins()
            _wl(f"  dir: {PLUGINS_DIR}")
            for f in files: _wl(f"    {f.name}")
            if not files: _wl(f"    (empty)")
    elif cmd == "/tokens":
        u = agent.get_token_usage()
        _wl(f"  prompt: {C.CYAN}{u['prompt_tokens']}{C.RESET}  completion: {C.CYAN}{u['completion_tokens']}{C.RESET}  total: {C.PURPLE}{u['total_tokens']}{C.RESET}  requests: {u['requests']}")
    else:
        _wl(f"  {C.YELLOW}>> unknown: {cmd}  /help{C.RESET}")
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
        _wl(f"{C.RED}>> not configured. run: paw init{C.RESET}")
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
    _chat_header(config["llm"]["model"], pi["name"], sid)
    _wl()

    tui = None
    if not no_tui:
        try:
            from paw.tui import PawInput
            tui = PawInput(config=config, session_id=sid, get_sessions=lambda: agent.memory.get_sessions())
        except Exception as e:
            _wl(f"  {C.YELLOW}tui failed: {e}, using basic input{C.RESET}")

    try:
        while True:
            # ===== 输入 =====
            try:
                if tui:
                    user_input = tui.prompt()
                else:
                    # 紫色粗箭头提示符
                    _w(f"  {C.ARROW}>{C.RESET} ")
                    user_input = input().strip()
            except (KeyboardInterrupt, EOFError):
                _wl(f"\n  {C.DIM}bye{C.RESET}")
                break
            if not user_input: continue

            # ===== 命令 =====
            if user_input.startswith("/"):
                try:
                    _, sid, tui = _cmd(user_input, agent, sid, config, tui)
                except SystemExit:
                    _wl(f"  {C.DIM}bye{C.RESET}")
                    break
                continue

            # ===== AI 回复 (流式) =====
            # 用缩进 + 蓝紫色标记 AI 输出
            _w(f"  {C.AI_TAG}>>{C.RESET} ")

            try:
                async def _run():
                    full = ""
                    async for ev in agent.chat_stream(user_input):
                        if ev["type"] == "token":
                            full += ev["content"]
                            _w(ev["content"])
                        elif ev["type"] == "tool_start":
                            a = ", ".join(f"{k}={repr(v)[:25]}" for k,v in ev["args"].items())
                            _w(f"\n    {C.GRAY}[tool] {ev['name']}({a}){C.RESET}")
                            _w(f"\n  {C.AI_TAG}>>{C.RESET} ")
                        elif ev["type"] == "tool_result":
                            _w(f"\n    {C.GRAY}[ok] {ev['result'][:50]}{C.RESET}")
                            _w(f"\n  {C.AI_TAG}>>{C.RESET} ")
                        elif ev["type"] == "tool_error":
                            _w(f"\n    {C.RED}[x] {ev['error']}{C.RESET}")
                            _w(f"\n  {C.AI_TAG}>>{C.RESET} ")
                        elif ev["type"] == "round":
                            _w(f"\n    {C.GRAY}-- round {ev['number']} --{C.RESET}")
                            _w(f"\n  {C.AI_TAG}>>{C.RESET} ")
                        elif ev["type"] == "done":
                            break
                    return full
                asyncio.run(_run())
                _wl()
                if show_tk:
                    u = agent.get_token_usage()
                    _wl(f"    {C.GRAY}tokens: {u['total_tokens']} ({u['requests']} req){C.RESET}")
                _wl()
            except KeyboardInterrupt:
                _wl(f"\n  {C.YELLOW}>> interrupted{C.RESET}\n")
            except Exception as e:
                _wl(f"\n  {C.RED}>> error: {e}{C.RESET}\n")
    finally:
        asyncio.run(agent.close())


# ===== init =====

@app.command()
def init():
    """初始化配置"""
    from rich.prompt import Prompt
    _banner()
    _wl(f"\n  {C.BOLD}Paw Setup{C.RESET}\n")
    config = DEFAULT_CONFIG.copy()
    config["llm"]["api_key"] = Prompt.ask("  API Key", password=True)
    config["llm"]["base_url"] = Prompt.ask("  Base URL", default="https://api.openai.com/v1")
    config["llm"]["model"] = Prompt.ask("  Model", default="gpt-4o-mini")
    config["agent"]["name"] = Prompt.ask("  Agent name", default="Paw")
    _show_personas()
    pc = Prompt.ask("  Persona", default="default")
    if pc in PERSONAS:
        config["agent"]["system_prompt"] = PERSONAS[pc]["system_prompt"]
        config["agent"]["_persona"] = pc
    config["web"]["port"] = int(Prompt.ask("  Web port", default="8765"))
    save_config(config)
    from paw.plugins import PLUGINS_DIR
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    _wl(f"\n  {C.GREEN}>> saved to {CONFIG_FILE}{C.RESET}")
    _wl(f"  {C.CYAN}paw chat{C.RESET}     start chatting")
    _wl(f"  {C.CYAN}paw web{C.RESET}      web ui\n")


# ===== web =====

@app.command()
def web(host: str = typer.Option(None, "--host", "-h"), port: int = typer.Option(None, "--port", "-p")):
    """启动 Web UI"""
    import paw.tools.builtin
    config = load_config()
    if not config["llm"].get("api_key"):
        _wl(f"{C.RED}>> run: paw init{C.RESET}")
        raise typer.Exit(1)
    _load_plugins(config)
    h = host or config["web"].get("host","127.0.0.1")
    p = port or config["web"].get("port",8765)
    console.print(Panel.fit(f"[bold]>> Paw Web UI[/]\nhttp://{h}:{p}\n[dim]Ctrl+C to stop[/]", border_style="bright_black"))
    from paw.web.app import create_app
    import uvicorn
    uvicorn.run(create_app(config), host=h, port=p, log_level="warning")


# ===== other commands =====

@app.command()
def config_show():
    """查看配置"""
    import json; cfg = load_config()
    k = cfg.get("llm",{}).get("api_key","")
    if k: cfg["llm"]["api_key"] = k[:8]+"..."+k[-4:] if len(k)>12 else "***"
    console.print_json(json.dumps(cfg, ensure_ascii=False, indent=2))

@app.command()
def config_set(key: str = typer.Argument(...), value: str = typer.Argument(...)):
    """修改配置"""
    if value.lower() in ("true","false"): value = value.lower()=="true"
    elif value.isdigit(): value = int(value)
    update_config(key, value)
    _wl(f"  {C.GREEN}>> {key} = {value}{C.RESET}")

@app.command()
def plugins(action: str = typer.Argument("list")):
    """管理插件"""
    from paw.plugins import PLUGINS_DIR, discover_plugins, create_plugin_scaffold
    if action == "init":
        from rich.prompt import Prompt
        n = Prompt.ask("name", default="my_plugin")
        try: _wl(f"  {C.GREEN}>> {create_plugin_scaffold(n)}{C.RESET}")
        except FileExistsError: _wl(f"  {C.YELLOW}exists{C.RESET}")
    elif action == "reload":
        _load_plugins(load_config()); _wl(f"  {C.GREEN}>> reloaded{C.RESET}")
    else:
        files = discover_plugins()
        _wl(f"  dir: {PLUGINS_DIR}")
        for f in files: _wl(f"    {f.name}")
        if not files: _wl(f"    (empty)")

@app.command()
def version():
    """显示版本"""
    _wl(f">> {__app_name__} v{__version__}")


if __name__ == "__main__":
    app()
