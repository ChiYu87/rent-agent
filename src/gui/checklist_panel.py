"""看房清单面板"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from ..core.tools import get_checklist


class ChecklistPanel:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self._build_ui()

    def _build_ui(self):
        # 阶段选择
        phase_frame = ttk.LabelFrame(self.frame, text="选择阶段")
        phase_frame.pack(fill=tk.X, padx=10, pady=5)

        self.phase_var = tk.StringVar(value="看房中")
        phases = ["看房前", "看房中", "看房后"]
        for p in phases:
            ttk.Radiobutton(phase_frame, text=p, variable=self.phase_var, value=p,
                           command=self._load_checklist).pack(side=tk.LEFT, padx=15, pady=5)

        # 清单内容
        self.text_area = scrolledtext.ScrolledText(
            self.frame, wrap=tk.WORD, font=("Microsoft YaHei UI", 11),
            state=tk.DISABLED, bg="#FAFAFA", padx=15, pady=15,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text_area.tag_config("header", font=("Microsoft YaHei UI", 13, "bold"), foreground="#1565C0")
        self.text_area.tag_config("item", font=("Microsoft YaHei UI", 11), foreground="#333333")
        self.text_area.tag_config("tip", font=("Microsoft YaHei UI", 10), foreground="#757575")

        # 记录区域
        record_frame = ttk.LabelFrame(self.frame, text="我的看房记录")
        record_frame.pack(fill=tk.X, padx=10, pady=5)

        addr_frame = ttk.Frame(record_frame)
        addr_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(addr_frame, text="地址:").pack(side=tk.LEFT)
        self.addr_var = tk.StringVar()
        ttk.Entry(addr_frame, textvariable=self.addr_var, width=40).pack(side=tk.LEFT, padx=5)

        notes_frame = ttk.Frame(record_frame)
        notes_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(notes_frame, text="备注:").pack(side=tk.LEFT)
        self.notes_var = tk.StringVar()
        ttk.Entry(notes_frame, textvariable=self.notes_var, width=40).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(record_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Button(btn_frame, text="💾 保存记录", command=self._save_record).pack(side=tk.LEFT, padx=5)

        # 加载默认清单
        self._load_checklist()

    def _load_checklist(self):
        phase = self.phase_var.get()
        content = get_checklist(phase)

        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)

        lines = content.split("\n")
        for line in lines:
            if line.startswith("##"):
                self.text_area.insert(tk.END, line.lstrip("#") + "\n", "header")
            elif line.startswith("-") or line.startswith("📋") or line.startswith("🔌") or \
                 line.startswith("🚪") or line.startswith("🧱") or line.startswith("💧") or \
                 line.startswith("🔇") or line.startswith("☀️") or line.startswith("📶") or \
                 line.startswith("🔢") or line.startswith("📸") or line.startswith("📊"):
                self.text_area.insert(tk.END, line + "\n", "item")
            else:
                self.text_area.insert(tk.END, line + "\n", "tip")

        self.text_area.config(state=tk.DISABLED)

    def _save_record(self):
        from ..utils.db import Database
        db = Database()
        address = self.addr_var.get().strip()
        notes = self.notes_var.get().strip()
        if not address:
            return
        checklist = {"phase": self.phase_var.get()}
        db.add_viewing(address, checklist, [], notes, 0.0)
        self.addr_var.set("")
        self.notes_var.set("")
