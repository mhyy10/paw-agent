"""Paw TUI - prompt_toolkit 增强的终端交互

功能:
- 智能输入框，带提示符
- Tab 自动补全: /命令、人格名、文件路径
- 命令历史 (上下箭头)
- 语法高亮 (命令着色)
- 多行输入 (Shift+Enter 换行)
- 快捷键: Ctrl+L 清屏, Esc 取消
"""

import os
import glob
from pathlib import Path
from typing import List, Optional, Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import (
    Completer, Completion, WordCompleter, PathCompleter
)
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.filters import Condition
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from paw.personas import PERSONAS, list_personas


# ========== 样式定义 ==========

PAW_STYLE = Style.from_dict({
    # 提示符 - 紫色粗箭头
    'prompt': 'bold #8b5cf6',
    'border': '#64748b',
    # 补全菜单
    'completion-menu.completion': 'bg:#1e293b #e2e8f0',
    'completion-menu.completion.current': 'bg:#0ea5e9 #ffffff bold',
    'completion-menu.meta.completion': 'bg:#1e293b #94a3b8 italic',
    'completion-menu.meta.completion.current': 'bg:#0ea5e9 #ffffff',
    'completion-menu.multi-column-meta': 'bg:#1e293b #94a3b8',
    # 输入文本
    'command': 'bold #06b6d4',          # /命令 青色
    'arg': '#f59e0b',                   # 参数 黄色
    'string': '#a78bfa',                # 字符串 紫色
    'default': '#e2e8f0',               # 默认 浅灰
    # 底部工具栏
    'bottom-toolbar': 'bg:#0f172a #94a3b8',
    'bottom-toolbar.text': 'bg:#0f172a #94a3b8',
    'bottom-toolbar.key': 'bg:#0f172a #06b6d4 bold',
})


# ========== 自动补全 ==========

class PawCompleter(Completer):
    """Paw 智能补全器"""

    def __init__(self, config: dict = None, get_sessions: Callable = None):
        self.config = config or {}
        self.get_sessions = get_sessions or (lambda: [])
        self._path_completer = PathCompleter(
            only_directories=False,
            expanduser=True,
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        if not text:
            # 空输入: 显示所有 /命令
            yield from self._command_completions(document)
            return

        # 按空格拆分，保留尾部空格信息
        stripped = text.rstrip()
        parts = stripped.split()
        has_trailing_space = text.endswith(' ') and len(text) > len(stripped)

        if text.startswith('/'):
            # 正在输入第一个词 (命令名)
            if len(parts) == 0:
                # 只输入了 "/"
                yield from self._command_completions(document)
                return

            cmd = parts[0].lower()

            # 还在输入命令名 (没有尾部空格，且只有一个词)
            if len(parts) == 1 and not has_trailing_space:
                yield from self._command_completions(document)
                return

            # 命令已完整，正在输入参数
            if cmd == '/persona':
                yield from self._persona_completions(document)
                return
            elif cmd == '/model':
                yield from self._model_completions(document)
                return
            elif cmd == '/switch':
                yield from self._session_completions(document)
                return
            # 其他命令: 不补全参数
            return

        # 非命令: 不补全
        return

    def _command_completions(self, document):
        """补全 /命令"""
        commands = [
            ('/help',    '显示帮助'),
            ('/new',     '新建会话'),
            ('/sessions','查看所有会话'),
            ('/switch',  '切换会话'),
            ('/clear',   '清空当前会话'),
            ('/history', '查看历史消息'),
            ('/export',  '导出为 Markdown'),
            ('/config',  '查看配置'),
            ('/model',   '切换模型'),
            ('/persona', '切换人格'),
            ('/system',  '修改系统提示'),
            ('/tools',   '列出可用工具'),
            ('/plugins', '管理插件'),
            ('/tokens',  '查看 Token 用量'),
            ('/quit',    '退出'),
        ]
        # 用整个输入文本做前缀匹配 (因为 / 不是 word 字符)
        text = document.text_before_cursor.strip()
        for cmd, desc in commands:
            if cmd.startswith(text) or not text:
                yield Completion(
                    cmd,
                    start_position=-len(document.get_word_before_cursor()),
                    display_meta=desc,
                )

    def _persona_completions(self, document):
        """补全人格名"""
        word = document.get_word_before_cursor()
        for key, p in PERSONAS.items():
            if key.startswith(word) or not word:
                yield Completion(
                    key,
                    start_position=-len(word),
                    display_meta=f"{p['emoji']} {p['name']} - {p['description']}",
                )

    def _model_completions(self, document):
        """补全模型名 (常用模型)"""
        word = document.get_word_before_cursor()
        models = [
            ('gpt-4o', 'OpenAI GPT-4o'),
            ('gpt-4o-mini', 'OpenAI GPT-4o Mini'),
            ('gpt-3.5-turbo', 'OpenAI GPT-3.5 Turbo'),
            ('claude-3-5-sonnet', 'Claude 3.5 Sonnet'),
            ('claude-3-haiku', 'Claude 3 Haiku'),
            ('deepseek-chat', 'DeepSeek Chat'),
            ('deepseek-coder', 'DeepSeek Coder'),
            ('qwen-turbo', '通义千问 Turbo'),
            ('qwen-plus', '通义千问 Plus'),
        ]
        # 加上当前配置的模型
        current_model = self.config.get('llm', {}).get('model', '')
        if current_model and current_model not in [m[0] for m in models]:
            models.insert(0, (current_model, '当前模型'))

        for model, desc in models:
            if model.startswith(word) or not word:
                yield Completion(
                    model,
                    start_position=-len(word),
                    display_meta=desc,
                )

    def _session_completions(self, document):
        """补全会话 ID"""
        word = document.get_word_before_cursor()
        sessions = self.get_sessions()
        for s in sessions:
            sid = s.get('session_id', '')
            title = s.get('title', '')[:30]
            if sid.startswith(word) or not word:
                yield Completion(
                    sid,
                    start_position=-len(word),
                    display_meta=title,
                )

    def _path_completions(self, document):
        """补全文件路径"""
        yield from self._path_completer.get_completions(document, None)


# ========== 输入语法高亮 ==========

class PawLexer(Lexer):
    """输入文本语法高亮"""

    def lex_document(self, document):
        lines = document.lines

        def get_line(lineno):
            line = lines[lineno] if lineno < len(lines) else ''
            tokens = []

            if line.startswith('/'):
                # 命令行: /命令 + 参数
                parts = line.split(maxsplit=1)
                tokens.append(('class:command', parts[0]))
                if len(parts) > 1:
                    tokens.append(('class:default', ' '))
                    tokens.append(('class:arg', parts[1]))
            else:
                tokens.append(('class:default', line))

            return tokens

        return get_line


# ========== 快捷键 ==========

def create_keybindings():
    """创建快捷键绑定"""
    bindings = KeyBindings()

    @bindings.add('c-l')
    def clear_screen(event):
        """Ctrl+L: 清屏"""
        event.app.renderer.clear()

    @bindings.add('escape')
    def cancel(event):
        """Esc: 清空当前输入"""
        event.app.current_buffer.text = ''

    @bindings.add('c-c')
    def ctrl_c(event):
        """Ctrl+C: 清空输入或退出"""
        buf = event.app.current_buffer
        if buf.text:
            buf.text = ''
        else:
            # 空输入时 Ctrl+C 退出
            event.app.exit(exception=KeyboardInterrupt)

    @bindings.add('c-d')
    def ctrl_d(event):
        """Ctrl+D: EOF 退出"""
        buf = event.app.current_buffer
        if not buf.text:
            event.app.exit(exception=EOFError)

    return bindings


# ========== 底部工具栏 ==========

def get_bottom_toolbar(config: dict, session_id: str):
    """生成底部工具栏"""
    model = config.get('llm', {}).get('model', 'unknown')
    persona = config.get('agent', {}).get('_persona', 'default')
    persona_info = PERSONAS.get(persona, PERSONAS['default'])

    # 不在工具栏使用 emoji，避免编码问题
    return HTML(
        f' <b>session:</b> {session_id} '
        f'| <b>model:</b> {model} '
        f'| <b>persona:</b> {persona_info["name"]} '
        f'| <b>Tab</b> complete '
        f'| <b>Ctrl+L</b> clear '
        f'| <b>Ctrl+C</b> cancel'
    )


# ========== 智能输入会话 ==========

class PawInput:
    """Paw 智能输入管理器"""

    def __init__(self, config: dict = None, session_id: str = 'default',
                 get_sessions: Callable = None):
        self.config = config or {}
        self.session_id = session_id

        # 命令历史文件
        history_dir = Path.home() / '.paw'
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / 'input_history'

        try:
            history = FileHistory(str(history_file))
        except Exception:
            history = InMemoryHistory()

        # 补全器
        completer = PawCompleter(
            config=config,
            get_sessions=get_sessions,
        )

        # 快捷键
        key_bindings = create_keybindings()

        # 创建 prompt session
        self.session = PromptSession(
            completer=completer,
            history=history,
            lexer=PawLexer(),
            style=PAW_STYLE,
            key_bindings=key_bindings,
            auto_suggest=AutoSuggestFromHistory(),
            complete_while_typing=True,
            complete_in_thread=True,
            mouse_support=False,
            multiline=False,
            wrap_lines=True,
            # 补全菜单样式
            complete_style='MULTI_COLUMN',
        )

    def prompt(self, message: str = None) -> str:
        """显示输入提示，全包围输入框。空输入时静默重试。"""
        import sys

        tl, tr, bl, br = '\u256d', '\u256e', '\u2570', '\u256f'
        h, v = '\u2500', '\u2502'
        arrow = '\u276f'  # ❯
        w = 58
        gray = "\033[38;5;245m"
        accent = "\033[1;38;5;141m"
        reset = "\033[0m"

        while True:
            # 上边框
            sys.stdout.write(f"\n{gray}  {tl}{h * w}{tr}{reset}\n")
            # 左边框 + ❯ 提示符
            sys.stdout.write(f"{gray}  {v}{reset} {accent}{arrow}{reset} ")
            sys.stdout.flush()

            try:
                result = self.session.prompt(
                    '',  # 空 message，提示符已手动打印
                    bottom_toolbar=get_bottom_toolbar(self.config, self.session_id),
                )
            except KeyboardInterrupt:
                sys.stdout.write(f"\n{gray}  {bl}{h * w}{br}{reset}\n")
                sys.stdout.flush()
                raise
            except EOFError:
                sys.stdout.write(f"\n{gray}  {bl}{h * w}{br}{reset}\n")
                sys.stdout.flush()
                raise

            result = result.strip()

            if not result:
                # 空输入: 上移擦除，静默重试
                sys.stdout.write("\033[2A\033[2K\033[1B\033[2K\r")
                sys.stdout.flush()
                continue

            # 有输入: 补右边框 + 下边框
            input_len = len(result) + 3  # "❯ " 的宽度
            pad = max(1, w - input_len)
            sys.stdout.write(f"{' ' * pad}{gray}{v}{reset}\n")
            sys.stdout.write(f"{gray}  {bl}{h * w}{br}{reset}\n")
            sys.stdout.flush()
            return result

    def update_session_id(self, session_id: str):
        self.session_id = session_id

    def update_config(self, config: dict):
        self.config = config
