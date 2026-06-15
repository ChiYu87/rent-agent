"""Agent 工具集 (Tools)"""
import json
import re
import subprocess
from pathlib import Path
from typing import Callable
from ..utils.text import normalize_price, format_money


# ==================== 工具注册表 ====================

TOOLS = []  # 工具列表


def tool(name: str, description: str, params: list = None):
    """工具装饰器"""
    def decorator(func: Callable):
        func._tool_meta = {
            "name": name,
            "description": description,
            "params": params or [],
        }
        TOOLS.append(func)
        return func
    return decorator


# ==================== 工具实现 ====================

@tool(
    name="calc_rent_cost",
    description="计算租房真实成本",
    params=[
        {"name": "rent", "type": "number", "description": "月租金（元）"},
        {"name": "deposit", "type": "number", "description": "押金（元，通常等于1-2个月租金）"},
        {"name": "agent_fee", "type": "number", "description": "中介费（元）"},
        {"name": "utilities", "type": "number", "description": "水电燃网等月均支出（元）"},
        {"name": "property_fee", "type": "number", "description": "物业费月均（元）"},
        {"name": "payment_cycle", "type": "string", "description": "付款周期：押一付一/押一付三/押二付一"},
    ]
)
def calc_rent_cost(rent: float, deposit: float = None, agent_fee: float = 0,
                   utilities: float = 200, property_fee: float = 0,
                   payment_cycle: str = "押一付三") -> str:
    """
    计算租房的真实成本
    """
    # 解析押金比例
    if deposit is None:
        deposit = rent  # 默认押一

    # 解析付款周期
    cycle_match = re.search(r'押(\d)付(\d)', payment_cycle)
    if cycle_match:
        deposit_months = int(cycle_match.group(1))
        pay_months = int(cycle_match.group(2))
    else:
        deposit_months, pay_months = 1, 3

    deposit_amt = deposit_months * rent
    first_payment = pay_months * rent
    monthly_avg = (first_payment + deposit_amt + agent_fee) / pay_months + utilities + property_fee

    result = {
        "月租金": f"{rent:.0f}元",
        "押金总额": f"{deposit_amt:.0f}元",
        "首期付款（不含押金）": f"{first_payment:.0f}元（含{pay_months}个月）",
        "中介费": f"{agent_fee:.0f}元",
        "月均固定支出": f"{monthly_avg:.0f}元/月",
        "首月总支出": f"{first_payment + deposit_amt + agent_fee:.0f}元",
        "提示": "实际月均支出 = (首期+押金+中介)/期数 + 水电燃网 + 物业"
    }

    # 风险提示
    if agent_fee > rent * 0.5:
        result["⚠️风险"] = "中介费偏高，通常半个月到一个半月租金为正常"
    if deposit_months > 2:
        result["⚠️风险"] = "押金月数偏多，押金越多风险越高"

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool(
    name="calc_deposit_return",
    description="模拟押金退还",
    params=[
        {"name": "deposit", "type": "number", "description": "押金金额（元）"},
        {"name": "contract_months", "type": "number", "description": "合同月数"},
        {"name": "has_damage", "type": "string", "description": "是否有损坏：是/否/不确定"},
        {"name": "early_termination", "type": "string", "description": "是否提前退租：是/否"},
        {"name": "notice_days", "type": "number", "description": "提前通知天数（通常30天）"},
    ]
)
def calc_deposit_return(deposit: float, contract_months: int = 12,
                        has_damage: str = "不确定", early_termination: str = "否",
                        notice_days: int = 30) -> str:
    """模拟退租押金退还"""
    result = {}

    # 正常退租
    if early_termination == "否":
        result["正常退租"] = {
            "押金退还": f"{deposit:.0f}元（理想情况）",
            "条件": "房屋完好 + 到期前30天通知"
        }
        result["可能扣款项"] = {
            "墙面/家具损坏": "视情况赔偿",
            "清洁费": "通常100-300元",
            "水电燃气欠费": "据实结算",
            "物品丢失": "据实赔偿",
        }
        result["预估退还"] = f"{deposit * 0.8:.0f} ~ {deposit:.0f}元"
    else:
        # 提前退租
        result["提前退租"] = {
            "状态": "⚠️ 风险较高",
            "可能扣款": [
                f"违约金：通常1个月租金（{deposit:.0f}元）",
                "剩余租期租金损失（视合同条款）",
                "中介/房东的其他损失"
            ],
            "预估退还": f"0 ~ {deposit * 0.3:.0f}元（视合同条款）"
        }

    result["建议"] = [
        "退租前30天书面通知（留证据）",
        "入住时拍照留证",
        "提前和房东沟通，避免私下转租",
        "退房当天和房东一起验收，签署退房确认书"
    ]

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool(
    name="check_blacklist",
    description="查询黑中介/黑房东黑名单",
    params=[
        {"name": "name", "type": "string", "description": "中介/房东姓名或公司名"},
        {"name": "city", "type": "string", "description": "城市名"},
    ]
)
def check_blacklist(name: str, city: str = "") -> str:
    """查询黑名单"""
    from ..utils.db import Database
    db = Database()
    results = db.check_blacklist(name, city)

    if not results:
        return f"✅ 未在本地黑名单中找到「{name}」的相关记录\n\n" \
               f"注意：未在库 ≠ 完全可信，建议仍通过合同和沟通保护自己。"

    lines = [f"⚠️ 找到 {len(results)} 条相关记录:\n"]
    for r in results:
        lines.append(f"【{r['type']}】{r['name']}")
        lines.append(f"  城市: {r['city']}")
        lines.append(f"  原因: {r['reason']}")
        lines.append(f"  上报时间: {r['reported_at']}")
        lines.append("")
    return "\n".join(lines)


@tool(
    name="add_blacklist",
    description="匿名上报黑中介/黑房东",
    params=[
        {"name": "name", "type": "string", "description": "中介/房东姓名或公司名"},
        {"name": "type_", "type": "string", "description": "类型：中介/房东/二房东"},
        {"name": "reason", "type": "string", "description": "踩坑原因"},
        {"name": "city", "type": "string", "description": "城市"},
    ]
)
def add_blacklist(name: str, type_: str, reason: str, city: str) -> str:
    """匿名上报黑名单"""
    from ..utils.db import Database
    db = Database()
    db.add_blacklist_entry(name, type_, reason, city)
    return f"✅ 已匿名记录，感谢你的反馈！这将帮助其他人避坑。"


@tool(
    name="get_checklist",
    description="获取看房检查清单",
    params=[
        {"name": "phase", "type": "string", "description": "阶段：看房前/看房中/看房后"},
    ]
)
def get_checklist(phase: str = "看房中") -> str:
    """返回看房检查清单"""
    checklists = {
        "看房前": [
            "📋 准备物品：手机（拍照）、录音笔、卷尺、笔、本子",
            "📋 确认中介资质：营业执照、经纪人资格证",
            "📋 查房价位：同区域同户型近期成交价",
            "📋 确认证件：房东房产证、身份证（是否一致）",
            "📋 问清费用：租金、押金、付款方式、中介费、其他费用",
            "📋 问清条件：能否养宠、能否转租、能否装修",
        ],
        "看房中": [
            "🔌 水电：开关灯、开水龙头、试马桶、试热水器",
            "🔌 家电：空调/冰箱/洗衣机能否正常运行，遥控器是否匹配",
            "🚪 门窗：门锁是否好开、窗户是否漏风",
            "🧱 墙面：有无裂缝、潮湿、脱皮",
            "💧 排水：地漏是否堵、卫生间坡度是否够",
            "🔇 隔音：关窗后临街噪音如何、隔壁说话声是否明显",
            "☀️ 采光：上午/下午各看一次，注意朝向",
            "📶 网络：测试手机信号、WiFi速度",
            "🔢 记录：水电表底数（拍照）、家具数量",
            "📸 拍照：每个房间全景 + 细节（破损处）+ 窗外环境",
        ],
        "看房后": [
            "📊 对比同类房源：价格、配置、位置综合打分",
            "📊 核实房东身份：房产证+身份证+姓名是否一致",
            "📊 确认二房东风险：转租是否经过房东书面同意",
            "📊 检查小区环境：安保、垃圾处理、邻居情况",
            "📊 了解物业：物业费谁交、维修响应速度",
        ]
    }
    items = checklists.get(phase, checklists["看房中"])
    return f"## {phase}检查清单\n\n" + "\n".join(items)


@tool(
    name="review_contract",
    description="审查合同条款（本地规则引擎）",
    params=[
        {"name": "contract_text", "type": "string", "description": "合同文本内容"},
    ]
)
def review_contract(contract_text: str) -> str:
    """本地合同审查 - 关键词规则"""
    risks = []
    warnings = []
    city = "北京"  # TODO: 从用户配置获取

    contract_text_lower = contract_text.lower()

    # 高风险条款
    risk_patterns = [
        (r"押金概不退还", "🚨 押金不退条款 - 违法！押金必须据实结算后退还"),
        (r"提前(\d+)天.*通知.*违约金", "🚨 提前通知违约金过高"),
        (r"每天?.*滞纳金|日利率", "🚨 滞纳金条款 - 每日滞纳金可能违法"),
        (r"不得.*养宠|禁止养宠物", "⚠️ 禁养宠物 - 民法典保护饲主权利，此条款可能被判无效"),
        (r"单方.*解除|随时解除", "🚨 单方解除权 - 房东可随时解约的条款违法"),
        (r"第三方.*入住|不得留宿他人", "⚠️ 限制同住人 - 合理探访不受限"),
        (r"维修.*租客.*承担|设施.*租客负责", "⚠️ 维修责任转嫁 - 正常使用损坏应由房东维修"),
    ]

    for pattern, msg in risk_patterns:
        if re.search(pattern, contract_text):
            risks.append(msg)

    # 中风险
    warn_patterns = [
        (r"转租.*房东同意", "⚠️ 转租需房东书面同意，警惕二房东"),
        (r"押二|押金.*2个月", "⚠️ 押金2个月偏高，资金压力较大"),
        (r"中介费.*(一|1).*个月以上", "⚠️ 中介费偏高，正常为半个月到一个半月租金"),
        (r"水费.*电费.*[无上].*限", "⚠️ 水电费无上限可能导致账单失控"),
        (r"宽带.*网络.*自办|自装", "⚠️ 宽带自办理注意费用归属"),
    ]

    for pattern, msg in warn_patterns:
        if re.search(pattern, contract_text):
            warnings.append(msg)

    if not risks and not warnings:
        return "✅ 合同暂未发现明显违法条款\n\n" \
               "建议仍通过 AI 详细审查或人工核对标准合同。"

    result = "## 📋 合同风险审查结果\n\n"
    if risks:
        result += "### 🚨 高风险条款\n"
        for r in risks:
            result += f"- {r}\n"
        result += "\n"
    if warnings:
        result += "### ⚠️ 中风险条款\n"
        for w in warnings:
            result += f"- {w}\n"
        result += "\n"

    result += "### 💡 建议\n"
    result += "- 遇到高风险条款建议拒绝签署，或要求修改\n"
    result += "- 合同签字前务必仔细阅读，有疑问不签\n"
    result += "- 可要求房东提供房产证原件和身份证明\n"

    return result


@tool(
    name="generate_speech",
    description="生成'假装很懂'的沟通话术",
    params=[
        {"name": "situation", "type": "string", "description": "场景：问价格/问缺点/谈条件/退定金"},
    ]
)
def generate_speech(situation: str) -> str:
    """生成专业话术让用户显得懂行"""
    speeches = {
        "问价格": """中介/房东问价时，你可以这样说：

"您好，我看您这套房租金是 X 元/月，请问这个价格是实收还是含物业？我想确认一下除了租金之外，还有没有其他费用，比如中介费、服务费这些。另外，付款方式是怎么算的，押几付几？"

这样问显得你：✅ 了解市场行情 | ✅ 懂得问清全部费用 | ✅ 不是小白""",

        "问缺点": """主动问缺点显得专业：

"这套房我自己挺满意的，不过我想客观了解一下，这套房有没有什么比较明显的问题？比如朝向、噪音、装修老化之类的，我怕住进去才发现，影响生活。"

这样问显得你：✅ 看过很多房 | ✅ 理性决策 | ✅ 提前规避风险""",

        "谈条件": """谈租金或条件时：

"我看了一下，这套房我整体挺满意的。如果您能帮我把价格谈到 X 元/月，或者免掉中介费，我可以今天就签合同下定金，您看方便吗？另外我希望能加一条，如果工作调动需要提前退租，希望能配合我转租，这样双方都方便。"

这样谈显得你：✅ 有意向但有筹码 | ✅ 条件具体可执行 | ✅ 保护自己同时给对方台阶""",

        "退定金": """想退定金时：

"您好，关于定金的事我想跟您沟通一下。当时交定金的时候您说是可以退的，但后来我考虑到 XX 原因（户型/位置/工作变化），确实不适合签合同了。按照法律规定，定金退还需要双方协商，您这边能否考虑退还部分定金？我们可以好好谈。"

这样谈显得你：✅ 懂法律 | ✅ 态度诚恳但有底线 | ✅ 不容易被吓退""",
    }
    return speeches.get(situation, "请描述具体场景，可选：问价格、问缺点、谈条件、退定金")


@tool(
    name="city_rules",
    description="查询本地租房政策",
    params=[
        {"name": "city", "type": "string", "description": "城市名"},
        {"name": "topic", "type": "string", "description": "话题：居住证/押金/禁止事项/群租"},
    ]
)
def city_rules(city: str = "北京", topic: str = "押金") -> str:
    """查询城市租房政策"""
    rules = {
        "北京": {
            "居住证": "北京居住证需租房满6个月可申请，与积分落户挂钩",
            "押金": "押金通常为1个月租金，不得高于2个月，押金收据必须留存",
            "禁止事项": "不得改变房屋结构，不得从事经营活动，不得留宿他人超过限制人数",
            "群租": '明确禁止"隔断房"（N+1/N+2模式），发现可举报拆除',
            "二房东": "转租需经房东书面同意，否则房东可解除合同",
        },
        "上海": {
            "居住证": "租房可办理上海居住证，与子女入学、公积金提取相关",
            "押金": "押金通常为1-2个月，押金条款应明确约定退还条件和时间",
            "禁止事项": '禁止"群租"，人均居住面积不得低于5平方米',
            "群租": "人均使用面积不低于5平方米，违反可被强制整改",
            "二房东": "正规二房东（长租公寓）有平台保障，个人转租风险较高",
        },
        "深圳": {
            "居住证": "深圳居住证与社保挂钩，换工作注意续办",
            "押金": "押金通常为1-2个月，押金退还争议可向街道办调解",
            "禁止事项": "不得改变房屋结构，消防安全隐患需整改",
            "群租": '深圳对"胶囊房""背包房"整治力度大',
            "二房东": "城中村二房东普遍存在，签署合同前核实房东身份",
        },
    }
    city_rules = rules.get(city, rules["北京"])
    result = f"## 🏙️ {city} 租房政策\n\n"
    for key, value in city_rules.items():
        result += f"### {key}\n{value}\n\n"
    return result


@tool(
    name="calc_commute",
    description="估算通勤时间（简单估算）",
    params=[
        {"name": "distance_km", "type": "number", "description": "直线距离（公里）"},
        {"name": "method", "type": "string", "description": "出行方式：地铁/公交/骑行/驾车"},
    ]
)
def calc_commute(distance_km: float, method: str = "地铁") -> str:
    """粗略估算通勤时间"""
    speeds = {"地铁": 35, "公交": 20, "骑行": 15, "驾车": 30}
    speed = speeds.get(method, 30)
    time_min = (distance_km / speed) * 60

    if time_min <= 20:
        level = "✅ 优秀"
    elif time_min <= 40:
        level = "🟡 正常"
    elif time_min <= 60:
        level = "🟠 较长"
    else:
        level = "🔴 过长，建议慎重考虑"

    return f"## 🚇 通勤估算\n\n" \
           f"- 距离: {distance_km} km\n" \
           f"- 方式: {method}\n" \
           f"- 预计耗时: 约 {time_min:.0f} 分钟（单程）\n" \
           f"- 评价: {level}\n" \
           f"- 往返: 约 {time_min * 2:.0f} 分钟/天\n\n" \
           f"注：实际通勤取决于具体路线，换乘和步行会增加时间"


def get_all_tools() -> list:
    """获取所有工具"""
    return TOOLS


def get_tool_by_name(name: str):
    """按名称获取工具函数"""
    for t in TOOLS:
        if t._tool_meta["name"] == name:
            return t
    return None


def get_tools_description() -> str:
    """获取工具描述文本（用于给LLM）"""
    lines = ["你可使用以下工具："]
    for t in TOOLS:
        meta = t._tool_meta
        params_str = ", ".join([f"{p['name']}: {p['type']}" for p in meta["params"]])
        lines.append(f"- {meta['name']}({params_str}): {meta['description']}")
    return "\n".join(lines)
