# Phase 3 - 前端增强：合同审查报告页升级

## 完成时间
2026-06-17

## 修改文件清单

### 1. `frontend/src/utils/api.js`
- **reviewContractImages**: 返回后自动补 `ai_review`/`negotiation_speech` 为 null（兼容后端未完成）
- **reviewContractText**: 同上
- **新增 getNegotiationSpeech(riskIds)**: 调用 `GET /contract/negotiation-speech?risk_ids=A01,C01`
- **default export**: 补充 `getNegotiationSpeech`

### 2. `frontend/src/views/ContractView.vue`

#### A. AI 深度审查区块
- 在合同概要下方、风险列表前展示 `result.ai_review`
- 浅蓝渐变背景卡片（`#e3f2fd → #bbdefb`）
- 显示：综合摘要 / 关键风险列表 / 整体建议
- `v-if="result.ai_review"` 保护，后端未返回时不显示

#### B. 谈判话术升级
- 每条风险卡片展开后增加「生成话术」按钮
- 点击调用 `getNegotiationSpeech([risk.id])`
- 话术结果分条展示在展开区域，每条包含：
  - 语气标签（强硬=红色/礼貌=绿色/建议=蓝色）
  - 「复制」按钮
- 新增 `riskSpeechMap` / `speechLoadingMap` 响应式状态管理
- 保留原有全局「生成谈判话术」按钮

#### C. 标准对比区块
- 在合同概要下方新增「标准对比」section
- 内嵌 19 项标准合同条款（从 `standard_contract.json` 提取）
- 对比逻辑：`result.contract_info` 逐字段对比标准值
- 每项显示：✅合规 / ⚠️不合规 / ❌未约定
- `v-if="comparisonItems.length"` 保护

### 3. 构建验证
- `npm run build` 零错误，4.20s 完成
- ContractView chunk: 33.52 KB (gzip 12.32 KB)

## 关键设计决策
1. **标准对比数据前端内嵌**：避免额外网络请求，19项直接写在组件常量中
2. **兼容性保护**：所有新字段用 `v-if` / null 兜底，后端未升级时不报错
3. **话术语气标签**：`speechTagType()` 函数根据 tone 字段映射 van-tag type（danger/success/primary）
4. **复制功能复用**：提取 `copyText()` 通用方法，话术条目和全局话术弹窗共用
