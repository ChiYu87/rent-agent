"""费用计算面板"""
import tkinter as tk
from tkinter import ttk
from ..core.tools import calc_rent_cost, calc_deposit_return


class CalculatorPanel:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self._build_ui()

    def _build_ui(self):
        # 左右分栏
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧：租房成本
        cost_frame = ttk.LabelFrame(paned, text="💰 租房真实成本")
        paned.add(cost_frame, weight=1)

        fields = [
            ("月租金（元）", "rent", "3000"),
            ("押金（元，留空=1个月租金）", "deposit", ""),
            ("中介费（元）", "agent_fee", "0"),
            ("水电燃网月均（元）", "utilities", "200"),
            ("物业费月均（元）", "property_fee", "0"),
        ]

        self.cost_vars = {}
        for i, (label, key, default) in enumerate(fields):
            ttk.Label(cost_frame, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            var = tk.StringVar(value=default)
            self.cost_vars[key] = var
            ttk.Entry(cost_frame, textvariable=var, width=15).grid(row=i, column=1, padx=10, pady=5)

        # 付款方式
        ttk.Label(cost_frame, text="付款方式").grid(row=len(fields), column=0, padx=10, pady=5, sticky="w")
        self.payment_var = tk.StringVar(value="押一付三")
        payment_combo = ttk.Combobox(cost_frame, textvariable=self.payment_var,
                                     values=["押一付一", "押一付三", "押二付一", "押二付三"],
                                     width=12, state="readonly")
        payment_combo.grid(row=len(fields), column=1, padx=10, pady=5)

        ttk.Button(cost_frame, text="🧮 计算", command=self._calc_cost).grid(
            row=len(fields) + 1, column=0, columnspan=2, pady=15)

        self.cost_result = tk.Text(cost_frame, wrap=tk.WORD, font=("Microsoft YaHei UI", 10),
                                   height=10, bg="#FAFAFA", padx=10, pady=10, state=tk.DISABLED)
        self.cost_result.grid(row=len(fields) + 2, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")
        cost_frame.grid_rowconfigure(len(fields) + 2, weight=1)
        cost_frame.grid_columnconfigure(1, weight=1)

        # 右侧：押金退还
        deposit_frame = ttk.LabelFrame(paned, text="🏦 押金退还模拟")
        paned.add(deposit_frame, weight=1)

        dep_fields = [
            ("押金金额（元）", "deposit", "3000"),
            ("合同月数", "contract_months", "12"),
        ]
        self.dep_vars = {}
        for i, (label, key, default) in enumerate(dep_fields):
            ttk.Label(deposit_frame, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            var = tk.StringVar(value=default)
            self.dep_vars[key] = var
            ttk.Entry(deposit_frame, textvariable=var, width=15).grid(row=i, column=1, padx=10, pady=5)

        # 是否提前退租
        row = len(dep_fields)
        ttk.Label(deposit_frame, text="提前退租").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.early_var = tk.StringVar(value="否")
        ttk.Combobox(deposit_frame, textvariable=self.early_var,
                     values=["否", "是"], width=12, state="readonly").grid(row=row, column=1, padx=10, pady=5)

        # 是否有损坏
        row += 1
        ttk.Label(deposit_frame, text="设施损坏").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.damage_var = tk.StringVar(value="不确定")
        ttk.Combobox(deposit_frame, textvariable=self.damage_var,
                     values=["否", "是", "不确定"], width=12, state="readonly").grid(row=row, column=1, padx=10, pady=5)

        ttk.Button(deposit_frame, text="🧮 模拟", command=self._calc_deposit).grid(
            row=row + 1, column=0, columnspan=2, pady=15)

        self.deposit_result = tk.Text(deposit_frame, wrap=tk.WORD, font=("Microsoft YaHei UI", 10),
                                      height=10, bg="#FAFAFA", padx=10, pady=10, state=tk.DISABLED)
        self.deposit_result.grid(row=row + 2, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")
        deposit_frame.grid_rowconfigure(row + 2, weight=1)
        deposit_frame.grid_columnconfigure(1, weight=1)

    def _calc_cost(self):
        try:
            rent = float(self.cost_vars["rent"].get() or 0)
            deposit_str = self.cost_vars["deposit"].get().strip()
            deposit = float(deposit_str) if deposit_str else None
            agent_fee = float(self.cost_vars["agent_fee"].get() or 0)
            utilities = float(self.cost_vars["utilities"].get() or 200)
            property_fee = float(self.cost_vars["property_fee"].get() or 0)
            payment_cycle = self.payment_var.get()

            result = calc_rent_cost(rent, deposit, agent_fee, utilities, property_fee, payment_cycle)
            self._show_result(self.cost_result, result)
        except ValueError:
            self._show_result(self.cost_result, "⚠️ 请输入有效数字")

    def _calc_deposit(self):
        try:
            deposit = float(self.dep_vars["deposit"].get() or 0)
            months = int(self.dep_vars["contract_months"].get() or 12)
            early = self.early_var.get()
            damage = self.damage_var.get()

            result = calc_deposit_return(deposit, months, damage, early)
            self._show_result(self.deposit_result, result)
        except ValueError:
            self._show_result(self.deposit_result, "⚠️ 请输入有效数字")

    def _show_result(self, text_widget, content):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)
        text_widget.config(state=tk.DISABLED)
