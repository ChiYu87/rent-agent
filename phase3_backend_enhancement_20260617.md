# Phase 3 后端增强完成报告

## 完成时间
2026-06-17

## 修改文件清单

### 1. `src/data/standard_contract.json` — 标准合同数据扩展
- 从10个条款扩展到18个条款
- 新增：房屋用途、入住查验、家具清单、钥匙交接、装修约定、押金退还条件、紧急维修、解约通知期、房东进入权
- 新增 `上限` 字段用于"是否达标"检测

### 2. `src/core/risk_engine.py` — 核心引擎增强（主要改动）
**任务1：标准合同对比增强**
- `_compare_standard()` 完全重写，从8项扩展到18项对比
- 每个对比项返回 `{field, importance, standard, actual, match: bool, suggestion}`
- 对比逻辑升级：不仅检测"缺失"，还检测"是否达标"（如押金金额 vs 标准上限、水电费商用/民用、付款方式偏苛刻等）

**任务2：AI深度审查接入主流程**
- `review()` 新增 `enable_ai_review: bool = True` 参数
- 新增 `_do_ai_review()` 方法，基于结构化信息+风险列表让LLM做深度分析
- AI审查结果结构：`{summary, key_risks, negotiation_tips}`
- 10秒超时保护，失败时返回 `"AI 审查暂不可用"`
- `enable_ai_review=False` 时跳过AI调用和LLM话术生成

**任务3：谈判话术生成**
- 新增 `_SPEECH_TEMPLATES` 类属性：12个高频风险的预置话术（A01/A02/A03/C01/C02/D01/D02/B03/G01/G02/A08/C03）
- 新增 `generate_negotiation_speech()` 方法：模板+LLM混合策略
- 新增 `_llm_generate_speech()` 方法：5秒超时，回退通用话术
- 新增 `_template_only_speech()` 方法：无LLM时仅用模板+通用话术
- 新增 `_infer_tone()` 静态方法：根据风险级别推断语气 (firm/polite)
- 每条话术结构：`{risk_id, title, speech, tone: "firm"|"polite"|"suggest"}`

### 3. `api/models.py` — API模型更新
- `ContractReviewResponse` 新增字段：
  - `ai_review: Any` — 支持str或dict类型（兼容"AI 审查暂不可用"和结构化结果）
  - `negotiation_speech: list[dict]` — 谈判话术列表
- 新增 `Any` 类型导入

### 4. `api/routes/contract.py` — API路由更新
- `/review/text` 和 `/review/upload` 调用 `reviewer.review()` 时传入 `enable_ai_review=True`
- 移除手动 `report.setdefault("ai_review", "")` 改为由review()内部生成
- 新增 `GET /contract/negotiation-speech?risk_ids=A01,C01` 路由
- 谈判话术路由支持逗号分隔的风险ID列表

### 5. `src/core/tools.py` — 工具集适配
- `review_contract()` 调用 `reviewer.review(contract_text, enable_ai_review=False)` 避免工具层触发LLM调用

### 6. `tests/test_agent.py` — 测试适配
- `test_risk_engine()` 传入 `enable_ai_review=False` 避免LLM超时
- `ai_review` 类型断言从 `str` 改为 `(str, dict)` 兼容新格式

## 测试结果
```
6 passed in 26.64s
```

## 设计决策
1. **enable_ai_review=False 时仍生成模板话术**：避免无LLM环境完全无话术可用
2. **ai_review 返回 str 或 dict**：超时/失败时返回纯字符串，成功时返回结构化dict
3. **超时保护**：AI审查10秒，LLM话术5秒，均使用 ThreadPoolExecutor + future.result(timeout=)
4. **向后兼容**：`review_with_llm()` 保留独立调用能力，旧API字段保持
