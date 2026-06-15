# 🏠 RentBuddy - 租房小白 AI 助手

> 降低信息差 · 标准化流程 · 风险预警

租房全流程贴身助手：找房→看房→签约→入住，有问必答 + 主动提醒 + 决策辅助。

## 功能模块

| 模块 | 功能 |
|------|------|
| 🔍 智能找房助手 | 需求诊断、房源初筛、通勤计算 |
| ✅ 看房 Checklist | 语音/文字提醒、拍照指引、实时问答 |
| 📋 合同风控助手 | 合同解析、风险标注、标准对比 |
| 💰 费用计算器 | 真实成本、押金退还模拟 |
| 🛡️ 维权与入住指南 | 入住交接、报修指引、退租清单 |

## 技术栈

- **LLM**: Ollama (qwen2.5 / llama3)
- **Agent**: 自研 ReAct 框架
- **Embedding**: Ollama 本地 embedding
- **GUI**: tkinter (Python 自带)
- **存储**: SQLite3 + 向量检索 (Python 自带)
- **记忆**: SQLite 长期记忆 + 对话历史

## 快速开始

```bash
# 1. 安装 Ollama 并拉取模型
ollama pull qwen2.5
ollama pull nomic-embed-text

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python main.py
```

## 项目结构

```
rent-agent/
├── main.py                  # 入口
├── requirements.txt
├── README.md
├── src/
│   ├── core/
│   │   ├── agent.py         # ReAct Agent 引擎
│   │   ├── llm.py           # Ollama LLM 封装
│   │   ├── memory.py        # 长期记忆 (SQLite + 向量)
│   │   ├── embedder.py      # 本地 Embedding
│   │   └── tools.py         # Agent 工具集
│   ├── gui/
│   │   ├── app.py           # 主窗口
│   │   ├── chat_panel.py    # 对话面板
│   │   ├── checklist_panel.py # 看房清单
│   │   ├── contract_panel.py  # 合同分析
│   │   └── calculator_panel.py # 费用计算
│   ├── utils/
│   │   ├── db.py            # SQLite 数据库
│   │   ├── config.py        # 配置管理
│   │   └── text.py          # 文本处理
│   └── data/
│       ├── standard_contract.json  # 标准合同条款
│       ├── city_rules.json         # 城市政策
│       └── blacklist.json          # 黑名单数据
├── prompts/
│   ├── system.md            # 系统提示词
│   ├── checklist.md         # 看房清单模板
│   └── contract_review.md   # 合同审查提示词
└── tests/
    └── test_agent.py
```

## License

MIT
