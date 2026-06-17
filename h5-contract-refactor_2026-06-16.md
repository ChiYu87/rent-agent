# H5 前端合同审查页面重构

## 任务目标
重构 RentBuddy H5 前端的合同审查页面和对话页面，适配新的后端结构化审查接口。

## 完成内容

### 1. ContractView.vue - 完全重写
- **上传区域**: `van-uploader` 组件，最多9张图片，支持拍照和相册
- **文本粘贴**: `van-field` textarea，10000字限制
- **图片审查**: 调用 `POST /api/contract/review/upload?user_id=xxx`，multipart/form-data
- **文本审查**: 调用 `POST /api/contract/review/text`，JSON body
- **评分展示**: 大号数字(64px) + SVG 圆环进度条 + 渐变背景色（绿/黄/橙/红四档）
- **风险卡片**: 可展开/收起，显示原文、分析、建议、法律依据；ID 标签颜色区分高/中风险
- **缺失条款**: `van-tag` 标签展示，点击弹窗显示建议
- **谈判话术**: 调用 `/api/tools/speech?situation=合同谈判`，`van-dialog` 弹窗展示，支持一键复制（clipboard API + fallback）
- **合同概要**: `van-cell-group` 展示房东、地址、租金、押金、租期、付款方式
- **保存报告**: 导出 JSON 文件下载

### 2. api.js - 新增两个 API 函数
- `reviewContractImages(files)`: FormData 上传多张图片到 `/contract/review/upload`
- `reviewContractText(contractText)`: JSON POST 到 `/contract/review/text`
- 已添加到 default export 对象

### 3. ChatView.vue - 快捷按钮更新
- "合同审查"按钮文字改为"帮我审查合同"
- 点击行为从 `sendQuick` 改为 `router.push('/contract')`，直接跳转合同审查页
- 新增 `useRouter` 导入和 `goContract` 方法

## 技术要点
- 全部使用 Vant 4 组件
- 移动端适配 max-width 480px
- 风险卡片展开状态用 reactive 对象管理（避免子组件注册问题）
- 字符串拼接代替模板字符串中的 emoji/特殊字符，避免编码问题
- 评分圆环用 SVG stroke-dasharray 实现动画效果

## 构建验证
`npx vite build` 成功，828ms 完成，无报错。
