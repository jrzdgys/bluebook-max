# 蓝宝书Max

> 基于 Alpha派 蓝宝书的机构级投研情报工具。全链路自动化：数据提取 → 分类评分 → AI摘要分析 → HTML生成 → GitHub Pages部署。

---

## 一、数据架构（v3 最终版）

```
                    Alpha派 API (各版本独立)
                           │
                           ▼
              ┌─────────────────────────┐
              │  数据处理管道 (Python)   │
              │  · 分类引擎 v2.1        │
              │  · 评分引擎 v2          │
              │  · AI摘要分析生成（无...截断）│
              │  · 标的理由照抄          │
              └───────────┬─────────────┘
                          │
                          ▼
                   ED JSON 数据块
                          │
                          ▼
              ┌─────────────────────────┐
              │    HTML 模板 (冻结)      │
              │  · CSS: 5791 chars      │
              │  · JS:  5892 chars      │
              │  · 纯客户端渲染          │
              └───────────┬─────────────┘
                          │
                          ▼
                 GitHub Pages 部署
```

**核心原则：模板（CSS/JS）为基线标准，版本更新以 ED JSON 数据替换为主，JS/CSS 的修复和改进需同步记录于本文档。**

---

## 二、HTML 模板架构（冻结）

### 2.1 CSS 核心规范

| 组件 | 类名 | 说明 |
|------|------|------|
| 页面容器 | `.w` | max-width:900px, 居中 |
| 头部 | `.sh` | 深蓝渐变背景，圆角顶部 |
| 内容区 | `.ct` | 米白背景，圆角底部 |
| 市场摘要 | `.ms` | 灰色底，13px |
| 主题卡片 | `.tc` | 白底圆角卡片，hover蓝色边框 |
| 阶段标签 | `.tc-stage` | 小圆角标签，颜色由JS动态设置 |
| 热度指数 | `.tc-heat` | 20px 加粗，可点击弹出评分详情 |
| 评分弹窗 | `.hp` | position:fixed，深色背景，智能边缘检测 |
| 股票行 | `.sr` | flex布局：名称→代码→价格→涨跌幅→理由 |
| 价格 | `.sp` | 12px desktop, 11px mobile |
| 涨跌幅 | `.spp` | 与价格并列 |
| 分组标签 | `.gl.l1/.l2/.l3` | 龙头首选(橙)/弹性机会(蓝紫)/相关标的(灰) |

### 2.2 移动端适配

```css
@media (max-width: 640px) {
  .sr2 { flex-basis: 100%; white-space: normal; overflow: visible; }
  body { padding: 12px; }
  .sh { padding: 16px 18px 14px; }
  .ct { padding: 14px 16px 20px; }
}
```

---

## 三、报告版本体系

### 3.1 四版结构

| 类型 | 文件名 | 图标 | 标签色 | Alpha派来源 | 更新时段 |
|------|--------|------|--------|-------------|----------|
| mc | mc-YYYYMMDD.html | 🌅 | #FF9500 暖橙 | 国内晨会版 | 交易日 7:05 |
| pm | pm-YYYYMMDD.html | ☀️ | #0071E3 天空蓝 | 国内午间版 | 交易日 11:35 |
| ev | ev-YYYYMMDD.html | 🌙 | #AF52DE 夜紫 | 国内晚间版 | 每日 20:00 |
| gv | gv-YYYYMMDD.html | 🌍 | #30B46E 全球绿 | 全球版 | 每日 8:03 |

### 3.2 版本差异

| 特性 | 国内三版 (mc/pm/ev) | 全球版 (gv) |
|------|---------------------|-------------|
| 数据结构 | ED JSON（主题+评分+标的分组） | 简化卡片（无评分） |
| 模板 | 完整TC模板 | 简化BB卡片模板 |
| 实时行情 | ✅ EastMoney轮询 | 无行情 |
| A股代码 | ✅ secidMap | 无 |
| 分类标签 | ✅ 龙头/弹性/相关 | 无 |

---

## 四、导航页（index.html）

### 4.1 报告排序 🔒

```js
var editionOrder = { gv: 0, mc: 1, pm: 2, ev: 3 };

// ⚠️ 关键陷阱：JS 中 0 是 falsy！
// ❌ 错误写法: (editionOrder[a.r.edition] || 99)
//    → gv的0变成99，全球版排到最后！
// ✅ 正确写法: (editionOrder[a.r.edition] != null ? editionOrder[a.r.edition] : 99)
```

排序结果：**全球版🟢 → 晨会版🟠 → 午间版🔵 → 晚间版🟣**

排序应用于两处：today分组 + history分组。

### 4.2 版本标签CSS类名 🔒

| CSS类 | 底色 | 字色 | 用途 |
|-------|------|------|------|
| `.r-badge.gv` `.report-card.gv` | rgba(48,180,110,.1) | #30B46E | 全球版 |
| `.r-badge.mc` `.report-card.mc` | rgba(255,149,0,.1) | #FF9500 | 晨会版 |
| `.r-badge.pm` `.report-card.pm` | rgba(0,113,227,.1) | #0071E3 | 午间版 |
| `.r-badge.ev` `.report-card.ev` | rgba(175,82,222,.1) | #AF52DE | 晚间版 |

**严禁使用 `am/md/global` 等旧代码。仅使用 `gv/mc/pm/ev` 四个标准代码。**

### 4.3 editionLabels 映射

```js
var editionLabels = { gv: '全球版', mc: '晨会版', pm: '午间版', ev: '晚间版' };
```

### 4.4 manifest.json 规范

```json
{
  "name": "蓝宝书Max",
  "last_updated": "2026-06-24 17:53:00",
  "total_reports": 9,
  "reports": [
    {
      "file": "mc-20260624.html",
      "edition": "mc",
      "label": "晨会版",
      "date": "20260624",
      "date_display": "2026年06月24日",
      "title": "蓝宝书Max 晨会版 - 2026年06月24日",
      "stock_count": 155
    }
  ]
}
```

规则：
- `file` 使用根目录文件名（**非** `reports/` 子目录前缀）
- `edition` 仅用 `gv/mc/pm/ev` 四个标准代码
- 同一日期同一版本如有 `-v2` 版本，优先保留 `-v2`，移除原始版本
- index.html 自动按 date 分组为"今天"和"历史"

---

## 五、数据源

| 数据 | 来源 | 用途 |
|------|------|------|
| 主题/标的/理由/摘要 | Alpha派蓝宝书 | 全量数据输入 |
| 收盘价 | 腾讯 qt.gtimg.cn | 历史行情快照 |
| 实时行情 | 东方财富 push2.eastmoney.com | 盘中15s轮询 |

---

## 六、部署

- **仓库**: `jrzdgys/bluebook-max` (main分支)
- **Pages URL**: `https://jrzdgys.github.io/bluebook-max/`
- **CDN缓存**: 约2-5分钟
- **验证方法**: 先检查 `raw.githubusercontent.com/...` 确认push生效，再等CDN刷新

---

## 七、交互特性

| 特性 | 实现 |
|------|------|
| 评分弹窗 | 仅点击热度数字触发，弹窗显示三维度明细（机构关注度/市场确认度/催化强度） |
| 弹窗关闭 | 点击页面空白 / 滚动 / resize |
| 实时行情 | 盘中15s轮询，切换.up/.dn class更新颜色 |
| 交易时段标记 | Header绿点脉冲（盘中）或橙色静态（盘后） |
| 移动端 | 股票理由全宽换行，评分弹窗适配小屏 |
| 表头统计 | 全部主题 / 平均热度 / 推荐标的 三栏 |
| 市场摘要 | 多行 bullet 列表 |
| 主题排序 | 标题注明"按综合热度降序" |

---

## 八、颜色系统

### 8.1 功能颜色

| 元素 | 色值 | 说明 |
|------|------|------|
| 上涨/主升 | #C4433A | 红涨 |
| 下跌 | #34C759 | 绿跌 |
| 强化阶段 | #E67E22 | 橙色 |
| 持续阶段 | #2E86C1 | 蓝色 |
| 孵化阶段 | #7D8B8F | 灰色 |
| 龙头标签 | #FFF0E6底 #E8870A字 | 暖橙 |
| 弹性标签 | #EEF0FF底 #5E5CE6字 | 蓝紫 |
| 相关标签 | #F2F2F7底 #86868B字 | 灰色 |
| 头部渐变 | #1a1a2e -> #16213e -> #0f3460 | 深蓝 |

### 8.2 版本标签颜色

| 版本 | 图标 | 底色 | 字色 |
|------|------|------|------|
| 全球版 | 🌍 | rgba(48,180,110,.15) | #30B46E |
| 晨会版 | 🌅 | rgba(255,149,0,.15) | #FF9500 |
| 午间版 | ☀️ | rgba(0,113,227,.15) | #0071E3 |
| 晚间版 | 🌙 | rgba(175,82,222,.15) | #AF52DE |

---

## 九、已知陷阱 ⚠️

### 9.1 JS falsy `0 || 99` 排序bug
`editionOrder['gv'] = 0`，而 `0 || 99` 返回 `99`（0是falsy）。必须用 `!= null` 判断。

### 9.2 CSS类名一致性
始终使用 `gv/mc/pm/ev` 四个标准代码。严禁使用 `am/md/global` 等旧代码。index.html的CSS选择器和JS映射必须一致。

### 9.3 template.html HTML编码
模板中JS使用 `&#39;` 替代单引号，进行字符串替换时必须匹配正确编码。

### 9.4 manifest.json路径
file字段使用根目录文件名（如 `mc-20260624.html`），**不使用** `reports/` 前缀子目录。

### 9.5 manifest去重
同一日期同一版本如有 `-v2` 版本优先保留，移除原始版本。仅保留标准四版（mc/pm/ev/gv）。

### 9.6 CDN延迟
推送后需等2-5分钟，通过 `raw.githubusercontent.com` 确认push已生效。

### 9.7 外部覆盖风险
其他AI模型可能通过commit覆盖已有修复。定期检查 index.html 和 manifest.json 的edition相关代码。

---

## 十、执行检查清单

每次生成报告后必须验证：

- [ ] 各版本数据完整提取（滚动到底，确认无遗漏）
- [ ] ED JSON生成（含AI摘要/引用，无...截断）
- [ ] 行情数据写入（腾讯API收盘价 + secidMap）
- [ ] HTML文件生成（使用冻结模板，仅替换ED JSON）
- [ ] manifest.json更新（去重、根路径、正确edition代码）
- [ ] index.html验证（排序使用!=null、颜色正确、editionLabels正确）
- [ ] Git push + raw.githubusercontent.com验证
- [ ] GitHub Pages验证（等待2-5分钟CDN）

---

## 十一、自动化蓝图

### 当前状态
通过 Ally 的 `bluebook-daily-tracker` 服务实现半自动化：用户触发 → Ally 提取数据 → AI分析 → 生成HTML → 部署GitHub Pages。

### 理想状态
1. 用户登录Alpha派一次
2. Ally 一次性提取所有可用版本数据
3. 自动生成全部版本HTML + manifest + 验证
4. 一键推送部署

### 约束
- Ally 不支持定时调度（未来功能）
- Alpha派需要浏览器登录态
- 各版本发布时间不同（7:05/11:35/20:00/8:03），无法一次性获取全版

### 建议
- 每天分两次运行：收盘后运行国内三版，次日早晨运行全球版
- 每次运行前确认Alpha派登录状态有效
- 使用 `ally://services/bluebook-daily-tracker/runbook.md` 作为完整操作手册
