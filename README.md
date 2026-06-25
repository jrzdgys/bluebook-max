# 蓝宝书Max 系统规则与维护文档

    > 基于2026年6月25日修复汇总，所有开发维护前请先阅读本文。

    ## 一、报告版本体系

    四版全时段覆盖，版本代码、颜色、排序全部统一：

    | 版本 | 代码 | 文件名 | 图标 | 标签色 | CSS类 | 排序 | 时段 |
    |------|------|--------|------|--------|-------|------|------|
    | 全球版 | gv | gv-YYYYMMDD.html | 🌍 | #30B46E | `.gv` | 0 | 每日 8:03 |
    | 晨会版 | mc | mc-YYYYMMDD.html | 🌅 | #FF9500 | `.mc` | 1 | 交易日 7:05 |
    | 午间版 | pm | pm-YYYYMMDD.html | ☀️ | #0071E3 | `.pm` | 2 | 交易日 11:35 |
    | 晚间版 | ev | ev-YYYYMMDD.html | 🌙 | #AF52DE | `.ev` | 3 | 每日 20:00 |

    ### 两套模板

    | 模板 | 适用版本 | 特点 |
    |------|----------|------|
    | TC模板 | mc/pm/ev | 主题卡片、评分体系、阶段标签、标的分组（龙头/弹性/相关）、实时行情轮询 |
    | BB卡片模板 | gv | 简化新闻卡片、无评分、无阶段、无实时行情、纯信息展示 |

    ---

    ## 二、导航页 index.html 关键规则

    ### 2.1 版本标签颜色

    导航页中 `.r-badge` 和 `.report-card` 的 CSS 类名映射必须正确：

    ```css
    .r-badge.gv, .report-card.gv { background: #30B46E15; color: #30B46E; border-color: #30B46E; }
    .r-badge.mc, .report-card.mc { background: #FF950015; color: #FF9500; border-color: #FF9500; }
    .r-badge.pm, .report-card.pm { background: #0071E315; color: #0071E3; border-color: #0071E3; }
    .r-badge.ev, .report-card.ev { background: #AF52DE15; color: #AF52DE; border-color: #AF52DE; }
    ```

    **⚠️ 注意**：旧版用 `am`/`md`/`pm`/`global` 命名，已全量迁移至 `gv`/`mc`/`pm`/`ev`。如遇不显示颜色，检查 CSS 类名是否匹配。

    ### 2.2 JS 正则双转义

    在 `renderCard` 和历史渲染逻辑中，从日期字符串提取版本代码时，**正则表达式中的 `\d` 必须写成 `\\d`**（JSON 字符串中双反斜杠）：

    ```js
    // ✅ 正确
    var vm = (a.r.edition || '').match(/[a-z]+/)?.[0] || 'mc';
    var vd = (a.file || '').match(/(\d{8})/)?.[1] || '';

    // ❌ 错误（单反斜杠会被 JS 解析为转义）
    var vd = (a.file || '').match(/(\d{8})/)?.[1] || '';
    ```

    ### 2.3 导航页排序

    ```js
    var editionOrder = { gv: 0, mc: 1, pm: 2, ev: 3 };

    // ⚠️ JS 中 0 是 falsy，必须用 != null 判断
    // ✅ 正确: (editionOrder[a.r.edition] != null ? editionOrder[a.r.edition] : 99)
    // ❌ 错误: (editionOrder[a.r.edition] || 99) → gv的0变成99，排到最后
    ```

    ### 2.4 历史记录显示
    - 默认仅显示最近 2 天的历史报告
    - 通过「显示更多历史报告」按钮手动展开
    - 新版 `setTimeout` 移除自动展开行为（auto-expand 已禁用）
    - 同日期同版本有 `-v2` 的，优先保留 `-v2`，移除原版

    ---

    ## 三、付费墙 paywall.js 关键规则

    ### 3.1 调用方式
    ```js
    // ✅ 正确
    showLoginPaywall = function() { Paywall.showActivationModal(); };

    // ❌ 错误（不存在的函数）
    showLoginPaywall = function() { renderPaywall(); };
    ```

    ### 3.2 Canvas 指纹兼容
    ```js
    // ✅ iOS Safari 私密模式下 getCanvasHash 必须用 Promise + 超时兜底
    function getCanvasHash() {
      return new Promise(function(resolve) {
        try { /* canvas 指纹计算 */ resolve(hash); } catch(e) { resolve('fallback-' + Date.now()); }
        setTimeout(function() { resolve('fallback-timeout'); }, 3000);
      });
    }
    ```

    ### 3.3 样式注入
    付费墙样式必须通过 JS 动态注入，不能依赖外部 CSS 文件。

    ### 3.4 缓存破坏
    每次更新 `paywall.js` 后，在 `index.html` 中增加版本号强制刷新：`<script src="paywall.js?v=3"></script>`

    ---

    ## 四、报告 NaN 修复（行情数据显示）

    ### 4.1 行情 API 字段
    必须请求 **f18**（昨收盘价）字段：`fields=f2,f3,f12,f14,f18`

    ### 4.2 价格解析（盘前/停牌保护）
    ```js
    var p = parseFloat(d.price);
    if (!isNaN(p) && p !== 0) {
      spEl.textContent = p.toFixed(2);
    } else if (d.close) {
      spEl.textContent = parseFloat(d.close).toFixed(2);
    }
    ```

    ### 4.3 涨跌幅解析
    ```js
    if (d.pct != null) {
      var v = parseFloat(d.pct);
      if (!isNaN(v)) { /* 更新涨跌幅显示 */ }
    }
    ```

    ---

    ## 五、交易时段与轮询逻辑

    ### 5.1 时段判断（CST/北京时间）
    ```
    9:15 前         → 盘前，显示昨收价，不轮询
    9:15 - 9:30     → 集合竞价阶段（t >= 555 && t < 570）
    9:30 - 15:00    → 盘中交易（t >= 570 && t < 900）
    15:00 后/周末   → 盘后，停止轮询
    ```

    ### 5.2 轮询策略
    - 交易日加载时：`if(isMarketDay()){ fq(); }` — 获取一次收盘价
    - 每 30s 检查是否进入交易时段
    - 交易时段：每 10s 轮询一次实时行情
    - 非交易时段：停止轮询

    ### 5.3 动态时间
    每秒更新显示时间和行情状态。

    ---

    ## 六、管理后台 admin.html

    ### 6.1 API 端点
    | 端点 | 方法 | 用途 |
    |------|------|------|
    | `/list` | GET | 列出所有激活码 |
    | `/unbind` | POST | 解绑设备 |
    | `/codes/create` | POST | 批量生成激活码 |
    | `/codes/delete` | POST | 删除激活码 |

    ### 6.2 Worker URL
    `https://bluebook-auth.bluebookmax.workers.dev`

    ### 6.3 Admin Key
    `ADMIN_KEY = "bbmax-admin-2026"`（生产环境必须修改！）

    ### 6.4 部署方式
    修改 `auth-worker.js` 后，需手动部署到 Cloudflare Workers。

    ---

    ## 七、manifest.json 规范
    - `file`：统一使用 `reports/` 前缀
    - `edition`：仅用 `gv/mc/pm/ev`
    - 同日期同版本有 `-v2` 的，优先保留 `-v2`，移除原版
    - `total_reports` 必须与实际数量一致

    ---

    ## 八、午间版特殊规则
    - 仅包含 10 个市场热点（非 22 个主题）
    - 使用独立分区标题「市场热点」
    - 使用独立模板

    ---

    ## 九、GitHub Pages 部署检查清单
    - [ ] 代码已 push 到 `main` 分支
    - [ ] `manifest.json` 已更新
    - [ ] `index.html` 导航页已更新
    - [ ] Cloudflare Worker 已重新部署
    - [ ] CDN 缓存已等待 2-5 分钟
    - [ ] 通过 `raw.githubusercontent.com` 验证文件存在
    