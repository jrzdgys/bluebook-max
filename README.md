# 蓝宝书Max 系统规则与维护文档

> 基于2026年6月28日 v5 正式版更新，所有开发维护前请先阅读本文。

---

## 一、报告版本体系

四版全时段覆盖，版本代码、颜色、排序全部统一：

| 版本 | 代码 | 文件名 | 图标 | 标签色 | CSS类 | 排序 | 时段 |
|------|------|--------|------|--------|-------|------|------|
| 全球版 | gv | gv-YYYYMMDD.html | 🌍 | #30B46E | .gv | 0 | 每日 8:03 |
| 晨会版 | mc | mc-YYYYMMDD.html | 🌅 | #FF9500 | .mc | 1 | 交易日 7:05 |
| 午间版 | pm | pm-YYYYMMDD.html | ☀️ | #D49B00 | .pm | 2 | 交易日 11:35 |
| 晚间版 | ev | ev-YYYYMMDD.html | 🌙 | #AF52DE | .ev | 3 | 每日 20:00 |

### 统一模板：template-v3.html

**所有 mc/pm/ev 三版共用同一份模板**，仅替换 `<script id="edition-data">` 中的 JSON 数据块。模板包含所有CSS/JS，不依赖外部样式文件。

模板关键特性（v3.1 2026-06-28）：
- OG meta 标签（社交分享）
- 重合标的 A股过滤（渲染前过滤，仅显示A股）
- A股/非A股条件渲染（非A股不显示价格栏和涨跌柱）
- 品牌名+Slogan新布局

---

## 二、数据生成核心规则（v5 正式版）

### 2.1 股票分类：东方财富API判定

**禁止硬编码黑白名单。** 每只从Alpha派提取的股票名必须通过东方财富API查询判定：

```
API: https://searchadapter.eastmoney.com/api/smartbox/search
参数: keyword=股票名&type=14
判定: MktNum=0或1 → A股（生成secid）
      其他 → 非A股（isAStock=false, price=null, pct=null）
```

### 2.2 全量保留

**Alpha派"关注"段的所有条目全部保留**，包括：
- 具体股票名（A股/港股/美股）
- 概念板块/产业链描述（如"半导体设备商"、"网络安全及AI编程应用"）
- 非A股标的（如Anthropic、Cerebras、博通、微软等）

**禁止过滤任何条目**，即使它看起来像概念而非股票。

### 2.3 模糊匹配

东方财富API返回的名称可能与Alpha派提取的名称不完全一致：
- XD前缀（如"XD国博电" → "国博电子"）
- -U/-UW后缀（如"沐曦股份-U" → "沐曦股份"）
- 更名（如"力诺药包" → "力诺特玻"）

处理方式：先用精确名查询，失败则用东方财富返回的名称做前缀匹配。

### 2.4 复合名称拆分

某些条目包含多个实体（如"谷歌及国内大模型厂商如智谱"），需拆分为独立条目，各自判定。

### 2.5 Summary = 分析段落

`summary` 仅包含 Alpha派正文的分析段落，**剔除标题行和"关注："段**。`quote` 为 summary 前180字符 + `...`。

### 2.6 评分公式

```
inst = clamp(round(heat*0.55), 20, 60)
market = clamp(round(heat*0.25), 5, 25)
catalyst = clamp(round(heat*0.20), 3, 15)
total = heat (微调 inst 使 sum=heat)
```

### 2.7 重合标的：仅A股

重合标的卡片仅显示A股。模板JS在渲染前执行过滤：
```js
mt = mt.filter(function(x){ return !!ED.secidMap[x.name]; });
```
此过滤必须在 `rs.innerHTML = h` 之前执行。

---

## 三、导航页 index.html 关键规则

### 3.1 版本标签颜色

```css
.r-badge.gv, .report-card.gv { background: #30B46E15; color: #30B46E; border-color: #30B46E; }
.r-badge.mc, .report-card.mc { background: #FF950015; color: #FF9500; border-color: #FF9500; }
.r-badge.pm, .report-card.pm { background: rgba(212,155,0,.1); color: #D49B00; border-color: #D49B00; }
.r-badge.ev, .report-card.ev { background: #AF52DE15; color: #AF52DE; border-color: #AF52DE; }
```

### 3.2 关键JS

```js
var editionOrder = { gv: 0, mc: 1, pm: 2, ev: 3 };
// 注意：0 是 falsy，必须用 != null 判断
```

---

## 四、模板修改记录（v3 → v3.1）

| 修改项 | 说明 |
|--------|------|
| OG meta标签 | og:title, og:description 用于社交分享 |
| 条件涨跌柱 | `s.price!=null` 判断，非A股不渲染pct-bar |
| 条件价格栏 | `s.price!=null` 判断，非A股不渲染价格/涨跌幅列 |
| 重合标的过滤 | `mt.filter(x => !!ED.secidMap[x.name])` 渲染前过滤 |
| 过滤位置 | 必须在 `rs.innerHTML = h` 之前执行 |

---

## 五、行情数据

- 数据源：**仅东方财富API**（弃用腾讯API）
- 服务端：`push2.eastmoney.com/api/qt/ulist.np/get`
- 客户端盘中轮询：每10秒（交易时段9:30-15:00）
- 红涨绿跌：`#C4433A` / `#34C759`

---

## 六、manifest.json 规范

- `file`：仅文件名，如 `mc-20260629.html`
- `edition`：仅用 `gv/mc/pm/ev`
- `stock_count`：实际标的数量
- `total_reports`：必须与实际条目数一致
- 禁止 `-v2` 后缀

---

## 七、部署检查清单

- [ ] ED JSON 通过完整性校验（topic数、stock数、secidMap非空）
- [ ] 重合标的仅A股（页面验证）
- [ ] 非A股无价格栏（页面验证）
- [ ] manifest.json 已更新
- [ ] 代码已 push 到 main 分支
- [ ] raw.githubusercontent.com 验证文件存在
- [ ] CDN 缓存等待 2-5 分钟

---

## 八、相关文档

| 文档 | 内容 |
|------|------|
| SKILL.md (bluebook-engine) | 完整引擎架构、ED JSON数据模型、渲染逻辑 |
| template-v3.html | 统一模板文件 |
| paywall.js | 鉴权系统 |
| auth/ARCHITECTURE.md | 鉴权架构详细文档 |
