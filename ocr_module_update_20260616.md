# OCR 模块创建与后端 API 更新

## 目标
为 RentBuddy 项目创建 OCR 模块和更新后端 API 路由，支持合同图片上传审查。

## 完成内容

### 1. 新建 `src/core/ocr.py` — OCR 识别模块
- `ContractOCR` 类，支持 PaddleOCR（优先）→ Tesseract（备选）自动降级
- 延迟初始化引擎，避免启动时加载
- 支持 str/bytes/PIL.Image 多种输入
- `recognize_image()` 单页识别，返回 regions/confidence/low_confidence_regions
- `recognize_images()` 多页识别，合并 full_text
- `_classify_region()` 区域分类：title/paragraph/table/signature
- `_post_process()` 合同专用纠错：高频词修正 + 数字上下文字符修正（O→0, l→1 等）
- 优雅降级：OCR 不可用时返回 error 提示

### 2. 新建 `src/core/risk_engine.py` — 结构化风险引擎
- `ContractReviewer` 类，替代原有简单规则扫描
- `review()` 返回完整报告：score/level/summary/risks/missing/contract_summary/contract_info
- 13 条风险规则（high/medium/low），7 条必备条款检查
- `_extract_contract_info()` 正则提取甲方/租金/押金/租期/地址/付款方式
- 风险评分：100 分制，80+安全 / 60-79 需谨慎 / 40-59 风险较大 / <40 危险
- `review_with_llm()` LLM 深度审查
- 兼容旧接口：返回 local_scan/risk_level 字段

### 3. 更新 `api/models.py` — 扩展响应模型
- `ContractReviewResponse` 新增字段：score, level, summary, risks, missing, contract_summary, contract_info, ocr_result
- 保留兼容旧接口字段：local_scan, ai_review, risk_level

### 4. 更新 `api/routes/contract.py` — 新增接口
- `POST /review/text` — 文本合同结构化审查
- `POST /review/upload` — 图片上传 OCR 审查（最多 9 张，单张 10MB 限制）
- 保留 `POST /review`（旧接口向后兼容）和 `POST /upload`（PDF/TXT）
- 异步函数中使用 `run_in_executor` 调用同步 OCR/审查代码
- OCR 引擎全局单例复用

### 5. 更新 `src/core/tools.py` — review_contract 工具
- `review_contract` 工具内部改为调用 `ContractReviewer`
- 返回格式化的可读文本（含评分/风险/缺失/建议）

### 6. 更新 `src/core/agent.py` — review_contract_text 方法
- 使用新的 `ContractReviewer` 替代原有简单实现
- 调用 `reviewer.review()` + `reviewer.review_with_llm()`

## 验证结果
- 所有 6 个文件编译通过
- OCR 模块初始化正常（无 PaddleOCR/Tesseract 时优雅降级）
- ContractReviewer 评分正确（测试用例：含"押金概不退还"得 60 分，1 条风险 + 4 条缺失）
- ContractReviewResponse 模型字段完整
- API 路由注册正确：5 个端点
