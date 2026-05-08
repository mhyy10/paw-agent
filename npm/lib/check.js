'use strict';

const { execSync, spawn } = require('child_process');
const os = require('os');

/**
 * 检测 Python 环境
 * 返回 { python, version, pip, platform } 或抛出错误
 */
function detectPython() {
  const candidates = _getCandidates();
  const errors = [];

  for (const cmd of candidates) {
    try {
      const version = execSync(`"${cmd}" --version 2>&1`, {
        encoding: 'utf8',
        timeout: 5000,
      }).trim();

      // 解析版本号: "Python 3.10.15" -> [3, 10, 15]
      const match = version.match(/Python (\d+)\.(\d+)\.(\d+)/);
      if (!match) {
        errors.push(`${cmd}: 无法解析版本 "${version}"`);
        continue;
      }

      const major = parseInt(match[1], 10);
      const minor = parseInt(match[2], 10);

      if (major < 3 || (major === 3 && minor < 9)) {
        errors.push(`${cmd}: 版本 ${version} 太低，需要 Python >= 3.9`);
        continue;
      }

      return {
        python: cmd,
        version: version,
        major,
        minor,
        patch: parseInt(match[3], 10),
        platform: os.platform(),
      };
    } catch {
      errors.push(`${cmd}: 未找到`);
      continue;
    }
  }

  const msg = [
    '❌ 未找到 Python >= 3.9',
    '',
    '已尝试:',
    ...errors.map(e => `  - ${e}`),
    '',
    '请安装 Python 3.9+:',
    '  Ubuntu/Debian: sudo apt install python3 python3-pip',
    '  macOS:         brew install python3',
    '  Windows:       https://www.python.org/downloads/',
  ].join('\n');

  throw new Error(msg);
}

/**
 * 检测 pip 是否可用
 */
function detectPip(pythonCmd) {
  // 先尝试 python3 -m pip
  try {
    execSync(`"${pythonCmd}" -m pip --version`, {
      encoding: 'utf8',
      timeout: 5000,
      stdio: 'pipe',
    });
    return { cmd: pythonCmd, args: ['-m', 'pip'] };
  } catch {
    // fall through
  }

  // 再尝试 pip3 / pip
  for (const pipCmd of ['pip3', 'pip']) {
    try {
      execSync(`"${pipCmd}" --version`, {
        encoding: 'utf8',
        timeout: 5000,
        stdio: 'pipe',
      });
      return { cmd: pipCmd, args: [] };
    } catch {
      continue;
    }
  }

  throw new Error(
    '❌ 未找到 pip\n\n' +
    '请安装 pip:\n' +
    '  python3 -m ensurepip --upgrade\n' +
    '  # 或\n' +
    '  sudo apt install python3-pip'
  );
}

/**
 * 检查 paw-agent 是否已安装
 */
function checkPawInstalled(pythonCmd) {
  try {
    const output = execSync(
      `"${pythonCmd}" -c "import paw; print(paw.__version__)"`,
      { encoding: 'utf8', timeout: 5000, stdio: 'pipe' }
    ).trim();
    return { installed: true, version: output };
  } catch {
    return { installed: false, version: null };
  }
}

/**
 * 获取候选 Python 命令列表
 */
function _getCandidates() {
  const platform = os.platform();

  if (platform === 'win32') {
    // Windows: 优先 py launcher
    return ['py -3', 'python3', 'python'];
  }

  // Linux / macOS
  return ['python3', 'python'];
}

module.exports = { detectPython, detectPip, checkPawInstalled };
