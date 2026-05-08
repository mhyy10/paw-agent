# 🐾 Paw Agent

轻量级 AI 智能体框架 — CLI + Web UI，新手友好，开箱即用。

## ✨ 特性

- 🖥️ **双界面** — 终端 CLI + Web UI，自由切换
- 🔧 **8 个内置工具** — 文件读写、命令执行、搜索、网页抓取、Python REPL
- 🔌 **插件系统** — 放个 `.py` 文件到 `~/.paw/plugins/` 即可扩展工具
- 🎭 **6 种人格** — 通用、编程、教学、创意、分析、翻译
- 💬 **多会话管理** — 随时新建、切换、导出会话
- 📊 **Token 追踪** — 实时显示每次对话的 token 消耗
- 🔄 **自动重试** — API 调用失败自动重试，指数退避
- 📡 **真 SSE 流式** — 逐 token 实时输出
- 🔁 **多轮工具调用** — Agent 可连续多轮调用工具完成复杂任务
- 💾 **SQLite 持久化** — 对话历史本地保存，零配置
- 🌐 **REST API** — HTTP 端点，方便外部集成
- 🎨 **Markdown 渲染** — CLI 用 Rich，Web 用 marked.js + highlight.js

## 🚀 快速开始

```bash
# 安装
cd paw-agent
pip install -e .

# 初始化（交互式引导）
paw init

# 开始聊天
paw chat

# 以编程专家身份聊天
paw chat -p coder

# 启动 Web UI
paw web
```

## 📖 CLI 命令

| 命令 | 说明 |
|------|------|
| `paw init` | 初始化配置 |
| `paw chat` | 开始聊天 |
| `paw chat -m <模型>` | 指定模型 |
| `paw chat -p <人格>` | 指定人格 |
| `paw web` | 启动 Web UI |
| `paw plugins list` | 查看插件 |
| `paw plugins init` | 创建插件模板 |
| `paw config-show` | 查看配置 |
| `paw config-set <key> <value>` | 修改配置 |
| `paw version` | 版本号 |

## 💬 聊天命令

在 `paw chat` 中可用：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/new` | 新建会话 |
| `/sessions` | 查看所有会话 |
| `/switch <id>` | 切换会话 |
| `/clear` | 清空当前会话 |
| `/history` | 查看历史消息 |
| `/export` | 导出为 Markdown |
| `/model <名称>` | 切换模型 |
| `/persona <id>` | 切换人格 |
| `/system <提示>` | 修改系统提示 |
| `/tools` | 列出可用工具 |
| `/plugins` | 管理插件 |
| `/tokens` | 查看 Token 用量 |
| `/quit` | 退出 |

## 🔌 插件系统

创建自定义工具：

```bash
# 创建插件模板
paw plugins init

# 编辑 ~/.paw/plugins/my_plugin.py
# 使用 @tool 装饰器定义工具

# 重载插件
paw plugins reload
```

插件模板示例：

```python
from paw.core.tools import tool

@tool(
    name="my_tool",
    description="我的自定义工具",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "输入"}
        },
        "required": ["input"],
    },
)
def my_tool(input: str) -> dict:
    return {"result": f"处理: {input}"}
```

## 🌐 REST API

Web UI 启动后，可用以下 HTTP 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 聊天（非流式） |
| `/api/sessions` | GET | 列出会话 |
| `/api/sessions/{id}/messages` | GET | 获取会话消息 |
| `/api/sessions/{id}` | DELETE | 删除会话 |
| `/api/tools` | GET | 列出工具 |
| `/api/personas` | GET | 列出人格 |
| `/api/config` | GET | 获取配置 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger 文档 |

## 🎭 人格列表

| ID | 表情 | 名称 | 描述 |
|----|------|------|------|
| default | 🐾 | Paw | 通用助手 |
| coder | 💻 | Coder | 编程专家 |
| teacher | 📚 | Teacher | 耐心教学 |
| creative | 🎨 | Creative | 创意写作 |
| analyst | 📊 | Analyst | 数据分析 |
| translator | 🌍 | Translator | 多语言翻译 |

## ⚙️ 配置

配置文件：`~/.paw/config.yaml`

```yaml
llm:
  api_key: "your-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  max_tokens: 4096
  temperature: 0.7

agent:
  name: "Paw"
  system_prompt: "你是 Paw..."
  max_tool_rounds: 10
  max_retries: 3
  show_token_usage: true

web:
  host: "127.0.0.1"
  port: 8765

tools:
  enabled: true
  plugins_enabled: true
```

## 📁 项目结构

```
paw-agent/
├── pyproject.toml
├── README.md
├── test_selfcheck.py
└── paw/
    ├── __init__.py        # 版本号
    ├── cli.py             # CLI 界面
    ├── config.py          # 配置管理
    ├── personas.py        # 人格系统
    ├── plugins.py         # 插件系统
    ├── core/
    │   ├── agent.py       # Agent 核心
    │   ├── llm.py         # LLM 客户端 (SSE + 重试)
    │   ├── memory.py      # SQLite 记忆
    │   └── tools.py       # 工具系统
    ├── tools/
    │   └── builtin.py     # 内置工具
    └── web/
        ├── app.py         # FastAPI + WebSocket + REST
        ├── static/
        └── templates/
```

## 📋 更新日志

### v0.3.0
- 🔌 插件系统：从 `~/.paw/plugins/` 自动加载自定义工具
- 📋 多会话管理：/new、/sessions、/switch 命令
- 📊 Token 用量追踪：每次回复显示 token 消耗
- 🔄 自动重试：API 调用失败自动重试 + 指数退避
- ⚙️ /system 命令：随时修改系统提示
- 🌐 REST API：/api/chat、/api/sessions 等 HTTP 端点
- 🎨 修复终端流式输出双重打印问题

### v0.2.0
- 真 SSE 流式输出
- 多轮工具调用
- 新增 web_fetch、python_repl 工具
- Rich Markdown 渲染
- 6 种人格系统
- Web UI 增强 (marked.js + highlight.js)

### v0.1.0
- 初始版本
- CLI + Web UI
- 6 个内置工具
- SQLite 记忆

## 📄 License

MIT
