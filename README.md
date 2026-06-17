# 🏠 RentBuddy — AI-Powered Rental Assistant

<p align="center">
  <strong>降低信息差 · 标准化流程 · 风险预警</strong><br>
  <strong>Bridging the information gap · Standardizing the process · Risk early warning</strong>
</p>

---

RentBuddy 是一个面向租房新手的 AI 助手，覆盖找房→看房→签约→入住全流程。基于自研 ReAct Agent 引擎 + 本地 LLM，数据不出本机，零隐私泄露。

RentBuddy is an AI assistant for rental beginners, covering the entire process from searching → viewing → signing → moving in. Built on a custom ReAct Agent engine + local LLM, your data never leaves your machine — zero privacy leaks.

## ✨ 功能亮点 / Features

| 模块 Module | 功能 Description |
|---|---|
| 🔍 智能找房助手 Smart Search | 需求诊断、房源初筛、通勤估算 / Need diagnosis, listing screening, commute estimation |
| ✅ 看房清单 Viewing Checklist | 分阶段检查项（看房前/中/后）、可勾选保存 / Phased checklists (before/during/after), checkable & savable |
| 📋 合同风控 Contract Review | OCR拍照→结构化提取→三层风险扫描→智能评分→谈判话术 / OCR→structured extraction→3-layer risk scan→smart scoring→negotiation scripts |
| 💰 费用计算器 Cost Calculator | 真实成本计算、押金退还不模拟 / True cost calculation, deposit refund simulation |
| 🛡️ 维权与黑名单 Rights & Blacklist | 入住交接指引、黑中介/黑房东查询与上报 / Move-in guide, blacklist query & reporting |
| 🗣️ 谈判话术 Speech Generator | 针对合同谈判、砍价等场景生成应对话术 / Generate negotiation scripts for contracts, bargaining, etc. |

### 差异化亮点 / What Makes It Different

- **自研 ReAct Agent 引擎** — 不依赖 LangChain，工具调用逻辑透明可控
  **Custom ReAct Agent engine** — No LangChain dependency; transparent & controllable tool-calling logic
- **本地 LLM + 本地 Embedding** — 数据不出本机，隐私零风险
  **Local LLM + local embedding** — Data stays on your machine, zero privacy risk
- **9 个专业工具** — 费用计算、押金模拟、合同审查、黑名单、看房清单、城市政策、通勤估算、话术生成
  **9 specialized tools** — Cost calc, deposit sim, contract review, blacklist, checklist, city rules, commute, speech
- **双端界面** — H5 移动端 (Vue 3 + Vant 4) + 桌面端 (tkinter)
  **Dual interfaces** — H5 mobile (Vue 3 + Vant 4) + Desktop (tkinter)
- **FastAPI 服务** — 开箱即用的 REST API + SSE 流式输出
  **FastAPI service** — Ready-to-use REST API + SSE streaming
- **多用户隔离** — user_id 粒度数据隔离，天然支持多用户场景
  **Multi-user isolation** — Per-user data isolation, naturally multi-tenant

## 📋 签约场景详解 / Contract Signing Deep Dive

签约是整个租房流程中信息最不对称、风险最集中的环节。RentBuddy 用 **四阶段流水线** 把一份合同从「拍张照片」变成「可执行的谈判方案」：

Signing is the most asymmetric & risk-concentrated step in renting. RentBuddy turns a contract from "a photo" to "an actionable negotiation plan" via a **4-stage pipeline**:

### Stage 1: OCR 识别 / OCR Recognition

```
拍照/上传合同图片
       ↓
PaddleOCR（优先）→ Tesseract（降级）→ 纯文本回退
       ↓
合同高频词纠错表 + 段落结构恢复
       ↓
输出：cleaned_text（可直接送入解析器）
```

- **自动降级**：PaddleOCR → Tesseract → 返回安装提示，不报错
- **纠错表**：37 个合同高频词映射（"用方"→"甲方" 等），修复 OCR 典型识别错误
- **支持格式**：图片（jpg/png）、PDF、纯文本

### Stage 2: 结构化提取 / Structured Extraction

```
cleaned_text
       ↓
ContractParser（规则引擎 + LLM 双引擎）
       ↓ 38 个正则模式 + LLM 补充提取
25+ 字段结构化输出
```

**提取字段一览：**

| 类别 Category | 字段 Fields |
|---|---|
| **当事人** | 房东姓名、租客姓名、身份证号（自动脱敏）、联系电话 |
| **房屋** | 地址、面积、房型 |
| **财务** | 月租金、押金、中介费、物业费、付款周期、付款日期、水电责任、其他费用 |
| **期限** | 起止日期、租期月数 |
| **条款** | 违约金、提前退租、转租、维修责任、续租、装修约定、入住查验、房东进入权 等 13 项 |

- **金额正则** 覆盖 5 种写法：`¥3500` / `3500元` / `人民币3500元` / `三千五百` / `3,500.00`
- **LLM 补充提取**（默认关闭，需手动开启）：对正则未命中的字段做 LLM 二次提取，5 秒超时保护

### Stage 3: 三层风险扫描 + 智能评分 / 3-Layer Risk Scan + Smart Scoring

```
结构化字段
       ↓
┌─────────────────────────────────────┐
│ Layer 1: 规则引擎 (80+ 条规则)        │
│   费用类15条 + 期限类10条 + 违约类12条  │
│   + 权利类8条 + 信息类5条              │
├─────────────────────────────────────┤
│ Layer 2: 标准合同对比 (18项条款)       │
│   逐项标注 match/missing/partial     │
├─────────────────────────────────────┤
│ Layer 3: AI 深度审查 (可选)            │
│   LLM 逐条审查，10秒超时保护           │
└─────────────────────────────────────┘
       ↓
非线性评分算法 → 0~100 分 + risk/warning/safe 等级
```

**评分算法（非线性衰减，避免低分陷阱）：**

| 风险等级 | 单项扣分 | 该类上限 |
|---|---|---|
| High | 6 分 | 35 分 |
| Medium | 2 分 | 25 分 |
| Low | 1 分 | 15 分 |
| 条款缺失 | 2 分/项 | 25 分 |

> 样本合同测试：24 个风险点（5 high + 15 medium + 4 low）→ 评分 **68/100**（之前线性算法仅 0 分）

**规则引擎示例：**

| 规则 ID | 等级 | 规则描述 | 法律依据 |
|---|---|---|---|
| A01 | 🔴 High | 押金超过3个月租金 | 《民法典》第四百七十条 |
| B03 | 🔴 High | 自动续租陷阱 | 《民法典》第七百三十四条 |
| C01 | 🔴 High | 提前退租押金全扣 | 《民法典》第五百八十五条 |
| D06 | 🟡 Medium | 无入住查验记录 | 入住查验是退租争议关键证据 |
| E02 | 🟢 Low | 付款日期约定模糊 | 付款期限不明确可能导致争议 |

### Stage 4: 谈判话术生成 / Negotiation Script Generation

```
风险点列表
       ↓
┌──────────────────────────────────┐
│ 12 个预置话术模板（0 延迟）         │
│  + LLM 混合生成（按需触发）         │
└──────────────────────────────────┘
       ↓
每个风险点 → 1 条谈判话术（含引用原文 + 建议 + 法律依据）
```

- **模板话术**：覆盖押金过高、违约金不对等、自动续租、房东随意进入等高频场景
- **LLM 话术**：对模板未覆盖的风险点，由 LLM 生成个性化话术（独立 API 按需调用）
- **前端一键展开**：点击风险卡片即可查看对应谈判话术

### 端到端流程 / End-to-End Flow

```
用户拍照上传 ──→ OCR识别 ──→ 结构化提取(25+字段) ──→ 规则扫描(80+条)
                                                          ↓
                                                    标准对比(18项)
                                                          ↓
                                                  AI深度审查(可选)
                                                          ↓
                                                非线性评分(0~100)
                                                          ↓
                                              谈判话术(12模板+LLM)
                                                          ↓
                                               前端可视化展示
```

**API 架构策略：**

| 端点 | AI 审查 | 耗时 | 说明 |
|---|---|---|---|
| `POST /api/contract/review` | 默认关闭 | <1s | 快速审查，规则引擎+标准对比+评分 |
| `GET /api/contract/ai-review` | 开启 | ~12s | AI 深度审查，超时优雅回退 |
| `GET /api/contract/negotiation-speech` | 模板 | <1s | 谈判话术（LLM话术独立触发） |

---

## 🛠️ 技术栈 / Tech Stack

| 层 Layer | 技术 Technology |
|---|---|
| **LLM** | Ollama (deepseek-r1 / qwen2.5 / llama3) — 自动检测可用模型 |
| **Embedding** | Ollama (all-minilm / nomic-embed-text) — 自动适配 API 版本 |
| **Agent** | 自研 ReAct 框架 — 工具调用 + 推理链 + 记忆检索 |
| **后端 Backend** | Python 3.10+ / FastAPI / SQLite3 |
| **前端 Frontend** | Vue 3 + Vant 4 + Vue Router (H5) / tkinter (Desktop) |
| **部署 Deploy** | Docker / Docker Compose |

## 🚀 快速开始 / Quick Start

### 前置条件 / Prerequisites

- [Ollama](https://ollama.ai) 已安装并运行
- Python 3.10+
- Node.js 18+（仅 H5 前端需要）

### 1. 安装 Ollama 模型 / Install Ollama Models

```bash
# LLM（任选其一，程序自动检测 / pick one, auto-detected）
ollama pull deepseek-r1:1.5b
ollama pull qwen2.5

# Embedding（任选其一 / pick one）
ollama pull all-minilm
ollama pull nomic-embed-text
```

### 2. 安装 Python 依赖 / Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. 启动 / Start

**方式一：H5 移动端（推荐）/ H5 Mobile (Recommended)**

```bash
# 构建前端 / Build frontend
cd frontend && npm install && npm run build && cd ..

# 启动服务（前端 + API 同端口）/ Start server (frontend + API on same port)
python main.py --api

# 浏览器打开 / Open in browser
# http://localhost:8000
```

**方式二：桌面端 / Desktop GUI**

```bash
python main.py
```

**方式三：仅 API 服务 / API Only**

```bash
python main.py --api --port 8000

# API 文档 / API docs
# http://localhost:8000/docs
```

**方式四：开发模式 / Dev Mode**

```bash
# 终端1：后端 / Terminal 1: backend
python main.py --api

# 终端2：前端热更新 / Terminal 2: frontend hot-reload
cd frontend && npm run dev
# http://localhost:3000 (自动代理 API 到 8000 / auto-proxy API to 8000)
```

### 4. Docker 部署 / Docker Deployment

```bash
docker-compose up -d

# 访问 / Visit
# http://localhost:8000
```

## 📁 项目结构 / Project Structure

```
rent-agent/
├── main.py                          # 启动入口 / Entry point
├── requirements.txt                 # Python 依赖 / Python deps
├── Dockerfile                       # Docker 镜像 / Docker image
├── docker-compose.yml               # Docker 编排 / Docker compose
├── LICENSE                          # MIT
│
├── api/                             # FastAPI 服务 / FastAPI service
│   ├── app.py                       #   应用入口 + 前端静态文件服务 / App entry + static file serving
│   ├── models.py                    #   请求/响应模型 / Request/Response models
│   └── routes/
│       ├── chat.py                  #   对话（含 SSE 流式）/ Chat (with SSE streaming)
│       ├── contract.py              #   合同审查 / Contract review
│       └── tools.py                 #   工具接口 / Tool endpoints
│
├── frontend/                        # Vue 3 H5 前端 / Vue 3 H5 frontend
│   ├── vite.config.js               #   Vite 配置 + Vant 自动导入 / Vite config + Vant auto-import
│   ├── index.html                   #   移动端 viewport / Mobile viewport
│   └── src/
│       ├── App.vue                  #   Tabbar 底部导航 / Bottom tab navigation
│       ├── main.js                  #   入口 / Entry
│       ├── router/index.js          #   路由 / Routes
│       ├── utils/api.js             #   API 客户端 (SSE + REST) / API client
│       └── views/
│           ├── ChatView.vue         #   对话页 / Chat page
│           ├── ChecklistView.vue    #   看房清单页 / Checklist page
│           ├── ContractView.vue     #   合同审查页 / Contract review page
│           ├── CostView.vue         #   费用计算页 / Cost calculator page
│           └── ProfileView.vue      #   个人中心页 / Profile page
│
├── src/                             # 核心逻辑 / Core logic
│   ├── core/
│   │   ├── agent.py                 #   ReAct Agent 引擎 / ReAct Agent engine
│   │   ├── llm.py                   #   Ollama LLM 封装 / Ollama LLM wrapper
│   │   ├── embedder.py              #   本地 Embedding / Local embedding
│   │   ├── memory.py                #   长期记忆 (SQLite + 向量) / Long-term memory
│   │   ├── tools.py                 #   9 个工具函数 / 9 tool functions
│   │   ├── contract_parser.py       #   合同结构化提取 / Contract structured extraction
│   │   ├── risk_engine.py           #   风险评分引擎(80+规则) / Risk scoring engine (80+ rules)
│   │   └── ocr.py                   #   合同OCR(PaddleOCR/Tesseract) / Contract OCR
│   ├── gui/                         #   tkinter 桌面端 / Desktop GUI
│   │   ├── app.py                   #   主窗口 / Main window
│   │   ├── chat_panel.py            #   对话面板 / Chat panel
│   │   ├── checklist_panel.py       #   看房清单 / Checklist panel
│   │   ├── contract_panel.py        #   合同分析 / Contract panel
│   │   └── calculator_panel.py      #   费用计算 / Calculator panel
│   ├── utils/
│   │   ├── db.py                    #   SQLite 多用户数据库 / SQLite multi-user DB
│   │   ├── config.py                #   配置管理 / Config management
│   │   └── text.py                  #   文本处理 / Text processing
│   └── data/
│       ├── standard_contract.json   #   18项标准合同条款 / 18-item standard contract clauses
│       ├── city_rules.json          #   城市租房政策 / City rental policies
│       └── blacklist.json           #   黑名单数据 / Blacklist data
│
├── prompts/                         # 提示词 / Prompt templates
│   ├── system.md                    #   系统提示词 / System prompt
│   └── contract_review.md           #   合同审查提示词 / Contract review prompt
│
└── tests/
    └── test_agent.py                #   测试 / Tests
```

## 🔌 API 概览 / API Overview

| 方法 Method | 路径 Path | 说明 Description |
|---|---|---|
| `POST` | `/api/chat` | 对话（普通）/ Chat (normal) |
| `POST` | `/api/chat/stream` | 对话（SSE 流式）/ Chat (SSE streaming) |
| `POST` | `/api/contract/review/text` | 合同审查(文本输入) / Contract review (text) |
| `POST` | `/api/contract/review/upload` | 合同审查(图片上传) / Contract review (upload) |
| `GET`  | `/api/contract/ai-review` | AI深度审查(独立) / AI deep review |
| `GET`  | `/api/contract/negotiation-speech` | 谈判话术 / Negotiation speech |
| `POST` | `/api/tools/cost` | 费用计算 / Cost calculation |
| `POST` | `/api/tools/deposit` | 押金模拟 / Deposit simulation |
| `POST` | `/api/tools/checklist` | 看房清单 / Viewing checklist |
| `POST` | `/api/tools/blacklist/check` | 黑名单查询 / Blacklist check |
| `POST` | `/api/tools/blacklist/report` | 黑名单上报 / Blacklist report |
| `GET`  | `/api/tools/city-rules` | 城市政策 / City rental rules |
| `GET`  | `/api/health` | 健康检查 / Health check |
| `GET`  | `/docs` | Swagger 文档 / Swagger docs |

所有接口支持 `user_id` 参数实现多用户数据隔离。

All endpoints support `user_id` parameter for per-user data isolation.

## 🤖 Agent 工具集 / Agent Tools

| 工具 Tool | 输入 Input | 输出 Output |
|---|---|---|
| `calculate_cost` | 租金、押金、中介费等 / rent, deposit, agent fee... | 费用明细 JSON / cost breakdown JSON |
| `simulate_deposit` | 押金、租期、退租情况 / deposit, term, conditions | 退还模拟 / refund simulation |
| `check_blacklist` | 名称、城市 / name, city | 匹配记录 / matched records |
| `report_blacklist` | 名称、原因、城市 / name, reason, city | 上报确认 / report confirmation |
| `get_checklist` | 阶段（看房前/中/后）/ phase | 检查清单 / checklist items |
| `review_contract` | 合同文本 / contract text | 风险等级 + 条款分析 / risk level + clause analysis |
| `generate_speech` | 场景 / situation | 话术文本 / speech text |
| `get_city_rules` | 城市 / city | 租房政策 / rental policies |
| `estimate_commute` | 地址 / address | 通勤时间估算 / commute estimation |

## 🧪 测试 / Testing

```bash
python -m pytest tests/ -v
```

## 📋 Roadmap

- [x] 合同 OCR 识别（拍照→文本）/ Contract OCR (photo → text)
- [x] 合同结构化提取（25+字段）/ Contract structured extraction (25+ fields)
- [x] 风险评分引擎（80+规则+18项标准对比）/ Risk scoring engine (80+ rules + 18-item standard comparison)
- [x] AI 深度审查 + 谈判话术 / AI deep review + negotiation scripts
- [ ] 房源信息抓取与初筛 / Listing scraping & screening
- [ ] 合同解析 LLM 利用率优化（当前偏依赖正则）/ Improve LLM utilization in contract parsing
- [ ] 微信小程序适配 / WeChat Mini Program
- [ ] PostgreSQL + pgvector 升级 / PostgreSQL + pgvector migration
- [ ] PWA 离线支持 / PWA offline support
- [ ] 深色模式 / Dark mode
- [ ] 多语言支持 / i18n

## 📄 License

[MIT](LICENSE)

---

<p align="center">
  Made with ❤️ for renters everywhere<br>
  为每一个租房者而做
</p>
