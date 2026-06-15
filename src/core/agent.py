"""自研 ReAct Agent 引擎

ReAct = Reasoning + Acting
循环：思考(Thought) → 行动(Action) → 观察(Observation) → ... → 回答(Answer)
支持多用户隔离，每个用户独立的 Memory 和 session。
"""
import re
import json
import uuid
from .llm import LLM
from .memory import Memory
from .tools import get_tool_by_name, get_tools_description
from ..utils.db import Database
from ..utils.config import Config


SYSTEM_PROMPT = """你是「租房小白助手 RentBuddy」，一个专门帮助租房新手的 AI 助手。

你的使命：降低信息差 + 标准化流程 + 风险预警。

你具备以下能力：
1. 🏠 租房全流程指导（找房→看房→签约→入住→退租）
2. 💰 费用精确计算（真实成本、押金模拟）
3. 📋 看房检查清单（拍照指引、注意事项）
4. 📝 合同风险审查（霸王条款识别、标准对比）
5. 🗣️ 专业话术生成（假装很懂行模式）
6. 🏙️ 本地政策查询（不同城市规则差异）
7. 🛡️ 黑名单查询与上报

## 行为准则
- 始终站在租客立场
- 遇到风险主动警告，宁滥勿缺
- 回答具体、实用，不说废话
- 不会的不要编，老老实实说
- 涉及法律问题提醒用户咨询专业人士

## ReAct 格式
你在每次思考时应该使用以下格式：

Thought: 我需要分析用户的问题...
Action: tool_name(param1="value1", param2="value2")
Observation: (工具返回的结果)
Thought: 根据结果我需要...
... (可以多轮 Thought-Action-Observation)
Answer: 最终回答用户

如果不需要调用工具，直接回答即可。"""


class ReActAgent:
    """ReAct Agent - 支持多用户"""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.llm = LLM()
        self.memory = Memory(user_id)
        self.db = Database()
        self.session_id = str(uuid.uuid4())[:8]
        self.max_iterations = Config().get("agent.max_iterations", 5)
        self.tools_desc = get_tools_description()

    def run(self, user_input: str, stream: bool = False) -> str:
        """执行一轮对话"""
        # 1. 确保用户存在
        self.db.ensure_user(self.user_id)

        # 2. 构建上下文
        context = self.memory.get_context(self.session_id, user_input)

        # 3. 构建 ReAct 提示
        react_prompt = f"""{SYSTEM_PROMPT}

{self.tools_desc}

---

当前对话历史：
{self._format_context(context)}

用户最新消息：{user_input}

请使用 ReAct 格式思考并回答。如果不需要工具，直接给出 Answer。"""

        messages = [{"role": "system", "content": react_prompt}]

        # 4. ReAct 循环
        for iteration in range(self.max_iterations):
            response = self.llm.chat(messages)

            # 解析 ReAct 输出
            action_match = re.search(r'Action:\s*(\w+)\((.+?)\)', response, re.DOTALL)

            if not action_match:
                # 没有 Action，直接返回
                answer = self._extract_answer(response)
                self.memory.save_interaction(self.session_id, user_input, answer)
                return answer

            # 执行工具
            tool_name = action_match.group(1)
            tool_params_str = action_match.group(2)

            tool_fn = get_tool_by_name(tool_name)
            if tool_fn is None:
                observation = f"错误：工具 '{tool_name}' 不存在"
            else:
                try:
                    params = self._parse_params(tool_params_str)
                    observation = tool_fn(**params)
                except Exception as e:
                    observation = f"工具执行错误: {e}"

            # 把结果加入上下文，继续推理
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}\n\n请继续思考，或直接给出 Answer。"
            })

        # 超过迭代次数，强制总结
        messages.append({
            "role": "user",
            "content": "已达到最大思考轮数，请根据以上信息直接给出 Answer。"
        })
        final = self.llm.chat(messages)
        answer = self._extract_answer(final)
        self.memory.save_interaction(self.session_id, user_input, answer)
        return answer

    def run_stream(self, user_input: str):
        """流式输出"""
        self.db.ensure_user(self.user_id)
        context = self.memory.get_context(self.session_id, user_input)

        react_prompt = f"""{SYSTEM_PROMPT}

{self.tools_desc}

---

当前对话历史：
{self._format_context(context)}

用户最新消息：{user_input}

请使用 ReAct 格式思考并回答。如果不需要工具，直接给出 Answer。"""

        messages = [{"role": "system", "content": react_prompt}]

        for iteration in range(self.max_iterations):
            full_response = ""
            for chunk in self.llm.chat_stream(messages):
                full_response += chunk
                yield chunk

            action_match = re.search(r'Action:\s*(\w+)\((.+?)\)', full_response, re.DOTALL)
            if not action_match:
                answer = self._extract_answer(full_response)
                self.memory.save_interaction(self.session_id, user_input, answer)
                return

            tool_name = action_match.group(1)
            tool_params_str = action_match.group(2)
            tool_fn = get_tool_by_name(tool_name)

            if tool_fn is None:
                observation = f"错误：工具 '{tool_name}' 不存在"
            else:
                try:
                    params = self._parse_params(tool_params_str)
                    observation = tool_fn(**params)
                except Exception as e:
                    observation = f"工具执行错误: {e}"

            yield f"\n\n📋 工具结果：{observation}\n\n"

            messages.append({"role": "assistant", "content": full_response})
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}\n\n请继续思考，或直接给出 Answer。"
            })

        answer = self._extract_answer(full_response)
        self.memory.save_interaction(self.session_id, user_input, answer)

    def review_contract_text(self, contract_text: str) -> dict:
        """合同审查（API 专用，返回结构化结果）"""
        from .tools import review_contract

        # 1. 本地规则引擎
        local_result = review_contract(contract_text)

        # 2. LLM 深度审查
        prompt = f"""请仔细审查以下租房合同，找出所有对租客不利的条款：

{contract_text}

请从以下角度审查：
1. 押金条款是否合理
2. 违约责任是否对等
3. 维修责任归属是否明确
4. 有无霸王条款
5. 转租条款是否合理
6. 水电费等其他费用是否明确
7. 退租条款是否公平

标注风险等级（🚨高风险/⚠️中风险/✅正常）。用中文回答。"""

        llm_result = self.llm.generate(prompt, system=SYSTEM_PROMPT_SHORT)

        # 3. 保存审查记录
        risk_level = "high" if "🚨" in local_result else ("medium" if "⚠️" in local_result else "low")
        self.db.add_contract(self.user_id, "", contract_text, {
            "local": local_result,
            "llm": llm_result,
        }, risk_level)

        return {
            "local_scan": local_result,
            "ai_review": llm_result,
            "risk_level": risk_level,
        }

    def _format_context(self, context: list[dict]) -> str:
        lines = []
        for msg in context:
            role = {"system": "系统", "user": "用户", "assistant": "助手"}.get(msg["role"], msg["role"])
            lines.append(f"[{role}]: {msg['content']}")
        return "\n".join(lines)

    def _extract_answer(self, response: str) -> str:
        answer_match = re.search(r'Answer:\s*(.+)', response, re.DOTALL)
        if answer_match:
            return answer_match.group(1).strip()

        lines = response.split("\n")
        result_lines = []
        in_thought = False
        for line in lines:
            if line.startswith("Thought:"):
                in_thought = True
                continue
            if in_thought and (line.startswith("Action:") or line.startswith("Observation:")):
                in_thought = False
                continue
            if not in_thought:
                result_lines.append(line)

        cleaned = "\n".join(result_lines).strip()
        return cleaned if cleaned else response.strip()

    def _parse_params(self, params_str: str) -> dict:
        params = {}
        for match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', params_str):
            params[match.group(1)] = match.group(2)
        for match in re.finditer(r'(\w+)\s*=\s*(\d+\.?\d*)', params_str):
            key = match.group(1)
            val = match.group(2)
            if key not in params:
                params[key] = float(val) if '.' in val else int(val)
        return params

    def reset_session(self):
        self.session_id = str(uuid.uuid4())[:8]


SYSTEM_PROMPT_SHORT = "你是租房合同审查专家，帮助租客识别不利条款。站在租客立场，实事求是，标注风险。"
