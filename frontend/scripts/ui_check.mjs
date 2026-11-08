// M2 UI 验证：playwright-core + 本机 Edge 无头。
// 覆盖：路由守卫、错误登录提示、正确登录、KPI 与 API 一致、图表渲染、
// 菜品分析四标签页、单品抽屉；fullPage 截图供人工复核。
import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const shotDir = path.resolve(__dirname, '../../.run/ui')
fs.mkdirSync(shotDir, { recursive: true })

const edgeCandidates = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
]
const executablePath = edgeCandidates.find((p) => fs.existsSync(p))
if (!executablePath) {
  console.error('[FAIL] 未找到本机 Edge')
  process.exit(1)
}

const results = []
function check(name, cond, detail = '') {
  results.push(cond)
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? `（${detail}）` : ''}`)
}

const base = 'http://127.0.0.1:5173'
const browser = await chromium.launch({ executablePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // 1. 未登录访问受保护路由 → 跳登录页
  await page.goto(`${base}/dashboard`)
  await page.waitForURL('**/login', { timeout: 10000 })
  check('路由守卫拦截未登录', page.url().endsWith('/login'))

  // 2. 错误密码 → 明确错误提示
  await page.fill('input[placeholder="admin"]', 'admin')
  await page.fill('input[placeholder="Admin@123"]', 'wrong-pass')
  await page.click('button:has-text("登录")')
  await page.waitForSelector('.el-message--error', { timeout: 10000 })
  const errText = await page.locator('.el-message--error').textContent()
  check('错误登录提示明确', errText.includes('用户名或密码错误'), errText.trim())

  // 3. 正确登录 → 经营大屏
  await page.fill('input[placeholder="Admin@123"]', 'Admin@123')
  await page.click('button:has-text("登录")')
  await page.waitForURL('**/dashboard', { timeout: 10000 })
  await page.waitForFunction(
    () => document.querySelector('[data-testid="kpi-value"]')?.textContent?.includes('¥'),
    { timeout: 20000 },
  )
  await page.waitForFunction(() => document.querySelectorAll('canvas').length >= 4, { timeout: 20000 })
  check('大屏四张图表渲染', true)

  // 4. KPI 数字与 API 一致
  const token = await page.evaluate(() => localStorage.getItem('token'))
  const resp = await page.request.get('http://127.0.0.1:8000/api/dashboard/overview', {
    headers: { Authorization: `Bearer ${token}` },
  })
  const kpis = (await resp.json()).data.kpis
  const expected = `¥${kpis.revenue.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
  const revenueText = (await page.locator('[data-testid="kpi-value"]').first().textContent()).trim()
  check('页面营收与 API 一致', revenueText === expected, `${revenueText} vs ${expected}`)
  await page.screenshot({ path: path.join(shotDir, 'dashboard.png'), fullPage: true })

  // 5. 菜品分析：组合 tab 表格 + 散点图
  await page.click('.el-menu-item:has-text("菜品分析")')
  await page.waitForSelector('.el-table__row', { timeout: 30000 })
  await page.waitForSelector('.el-loading-mask', { state: 'detached', timeout: 30000 })
  await page.waitForFunction(() => document.querySelectorAll('canvas').length >= 1, { timeout: 20000 })
  const rowCount = await page.locator('.el-tab-pane:visible .el-table__row').count()
  check('组合分析表格渲染', rowCount === 10, `每页 ${rowCount} 行`)
  await page.screenshot({ path: path.join(shotDir, 'dishes_portfolio.png'), fullPage: true })

  // 6. 单品抽屉
  await page.locator('.el-tab-pane:visible .el-table__row').first().click()
  await page.waitForSelector('.el-drawer', { timeout: 15000 })
  await page.waitForFunction(
    () => document.querySelector('.el-drawer')?.textContent?.includes('销售趋势'),
    { timeout: 15000 },
  )
  check('单品分析抽屉打开', true)
  await page.screenshot({ path: path.join(shotDir, 'dish_drawer.png'), fullPage: true })
  await page.click('.el-drawer__close-btn')

  // 7. 其余三个标签页
  for (const tab of ['浪费分析', '评价分析', '营养结构']) {
    await page.click(`.el-tabs__item:has-text("${tab}")`)
    await page.waitForTimeout(1200)
    const canvases = await page.locator('.el-tab-pane:visible canvas').count()
    check(`${tab}标签页图表渲染`, canvases >= 1, `${canvases} 张 canvas`)
  }
  await page.screenshot({ path: path.join(shotDir, 'dishes_nutrition.png'), fullPage: true })

  // 8. 预测备餐页：预置一次单菜品运行后走查渲染
  const token2 = await page.evaluate(() => localStorage.getItem('token'))
  await page.request.post('http://127.0.0.1:8000/api/forecast/runs', {
    headers: { Authorization: `Bearer ${token2}` },
    data: { dish_id: 1, horizon: 14 },
  })
  await page.click('.el-menu-item:has-text("预测备餐")')
  await page.waitForSelector('text=Holt-Winters MAE', { timeout: 60000 })
  await page.waitForSelector('.el-loading-mask', { state: 'detached', timeout: 60000 })
  await page.waitForFunction(() => document.querySelectorAll('canvas').length >= 1, { timeout: 20000 })
  const forecastHistory = await page.locator('.el-table__row').count()
  check('预测页误差对比与历史渲染', forecastHistory >= 1, `${forecastHistory} 条历史`)
  await page.screenshot({ path: path.join(shotDir, 'forecast.png'), fullPage: true })

  // 9. 菜单优化页：点击发起优化，等待结果
  await page.click('.el-menu-item:has-text("菜单优化")')
  await page.waitForSelector('text=目标权重', { timeout: 20000 })
  await page.click('button:has-text("发起菜单优化")')
  await page.waitForSelector('.el-message--success', { timeout: 120000 })
  await page.waitForSelector('.el-loading-mask', { state: 'detached', timeout: 60000 }).catch(() => {})
  await page.waitForFunction(
    () => document.querySelectorAll('.el-table__row').length >= 100,
    { timeout: 30000 },
  )
  check('优化页打分结果渲染', true)
  await page.screenshot({ path: path.join(shotDir, 'optimization.png'), fullPage: true })

  // 10. 智能助手页（规则模式会话，避免依赖外网）
  const api = async (path, method = 'get', data) => {
    const resp = await page.request[method](`http://127.0.0.1:8000${path}`, {
      headers: { Authorization: `Bearer ${token2}` },
      data,
    })
    return resp.json()
  }
  const sess = (await api('/api/agent/sessions', 'post', { mode: 'rule', title: 'UI 检查会话' })).data
  // SSE 接口返回事件流，不能按 JSON 解析
  await page.request.post(`http://127.0.0.1:8000/api/agent/sessions/${sess.id}/messages`, {
    headers: { Authorization: `Bearer ${token2}` },
    data: { content: '看看最近的经营指标' },
  })
  await page.click('.el-menu-item:has-text("智能助手")')
  await page.waitForSelector('[data-testid="agent-tool"]', { timeout: 30000 })
  await page.waitForFunction(
    () => [...document.querySelectorAll('[data-testid="agent-answer"]')].some((n) => n.textContent.includes('营收')),
    { timeout: 30000 },
  )
  check('智能助手历史与工具卡片渲染', true)
  // 页面内再发一条，验证 SSE 流式对话
  await page.fill('textarea[placeholder^="输入问题"]', '看看最近 30 天的经营指标')
  await page.click('button:has-text("发送")')
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="agent-answer"]').length >= 2,
    { timeout: 60000 },
  )
  await page.waitForTimeout(1500)
  const answers = await page.locator('[data-testid="agent-answer"]').count()
  check('对话流式发送成功', answers >= 2, `${answers} 条答复`)
  await page.waitForSelector('.el-message', { state: 'detached', timeout: 8000 }).catch(() => {})
  await page.screenshot({ path: path.join(shotDir, 'agent.png'), fullPage: true })

  // 11. 建议工单页：预置一条闭环工单后走查看板与抽屉
  const s1 = (await api('/api/suggestions', 'post',
    { type: 'menu_change', title: '看板草稿检查', content: { dish_id: 1 } })).data
  const s2 = (await api('/api/suggestions', 'post',
    { type: 'menu_change', title: '闭环检查工单', content: { dish_id: 2 } })).data
  await api(`/api/suggestions/${s2.id}/review`, 'post', { approve: true, note: '采纳' })
  await api(`/api/suggestions/${s2.id}/execute`, 'post', { note: '执行' })
  await api(`/api/suggestions/${s2.id}/evaluate`, 'post', { note: '复盘' })
  await page.click('.el-menu-item:has-text("建议工单")')
  await page.waitForSelector('text=待审批', { timeout: 20000 })
  await page.waitForSelector(`.el-card:has-text("闭环检查工单")`, { timeout: 20000 })
  check('工单看板分列渲染', true)
  await page.waitForSelector('.el-message', { state: 'detached', timeout: 8000 }).catch(() => {})
  await page.screenshot({ path: path.join(shotDir, 'suggestions.png'), fullPage: true })
  await page.click('.el-card:has-text("闭环检查工单")')
  await page.waitForSelector('text=效果归因', { timeout: 20000 })
  await page.waitForTimeout(700)
  const effectRows = await page.locator('.el-drawer .el-table__row').count()
  check('闭环工单展示效果归因', effectRows >= 4, `${effectRows} 项指标`)
  await page.screenshot({ path: path.join(shotDir, 'suggestion_detail.png'), fullPage: true })
  await page.click('.el-drawer__close-btn')

  // 12. 报告中心：点击生成周报并渲染 Markdown
  await page.click('.el-menu-item:has-text("报告中心")')
  await page.waitForSelector('text=生成周报', { timeout: 20000 })
  await page.click('button:has-text("生成周报")')
  await page.waitForSelector('[data-testid="report-content"] h1', { timeout: 60000 })
  await page.waitForSelector('.el-message', { state: 'detached', timeout: 8000 }).catch(() => {})
  const reportText = await page.locator('[data-testid="report-content"]').textContent()
  check('报告中心生成与渲染', reportText.includes('核心指标') && reportText.includes('营收'))
  await page.screenshot({ path: path.join(shotDir, 'reports.png'), fullPage: true })

  // 13. 数据管理页（只检查界面，避免误触发数据重建）
  await page.click('.el-menu-item:has-text("数据管理")')
  await page.waitForSelector('text=生成模拟经营数据', { timeout: 20000 })
  const dataPageText = await page.locator('.el-main').textContent()
  check('数据管理页渲染', dataPageText.includes('导入 CSV') && dataPageText.includes('模板'))
  await page.screenshot({ path: path.join(shotDir, 'data.png'), fullPage: true })

  // 14. 退出登录 → 回登录页
  await page.click('.el-dropdown span')
  await page.click('.el-dropdown-menu__item:has-text("退出登录")')
  await page.waitForURL('**/login', { timeout: 10000 })
  check('退出登录回登录页', page.url().endsWith('/login'))
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r).length
console.log(`\n合计 ${results.length} 项，失败 ${failed} 项；截图目录 ${shotDir}`)
process.exit(failed ? 1 : 0)