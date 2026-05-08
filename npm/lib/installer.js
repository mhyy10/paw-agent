'use strict';

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const PACKAGE_NAME = 'paw-agent';
const GITHUB_REPO = 'mhyy10/paw-agent';

/**
 * 安装 paw-agent Python 包
 *
 * 策略:
 *   1. 优先尝试从 PyPI 安装 (pip install paw-agent)
 *   2. 如果 PyPI 失败，从 GitHub Release 安装 wheel
 *   3. 最后尝试从 GitHub 源码安装 (pip install git+https://...)
 *
 * @param {string} pythonCmd - Python 命令
 * @param {object} options - { verbose: bool }
 * @returns {string} 安装的版本号
 */
function installPaw(pythonCmd, options = {}) {
  const { verbose = false } = options;
  const stdio = verbose ? 'inherit' : 'pipe';

  console.log('📦 正在安装 paw-agent Python 包...\n');

  // 策略 1: PyPI
  try {
    console.log('  → 从 PyPI 安装...');
    execSync(
      `"${pythonCmd}" -m pip install --upgrade ${PACKAGE_NAME}`,
      { stdio, timeout: 120000 }
    );
    const version = _getInstalledVersion(pythonCmd);
    console.log(`  ✅ 从 PyPI 安装成功: v${version}\n`);
    return version;
  } catch (e) {
    if (verbose) console.log(`  ⚠️  PyPI 安装失败: ${e.message}\n`);
    else console.log('  ⚠️  PyPI 未找到，尝试其他方式...\n');
  }

  // 策略 2: GitHub Release wheel
  try {
    console.log('  → 从 GitHub Release 安装...');
    const wheelUrl = _getLatestWheelUrl();
    execSync(
      `"${pythonCmd}" -m pip install --upgrade "${wheelUrl}"`,
      { stdio, timeout: 120000 }
    );
    const version = _getInstalledVersion(pythonCmd);
    console.log(`  ✅ 从 GitHub Release 安装成功: v${version}\n`);
    return version;
  } catch (e) {
    if (verbose) console.log(`  ⚠️  GitHub Release 安装失败: ${e.message}\n`);
    else console.log('  ⚠️  GitHub Release 不可用，尝试源码安装...\n');
  }

  // 策略 3: 从 GitHub 源码安装
  try {
    console.log('  → 从 GitHub 源码安装...');
    execSync(
      `"${pythonCmd}" -m pip install --upgrade "git+https://github.com/${GITHUB_REPO}.git"`,
      { stdio, timeout: 180000 }
    );
    const version = _getInstalledVersion(pythonCmd);
    console.log(`  ✅ 从 GitHub 源码安装成功: v${version}\n`);
    return version;
  } catch (e) {
    throw new Error(
      '❌ 所有安装方式均失败\n\n' +
      '请手动安装:\n' +
      `  pip install ${PACKAGE_NAME}\n` +
      '  # 或\n' +
      `  pip install git+https://github.com/${GITHUB_REPO}.git\n\n` +
      `最后错误: ${e.message}`
    );
  }
}

/**
 * 升级 paw-agent
 */
function upgradePaw(pythonCmd, options = {}) {
  const { verbose = false } = options;
  const stdio = verbose ? 'inherit' : 'pipe';

  console.log('📦 正在升级 paw-agent...\n');
  try {
    execSync(
      `"${pythonCmd}" -m pip install --upgrade ${PACKAGE_NAME}`,
      { stdio, timeout: 120000 }
    );
    const version = _getInstalledVersion(pythonCmd);
    console.log(`✅ 升级完成: v${version}\n`);
    return version;
  } catch (e) {
    throw new Error(`升级失败: ${e.message}\n\n请手动执行: pip install --upgrade ${PACKAGE_NAME}`);
  }
}

/**
 * 卸载 paw-agent
 */
function uninstallPaw(pythonCmd, options = {}) {
  const { verbose = false } = options;
  const stdio = verbose ? 'inherit' : 'pipe';

  console.log('🗑️  正在卸载 paw-agent...\n');
  try {
    execSync(
      `"${pythonCmd}" -m pip uninstall ${PACKAGE_NAME} -y`,
      { stdio, timeout: 30000 }
    );
    console.log('✅ 已卸载\n');
  } catch (e) {
    throw new Error(`卸载失败: ${e.message}`);
  }
}

/**
 * 获取已安装版本
 */
function _getInstalledVersion(pythonCmd) {
  const output = execSync(
    `"${pythonCmd}" -c "import paw; print(paw.__version__)"`,
    { encoding: 'utf8', timeout: 5000, stdio: 'pipe' }
  ).trim();
  return output;
}

/**
 * 构造 GitHub Release wheel URL
 * 假设 release 命名为 vX.Y.Z，wheel 文件名标准格式
 */
function _getLatestWheelUrl() {
  // 尝试用 gh CLI 获取最新 release
  try {
    const tag = execSync(
      `gh release view --repo ${GITHUB_REPO} --json tagName -q .tagName`,
      { encoding: 'utf8', timeout: 10000, stdio: 'pipe' }
    ).trim();

    // 从 release assets 中找 wheel
    const assets = execSync(
      `gh release view "${tag}" --repo ${GITHUB_REPO} --json assets -q ".assets[].name"`,
      { encoding: 'utf8', timeout: 10000, stdio: 'pipe' }
    ).trim().split('\n');

    const wheel = assets.find(a => a.endsWith('.whl'));
    if (wheel) {
      return `https://github.com/${GITHUB_REPO}/releases/download/${tag}/${wheel}`;
    }
  } catch {
    // gh 不可用或没有 release
  }

  // fallback: 指向最新 release 的 zipball
  return `https://github.com/${GITHUB_REPO}/archive/refs/heads/main.zip`;
}

module.exports = { installPaw, upgradePaw, uninstallPaw };
