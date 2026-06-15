"""对话面板 - 核心交互"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading


class ChatPanel:
    def __init__(self, parent, agent):
        self.agent = agent
        self.frame = ttk.Frame(parent)
        self._build_ui()

    def _build_ui(self):
        # 消息区域
        self.chat_area = scrolledtext.ScrolledText(
            self.frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),
            state=tk.DISABLED,
            bg="#FAFAFA",
            padx=10,
            pady=10,
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.chat_area.tag_config("user", foreground="#1565C0", font=("Microsoft YaHei UI", 10, "bold"))
        self.chat_area.tag_config("assistant", foreground="#2E7D32")
        self.chat_area.tag_config("system", foreground="#757575", font=("Microsoft YaHei UI", 9))
        self.chat_area.tag_config("warning", foreground="#E65100", font=("Microsoft YaHei UI", 10, "bold"))

        # 快捷按钮
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=5)

        quick_btns = [
            ("🏠 我要租房", "我是租房小白，请帮我从头开始，告诉我租房全流程该注意什么"),
            ("💰 算费用", "帮我算一下：月租3000，押一付三，中介费一个月，水电燃网大概200，物业费100"),
            ("📋 看房清单", "我明天要去实地看房了，给我一份看房检查清单"),
            ("📝 审合同", "我拿到一份租房合同，请帮我审查有没有坑"),
            ("🗣️ 装懂行", "帮我生成一段和中介谈价格的专业话术"),
            ("🛡️ 查黑名单", "我想查一下某中介/房东有没有被举报过"),
        ]

        for text, prompt in quick_btns:
            ttk.Button(
                btn_frame, text=text,
                command=lambda p=prompt: self._send_message(p)
            ).pack(side=tk.LEFT, padx=2)

        # 输入区域
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill=tk.X, pady=(5, 5))

        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var, font=("Microsoft YaHei UI", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda e: self._send_message())

        self.send_btn = ttk.Button(input_frame, text="发送", command=lambda: self._send_message())
        self.send_btn.pack(side=tk.RIGHT)

        # 欢迎消息
        self._append_message("system", "🏠 欢迎使用 RentBuddy！我是你的租房助手，随时问问题。")
        self._append_message("system", "提示：点击上方快捷按钮快速开始，或直接输入你的问题")

    def _send_message(self, text: str = None):
        user_input = text or self.input_var.get().strip()
        if not user_input:
            return
        self.input_var.set("")

        # 显示用户消息
        self._append_message("user", f"你: {user_input}")

        # 禁用输入
        self.send_btn.config(state=tk.DISABLED)
        self.input_entry.config(state=tk.DISABLED)

        # 异步调用 Agent
        def call_agent():
            try:
                response = self.agent.run(user_input)
                self.frame.after(0, lambda: self._on_response(response))
            except Exception as e:
                self.frame.after(0, lambda: self._on_response(f"⚠️ 出错了: {e}"))

        threading.Thread(target=call_agent, daemon=True).start()

    def _on_response(self, response: str):
        self._append_message("assistant", f"助手: {response}")
        self.send_btn.config(state=tk.NORMAL)
        self.input_entry.config(state=tk.NORMAL)
        self.input_entry.focus_set()

    def _append_message(self, tag: str, text: str):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, text + "\n\n", tag)
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def clear_chat(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.config(state=tk.DISABLED)
        self._append_message("system", "🏠 新会话已开始")
