# 🐾 Paw Agent

轻量级 AI 智能体框架 — CLI + Web UI，插件系统，多会话管理。

## 快速安装

```bash
npm install -g paw-agent
```

安装完成后直接使用：

```bash
# 首次使用：交互式配置
paw init

# 开始聊天
paw chat

# 以编程专家身份聊天
paw chat -p coder

# 启动 Web UI
paw web
```

## 系统要求

- **Node.js** >= 14
- **Python** >= 3.9（安装时自动检测）
- **pip**（Python 包管理器）

> 安装时会自动检测 Python 环境并安装 Python 依赖。
> 如果自动安装失败，运行 `paw setup` 手动修复。

## 管理命令

```bash
paw setup       # 首次安装/修复环境
paw upgrade     # 升级到最新版
paw uninstall   # 卸载 Python 包
paw doctor      # 诊断环境问题
paw help-npm    # 显示 npm 管理帮助
```

## 功能特性

- 🖥️ **双界面** — 终端 CLI + Web UI
- 🔧 **8 个内置工具** — 文件读写、命令执行、搜索、网页抓取、Python REPL
- 🔌 **插件系统** — `~/.paw/plugins/` 放 `.py` 文件即可扩展
- 🎭 **6 种人格** — 通用、编程、教学、创意、分析、翻译
- 💬 **多会话管理** — 新建、切换、导出会话
- 📊 **Token 追踪** — 实时显示 token 消耗
- 🔄 **自动重试** — API 失败自动重试 + 指数退避
- 📡 **真 SSE 流式** — 逐 token 实时输出
- 🌐 **REST API** — HTTP 端点，方便集成

## 聊天命令

```
/help          显示帮助
/new           新建会话
/sessions      查看所有会话
/switch <id>   切换会话
/model <名称>  切换模型
/persona <id>  切换人格
/system <提示> 修改系统提示
/tools         列出工具
/plugins       管理插件
/tokens        查看 Token 用量
/export        导出为 Markdown
/quit          退出
```

## 人格列表

| ID | 人格 | 描述 |
|----|------|------|
| default | 🐾 Paw | 通用助手 |
| coder | 💻 Coder | 编程专家 |
| teacher | 📚 Teacher | 耐心教学 |
| creative | 🎨 Creative | 创意写作 |
| analyst | 📊 Analyst | 数据分析 |
| translator | 🌍 Translator | 多语言翻译 |

## 插件开发

```bash
# 创建插件模板
paw plugins init

# 编辑 ~/.paw/plugins/my_plugin.py
# 使用 @tool 装饰器定义工具

# 重载插件
paw plugins reload
```

```python
from paw.core.tools import tool

@tool(name="my_tool", description="我的工具")
def my_tool(input: str) -> dict:
    return {"result": f"处理: {input}"}
```

## 配置

配置文件：`~/.paw/config.yaml`

```yaml
llm:
  api_key: "your-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"

agent:
  name: "Paw"
  system_prompt: "你是 Paw..."
  max_retries: 3

web:
  port: 8765
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `PAW_VERBOSE=1` | 显示详细安装输出 |
| `PAW_PYTHON=/path/to/python3` | 指定 Python 路径 |
| `PAW_SKIP_POSTINSTALL=1` | 跳过 postinstall |

## 故障排除

```bash
# 诊断环境
paw doctor

# 重新设置环境
paw setup

# 手动安装 Python 包
pip install paw-agent

# 升级
paw upgrade
```

## License

MIT
