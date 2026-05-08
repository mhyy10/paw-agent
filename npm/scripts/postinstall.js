#!/usr/bin/env node
'use strict';

/**
 * postinstall 脚本
 *
 * npm install -g paw-agent 后自动执行:
 * 1. 检测 Python >= 3.9
 * 2. 检测 pip
 * 3. 自动 pip install paw-agent
 *
 * 如果检测失败，打印安装指引但不阻断 (exit 0)
 * 用户可以之后运行 `paw setup` 手动修复
 */

const { detectPython, detectPip, checkPawInstalled } = require('../lib/check');
const { installPaw } = require('../lib/installer');

// CI 环境或 --ignore-scripts 时跳过
if (process.env.PAW_SKIP_POSTINSTALL === '1') {
  process.exit(0);
}

// 如果是 --save-dev 或本地开发安装，跳过
if (process.env.npm_config_global !== 'true' && !process.env.PAW_FORCE_POSTINSTALL) {
  console.log('ℹ️  paw-agent: 非全局安装，跳过 postinstall');
  console.log('   全局安装后会自动配置 Python 环境');
  process.exit(0);
}

console.log('\n🐾 Paw Agent — 正在配置环境...\n');

// 1. 检测 Python
let env;
try {
  env = detectPython();
  console.log(`  ✅ Python ${env.version}`);
} catch (e) {
  console.log('  ⚠️  Python >= 3.9 未找到');
  console.log('');
  console.log('  paw-agent 需要 Python 才能运行。请安装后执行:');
  console.log('    paw setup');
  console.log('');
  console.log('  安装 Python:');
  console.log('    Ubuntu/Debian: sudo apt install python3 python3-pip');
  console.log('    macOS:         brew install python3');
  console.log('    Windows:       https://www.python.org/downloads/');
  console.log('');
  // 不阻断安装
  process.exit(0);
}

// 2. 检测 pip
try {
  const pip = detectPip(env.python);
  console.log(`  ✅ pip 可用`);
} catch (e) {
  console.log('  ⚠️  pip 未找到');
  console.log('  请安装 pip 后执行: paw setup');
  process.exit(0);
}

// 3. 检查是否已安装
const paw = checkPawInstalled(env.python);
if (paw.installed) {
  console.log(`  ✅ paw-agent v${paw.version} 已安装`);
  console.log('');
  console.log('  🎉 准备就绪！运行 paw chat 开始聊天');
  console.log('');
  process.exit(0);
}

// 4. 自动安装
try {
  installPaw(env.python, { verbose: process.env.PAW_VERBOSE === '1' });
  console.log('  🎉 安装完成！运行 paw chat 开始聊天');
  console.log('');
} catch (e) {
  console.log(`  ⚠️  自动安装失败: ${e.message}`);
  console.log('  请手动执行: paw setup');
  console.log('');
  // 不阻断
  process.exit(0);
}
