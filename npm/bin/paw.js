#!/usr/bin/env node
'use strict';

const { spawn } = require('child_process');
const path = require('path');
const { detectPython, detectPip, checkPawInstalled } = require('../lib/check');
const { installPaw, upgradePaw, uninstallPaw } = require('../lib/installer');

// ========== 子命令处理 ==========

const args = process.argv.slice(2);
const subcmd = args[0];

// paw-agent 自身的管理命令 (非 Python CLI 透传)
const SELF_COMMANDS = ['setup', 'upgrade', 'uninstall', 'doctor', 'help-npm'];

if (subcmd === 'setup') {
  // paw setup — 首次安装/修复环境
  handleSetup();
} else if (subcmd === 'upgrade') {
  // paw upgrade — 升级 Python 包
  handleUpgrade();
} else if (subcmd === 'uninstall') {
  // paw uninstall — 卸载 Python 包
  handleUninstall();
} else if (subcmd === 'doctor') {
  // paw doctor — 诊断环境
  handleDoctor();
} else if (subcmd === 'help-npm') {
  // paw help-npm — 显示 npm 层帮助
  handleHelpNpm();
} else {
  // 其他命令: 透传给 Python paw CLI
  delegateToPython(args);
}

// ========== 实现 ==========

function delegateToPython(args) {
  let env;
  try {
    env = detectPython();
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }

  // 检查 paw 是否已安装
  const paw = checkPawInstalled(env.python);
  if (!paw.installed) {
    console.error('❌ paw-agent Python 包未安装\n');
    console.error('请运行: paw setup');
    process.exit(1);
  }

  // 构造命令: python3 -m paw.cli <args>
  const cmdArgs = ['-m', 'paw.cli', ...args];

  const child = spawn(env.python, cmdArgs, {
    stdio: ['inherit', 'inherit', 'inherit'],
    windowsHide: false,
  });

  child.on('exit', (code) => {
    process.exit(code || 0);
  });

  child.on('error', (err) => {
    console.error(`❌ 启动失败: ${err.message}`);
    process.exit(1);
  });

  // 优雅退出: 转发信号给子进程
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(sig, () => {
      if (!child.killed) {
        child.kill(sig);
      }
    });
  }
}

function handleSetup() {
  console.log('🐾 Paw Agent 环境设置\n');

  // 1. 检测 Python
  let env;
  try {
    env = detectPython();
    console.log(`✅ Python: ${env.version} (${env.python})`);
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }

  // 2. 检测 pip
  try {
    const pip = detectPip(env.python);
    console.log(`✅ pip: 可用 (${pip.cmd})`);
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }

  // 3. 安装/升级 paw-agent
  const paw = checkPawInstalled(env.python);
  if (paw.installed) {
    console.log(`✅ paw-agent: 已安装 v${paw.version}`);
    console.log('\n如需升级: paw upgrade');
  } else {
    try {
      installPaw(env.python, { verbose: process.env.PAW_VERBOSE === '1' });
    } catch (e) {
      console.error(e.message);
      process.exit(1);
    }
  }

  console.log('🎉 设置完成！运行 paw chat 开始聊天\n');
}

function handleUpgrade() {
  let env;
  try {
    env = detectPython();
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }

  try {
    upgradePaw(env.python, { verbose: process.env.PAW_VERBOSE === '1' });
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}

function handleUninstall() {
  let env;
  try {
    env = detectPython();
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }

  try {
    uninstallPaw(env.python, { verbose: process.env.PAW_VERBOSE === '1' });
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}

function handleDoctor() {
  console.log('🐾 Paw Agent 环境诊断\n');

  // Node.js
  console.log(`Node.js:  ${process.version}`);
  console.log(`Platform: ${process.platform} ${process.arch}`);
  console.log('');

  // Python
  try {
    const env = detectPython();
    console.log(`✅ Python: ${env.version} (${env.python})`);
  } catch (e) {
    console.log('❌ Python: 未找到 >= 3.9');
    console.log(e.message);
  }

  // pip
  try {
    const env = detectPython();
    const pip = detectPip(env.python);
    console.log(`✅ pip:    可用 (${pip.cmd})`);
  } catch {
    console.log('❌ pip:    不可用');
  }

  // paw-agent
  try {
    const env = detectPython();
    const paw = checkPawInstalled(env.python);
    if (paw.installed) {
      console.log(`✅ paw:    v${paw.installed ? paw.version : '未安装'}`);
    } else {
      console.log('❌ paw:    未安装 (运行 paw setup)');
    }
  } catch {
    console.log('❌ paw:    无法检测');
  }

  console.log('\n完成 ✨');
}

function handleHelpNpm() {
  console.log(`
🐾 Paw Agent — npm 管理命令

用法: paw <command>

npm 管理命令 (本层):
  setup       首次安装/修复环境 (检测 Python + pip + 安装 paw-agent)
  upgrade     升级 paw-agent Python 包
  uninstall   卸载 paw-agent Python 包
  doctor      诊断环境问题
  help-npm    显示本帮助

其他所有命令直接透传给 Python paw CLI:
  paw chat              开始聊天
  paw chat -p coder     以编程专家身份聊天
  paw web               启动 Web UI
  paw init              初始化配置
  paw plugins list      查看插件
  paw --help            查看 Python CLI 帮助

环境变量:
  PAW_VERBOSE=1    显示详细安装输出
  PAW_PYTHON=/path/to/python3  指定 Python 路径

文档: https://github.com/mhyy10/paw-agent
`);
}
