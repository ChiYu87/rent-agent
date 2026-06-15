"""主窗口 - tkinter GUI"""
import tkinter as tk
from tkinter import ttk, font as tkfont
from .chat_panel import ChatPanel
from .checklist_panel import ChecklistPanel
from .contract_panel import ContractPanel
from .calculator_panel import CalculatorPanel
from ..core.agent import ReActAgent
from ..core.llm import LLM


class RentBuddyApp:
    """租房小白助手主窗口"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🏠 RentBuddy - 租房小白助手")
        self.root.geometry("900x680")
        self.root.minsize(800, 600)

        # 检查 Ollama
        self.llm = LLM()
        self.ollama_ok = self.llm.check_connection()

        # 初始化 Agent
        self.agent = ReActAgent()

        # 样式
        self._setup_styles()

        # 布局
        self._build_ui()

        # 状态栏提示
        if not self.ollama_ok:
            self.status_var.set("⚠️ Ollama 未连接，请先启动 Ollama 并拉取模型")
        else:
            models = self.llm.list_models()
            self.status_var.set(f"✅ 已连接 Ollama | 模型: {', '.join(models[:3])}")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 9))
        style.configure("Tab.TNotebook", font=("Microsoft YaHei UI", 10))

    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(header, text="🏠 RentBuddy", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="租房小白助手 · 降低信息差 · 标准化流程 · 风险预警",
                  font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT, padx=10)

        # Tab 页面
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 1. 对话面板
        self.chat_panel = ChatPanel(self.notebook, self.agent)
        self.notebook.add(self.chat_panel.frame, text="💬 对话")

        # 2. 看房清单
        self.checklist_panel = ChecklistPanel(self.notebook)
        self.notebook.add(self.checklist_panel.frame, text="✅ 看房清单")

        # 3. 合同审查
        self.contract_panel = ContractPanel(self.notebook, self.agent)
        self.notebook.add(self.contract_panel.frame, text="📋 合同审查")

        # 4. 费用计算
        self.calc_panel = CalculatorPanel(self.notebook)
        self.notebook.add(self.calc_panel.frame, text="💰 费用计算")

        # 底部状态栏
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.status_var = tk.StringVar(value="正在初始化...")
        ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)

        # 设置按钮
        ttk.Button(status_bar, text="⚙️ 设置", command=self._show_settings).pack(side=tk.RIGHT)
        ttk.Button(status_bar, text="🔄 新会话", command=self._reset_session).pack(side=tk.RIGHT, padx=5)

    def _show_settings(self):
        """设置对话框"""
        win = tk.Toplevel(self.root)
        win.title("⚙️ 设置")
        win.geometry("400x300")
        win.resizable(False, False)

        from ..utils.config import Config
        cfg = Config()

        # 模型选择
        ttk.Label(win, text="LLM 模型:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        model_var = tk.StringVar(value=cfg.get("llm.model"))
        model_entry = ttk.Entry(win, textvariable=model_var, width=30)
        model_entry.grid(row=0, column=1, padx=10, pady=10)

        # Ollama 地址
        ttk.Label(win, text="Ollama 地址:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        url_var = tk.StringVar(value=cfg.get("llm.base_url"))
        ttk.Entry(win, textvariable=url_var, width=30).grid(row=1, column=1, padx=10, pady=10)

        # 城市
        ttk.Label(win, text="默认城市:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        city_var = tk.StringVar(value=cfg.get("city"))
        ttk.Entry(win, textvariable=city_var, width=30).grid(row=2, column=1, padx=10, pady=10)

        def save():
            cfg.set("llm.model", model_var.get())
            cfg.set("llm.base_url", url_var.get())
            cfg.set("city", city_var.get())
            win.destroy()
            self.status_var.set("✅ 设置已保存，重启生效")

        ttk.Button(win, text="保存", command=save).grid(row=3, column=0, columnspan=2, pady=20)

    def _reset_session(self):
        """重置会话"""
        self.agent.reset_session()
        self.chat_panel.clear_chat()
        self.status_var.set("✅ 新会话已开始")

    def run(self):
        self.root.mainloop()
