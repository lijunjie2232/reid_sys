// 把 web/src/i18n/locales/*.js 导出成 reid_sys/locales/*.json（扁平化 + 点号 key）。
//
// 为什么要这一步：HF Space 的 Gradio 前端（app.py）需要同一套文案。与其在 Python 里
// 手抄一遍（必然漂移），不如把 React 的字典当作唯一真相来源，导出给后端读。
// 改文案只改 .js，然后重跑本脚本：
//
//   node scripts/export_locales.mjs
//
// 顺带校验项目约定：三语 key 必须严格对齐，不一致直接非零退出。

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SRC = resolve(ROOT, 'web/src/i18n/locales')
const OUT = resolve(ROOT, 'reid_sys/locales')
const LOCALES = ['zh-TW', 'en-US', 'ja-JP']

mkdirSync(OUT, { recursive: true })

const keysets = []
for (const loc of LOCALES) {
  const { default: messages } = await import(pathToFileURL(resolve(SRC, `${loc}.js`)).href)
  const flat = {}
  const walk = (node, prefix) => {
    for (const [k, v] of Object.entries(node)) {
      const key = prefix ? `${prefix}.${k}` : k
      if (v && typeof v === 'object') walk(v, key)
      else flat[key] = v
    }
  }
  walk(messages, '')
  keysets.push(new Set(Object.keys(flat)))
  writeFileSync(resolve(OUT, `${loc}.json`), JSON.stringify(flat, null, 1) + '\n')
  console.log(`${loc}: ${Object.keys(flat).length} keys -> reid_sys/locales/${loc}.json`)
}

const [first, ...others] = keysets
for (const s of others) {
  const missing = [...first].filter((k) => !s.has(k))
  const extra = [...s].filter((k) => !first.has(k))
  if (missing.length || extra.length) {
    console.error('三语 key 不对齐：', { missing, extra })
    process.exit(1)
  }
}
console.log('三语 key 对齐 OK')
