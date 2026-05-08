'use strict';

/**
 * Paw Agent npm 包基础测试
 */

const assert = require('assert');
const path = require('path');

console.log('🐾 Paw Agent npm 包测试\n');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ❌ ${name}: ${e.message}`);
  }
}

// ========== 1. 模块加载 ==========
console.log('=== 模块加载 ===');

test('check.js 可加载', () => {
  const check = require('../lib/check');
  assert(typeof check.detectPython === 'function');
  assert(typeof check.detectPip === 'function');
  assert(typeof check.checkPawInstalled === 'function');
});

test('installer.js 可加载', () => {
  const installer = require('../lib/installer');
  assert(typeof installer.installPaw === 'function');
  assert(typeof installer.upgradePaw === 'function');
  assert(typeof installer.uninstallPaw === 'function');
});

// ========== 2. 环境检测 ==========
console.log('\n=== 环境检测 ===');

test('detectPython 能找到 Python', () => {
  const { detectPython } = require('../lib/check');
  const env = detectPython();
  assert(env.python, '应返回 python 路径');
  assert(env.version, '应返回版本号');
  assert(env.major >= 3, '主版本应 >= 3');
  console.log(`    → ${env.version} (${env.python})`);
});

test('detectPip 能找到 pip', () => {
  const { detectPython, detectPip } = require('../lib/check');
  const env = detectPython();
  const pip = detectPip(env.python);
  assert(pip.cmd, '应返回 pip 命令');
  console.log(`    → ${pip.cmd} ${pip.args.join(' ')}`);
});

test('checkPawInstalled 检测已安装的 paw', () => {
  const { detectPython, checkPawInstalled } = require('../lib/check');
  const env = detectPython();
  const result = checkPawInstalled(env.python);
  // 可能已安装或未安装，只要不报错就行
  assert(typeof result.installed === 'boolean');
  console.log(`    → installed: ${result.installed}, version: ${result.version || 'N/A'}`);
});

// ========== 3. package.json 验证 ==========
console.log('\n=== package.json ===');

test('package.json 有效', () => {
  const pkg = require('../package.json');
  assert(pkg.name === 'paw-agent', 'name 应为 paw-agent');
  assert(pkg.version, '应有版本号');
  assert(pkg.bin && pkg.bin.paw, '应有 bin.paw 入口');
});

test('bin/paw.js 存在且可执行', () => {
  const fs = require('fs');
  const binPath = path.join(__dirname, '..', 'bin', 'paw.js');
  assert(fs.existsSync(binPath), 'bin/paw.js 应存在');
  const content = fs.readFileSync(binPath, 'utf8');
  assert(content.startsWith('#!/usr/bin/env node'), '应有 shebang');
});

test('scripts/postinstall.js 存在', () => {
  const fs = require('fs');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'postinstall.js');
  assert(fs.existsSync(scriptPath), 'scripts/postinstall.js 应存在');
});

// ========== 结果 ==========
console.log(`\n${'='.repeat(40)}`);
console.log(`  ✅ 通过: ${passed}  ❌ 失败: ${failed}`);
console.log(`${'='.repeat(40)}`);

if (failed > 0) {
  process.exit(1);
} else {
  console.log('  🎉 全部通过！');
}
