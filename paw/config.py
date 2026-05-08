"""配置管理 - 单文件配置，新手友好"""

import os
import yaml
from pathlib import Path

# 默认配置目录
CONFIG_DIR = Path.home() / ".paw"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DB_FILE = CONFIG_DIR / "history.db"

DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "agent": {
        "name": "Paw",
        "system_prompt": (
            "你是 Paw，一个有用的 AI 助手。你可以帮助用户完成各种任务，"
            "包括读写文件、执行命令、搜索信息等。回答要简洁、准确、有帮助。"
        ),
        "max_tool_rounds": 10,
        "max_retries": 3,
        "show_token_usage": True,
    },
    "web": {
        "host": "127.0.0.1",
        "port": 8765,
    },
    "tools": {
        "enabled": True,
        "custom_dir": "",  # 用户自定义工具目录
        "plugins_enabled": True,  # 是否启用插件系统
    },
}


def ensure_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """加载配置，不存在则创建默认配置"""
    ensure_dir()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        # 合并默认配置（用户配置优先）
        return _deep_merge(DEFAULT_CONFIG, user_config)
    else:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置到文件"""
    ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def update_config(key_path: str, value):
    """更新单个配置项，支持点号路径如 'llm.model'"""
    config = load_config()
    keys = key_path.split(".")
    target = config
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]
    target[keys[-1]] = value
    save_config(config)
    return config


def get_config_value(key_path: str, default=None):
    """获取单个配置值"""
    config = load_config()
    keys = key_path.split(".")
    target = config
    for k in keys:
        if isinstance(target, dict) and k in target:
            target = target[k]
        else:
            return default
    return target


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
