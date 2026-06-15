"""合同审查面板"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter import filedialog
import threading


class ContractPanel:
    def __init__(self, parent, agent):
        self.agent = agent
        self.frame = ttk.Frame(parent)
        self._build_ui()

    def _build_ui(self):
        # 合同输入
        input_frame = ttk.LabelFrame(self.frame, text="合同内容")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        btn_row = ttk.Frame(input_frame)
        btn_row.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_row, text="📁 上传文件", command=self._upload_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="📋 粘贴合同", command=self._paste_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🔍 开始审查", command=self._analyze).pack(side=tk.RIGHT, padx=5)

        self.contract_text = scrolledtext.ScrolledText(
            input_frame, wrap=tk.WORD, font=("Microsoft YaHei UI", 10),
            height=12, bg="#FAFAFA", padx=10, pady=10,
        )
        self.contract_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 审查结果
        result_frame = ttk.LabelFrame(self.frame, text="审查结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.result_area = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=("Microsoft YaHei UI", 10),
            height=12, bg="#F5F5F5", padx=10, pady=10, state=tk.DISABLED,
        )
        self.result_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_area.tag_config("risk", foreground="#C62828", font=("Microsoft YaHei UI", 10, "bold"))
        self.result_area.tag_config("warn", foreground="#E65100", font=("Microsoft YaHei UI", 10, "bold"))
        self.result_area.tag_config("safe", foreground="#2E7D32", font=("Microsoft YaHei UI", 10, "bold"))
        self.result_area.tag_config("header", foreground="#1565C0", font=("Microsoft YaHei UI", 12, "bold"))
        self.result_area.tag_config("normal", foreground="#333333")

    def _upload_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("文本文件", "*.txt"), ("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        if not filepath:
            return

        try:
            if filepath.endswith(".pdf"):
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                text = "\n".join([page.extract_text() or "" for page in reader.pages])
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()

            self.contract_text.delete("1.0", tk.END)
            self.contract_text.insert("1.0", text)
        except Exception as e:
            self.contract_text.delete("1.0", tk.END)
            self.contract_text.insert("1.0", f"⚠️ 文件读取失败: {e}")

    def _paste_template(self):
        template = """房屋租赁合同

出租方（甲方）：___________
承租方（乙方）：___________

第一条 房屋基本情况
房屋地址：___________
建筑面积：___________ ㎡
房屋用途：居住

第二条 租赁期限
租赁期自 ____年__月__日 至 ____年__月__日

第三条 租金及支付方式
月租金：___________ 元
支付方式：押__付__
支付日期：每月__日前

第四条 押金
押金金额：___________ 元
退还条件：___________

第五条 其他费用
水费、电费、燃气费由乙方承担
物业费由___方承担
宽带费由___方承担

第六条 维修责任
房屋及设施维修由___方负责

第七条 违约责任
___________

第八条 转租条款
___________"""
        self.contract_text.delete("1.0", tk.END)
        self.contract_text.insert("1.0", template)

    def _analyze(self):
        contract_content = self.contract_text.get("1.0", tk.END).strip()
        if not contract_content:
            self._show_result("⚠️ 请先输入合同内容", "warn")
            return

        self._show_result("🔍 正在审查合同，请稍候...", "normal")

        def analyze_async():
            try:
                # 先用本地规则引擎
                from ..core.tools import review_contract
                local_result = review_contract(contract_content)

                # 再用 LLM 深度审查
                prompt = f"""请仔细审查以下租房合同，找出所有对租客不利的条款，并给出建议：

{contract_content}

请从以下角度审查：
1. 押金条款是否合理
2. 违约责任是否对等
3. 维修责任归属是否明确
4. 有无霸王条款
5. 转租条款是否合理
6. 水电费等其他费用是否明确
7. 退租条款是否公平

请用中文回答，标注风险等级（🚨高风险/⚠️中风险/✅正常）。"""

                llm_result = self.agent.llm.generate(prompt, system=SYSTEM_PROMPT_SHORT)
                combined = f"## 📋 本地规则扫描\n\n{local_result}\n\n---\n\n## 🤖 AI 深度审查\n\n{llm_result}"
                self.frame.after(0, lambda: self._show_result(combined, "normal"))
            except Exception as e:
                self.frame.after(0, lambda: self._show_result(f"⚠️ 审查失败: {e}", "risk"))

        threading.Thread(target=analyze_async, daemon=True).start()

    def _show_result(self, text: str, tag: str = "normal"):
        self.result_area.config(state=tk.NORMAL)
        self.result_area.delete("1.0", tk.END)
        self.result_area.insert("1.0", text, tag)
        self.result_area.config(state=tk.DISABLED)


SYSTEM_PROMPT_SHORT = "你是租房合同审查专家，帮助租客识别不利条款。站在租客立场，实事求是，标注风险。"
