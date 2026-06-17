"""
合同风险评分引擎 — ContractReviewer
三层扫描：规则引擎(80条) + 标准合同对比 + AI 深度审查 + 谈判话术
"""
import json
import logging
import pathlib
from typing import Any

from .contract_parser import ContractParser
from .llm import LLM

logger = logging.getLogger(__name__)

_SRC_DIR = pathlib.Path(__file__).parent.parent
_STANDARD_CONTRACT = _SRC_DIR / "data" / "standard_contract.json"
_CITY_RULES = _SRC_DIR / "data" / "city_rules.json"


def _load_json(path: pathlib.Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
        text = text.strip()
        if text.startswith('"""'):
            end = text.find('"""', 3)
            if end != -1:
                text = text[end + 3:].strip()
        return json.loads(text)
    except Exception as e:
        logger.warning("加载 JSON 失败 %s: %s", path, e)
        return {}


def _get_city_rules(city: str = "北京") -> dict:
    all_rules = _load_json(_CITY_RULES)
    return all_rules.get(city, {})


def _is_real_id_card(id_str: str | None) -> bool:
    if not id_str:
        return False
    return len(id_str) == 18 and id_str[:4] != "*" and id_str[-4:] != "*" * 4


def _mask_id(id_str: str) -> str:
    if not id_str or len(id_str) < 18:
        return id_str or ""
    return id_str[:4] + "**********" + id_str[-4:]


def _detect_city_from_address(address: str | None) -> str:
    if not address:
        return "北京"
    for city in ["北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "南京"]:
        if city in address:
            return city
    return "北京"


def re_search_check(pattern: str, text: str) -> bool:
    import re
    if not text:
        return False
    try:
        return bool(re.search(pattern, text))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 规则定义
# ---------------------------------------------------------------------------

def _build_rules() -> list[dict]:
    rules = []

    # ========== A. 费用类（15条） ==========
    rules.extend([
        {"id": "A01", "category": "费用", "level": "high",
         "title": "押金超过3个月租金",
         "check": lambda c: (c["financial"]["monthly_rent"] and c["financial"]["deposit"] and c["financial"]["deposit"] > c["financial"]["monthly_rent"] * 3),
         "suggestion": "押金建议不超过1个月租金，超过部分可协商退还",
         "legal_basis": "《民法典》第四百七十条：合同条款不得违反公平原则"},
        {"id": "A02", "category": "费用", "level": "medium",
         "title": "押金超过1个月且无退还约定",
         "check": lambda c: (c["financial"]["monthly_rent"] and c["financial"]["deposit"] and 1 < c["financial"]["deposit"] / c["financial"]["monthly_rent"] <= 3),
         "suggestion": "押金退还条件应在合同中明确约定",
         "legal_basis": "《民法典》第七百二十条"},
        {"id": "A03", "category": "费用", "level": "high",
         "title": "中介费超过1个月租金",
         "check": lambda c: (c["financial"]["agent_fee"] and c["financial"]["monthly_rent"] and c["financial"]["agent_fee"] > c["financial"]["monthly_rent"]),
         "suggestion": "中介费建议不超过0.5-1个月租金",
         "legal_basis": "中介费属于市场定价，一般不超过半个月到一个月租金"},
        {"id": "A04", "category": "费用", "level": "medium",
         "title": "存在隐性费用",
         "check": lambda c: len(c["financial"]["other_fees"]) > 2,
         "suggestion": "要求列明所有费用项目，拒绝任何未在合同中注明的收费",
         "legal_basis": "《民法典》第四百九十六条"},
        {"id": "A05", "category": "费用", "level": "high",
         "title": "水电费按商用标准收费",
         "check": lambda c: (c["financial"]["utility_responsibility"] and any(k in c["financial"]["utility_responsibility"] for k in ["商水", "商电", "商用"])),
         "suggestion": "住宅用房应按民用标准缴纳水电费",
         "legal_basis": "民用与商用水电价差可达2-3倍"},
        {"id": "A06", "category": "费用", "level": "medium",
         "title": "付款周期过长（付6个月以上）",
         "check": lambda c: (c["financial"]["payment_cycle"] and re_search_check(r"付\s*[六七八九十]", c["financial"]["payment_cycle"])),
         "suggestion": "建议缩短付款周期，降低一次性资金压力",
         "legal_basis": "一次性支付过长期限租金存在资金安全隐患"},
        {"id": "A07", "category": "费用", "level": "medium",
         "title": "付款周期为押二付三及以上",
         "check": lambda c: (c["financial"]["payment_cycle"] and re_search_check(r"押\s*[二三四五六]", c["financial"]["payment_cycle"])),
         "suggestion": "押金超过1个月对租客不利，建议谈判为押一付三",
         "legal_basis": "押二付三属于偏苛刻条款"},
        {"id": "A08", "category": "费用", "level": "medium",
         "title": "押金退还条件不明确",
         "check": lambda c: (c["financial"]["deposit"] and not re_search_check(r"退还|结算|退回", str(c.get("_raw_clauses", "")))),
         "suggestion": "合同应明确押金退还的时间、条件",
         "legal_basis": "《民法典》第三百二十一条"},
        {"id": "A09", "category": "费用", "level": "low",
         "title": "物业费由租客承担且金额未注明",
         "check": lambda c: (c["financial"]["property_fee"] is None and c["financial"]["utility_responsibility"] and any(k in c["financial"]["utility_responsibility"] for k in ["物业", "取暖"])),
         "suggestion": "明确物业费金额及承担方",
         "legal_basis": "物业费属于可以预见的日常支出"},
        {"id": "A10", "category": "费用", "level": "medium",
         "title": "存在预付租金不可退还条款",
         "check": lambda c: re_search_check(r"预付.*不退|预付.*不还", str(c.get("_raw_clauses", ""))),
         "suggestion": "预付款退还规则应当公平",
         "legal_basis": "《民法典》第四百九十七条"},
        {"id": "A11", "category": "费用", "level": "medium",
         "title": "租金包含不明费用",
         "check": lambda c: (c["financial"]["monthly_rent"] and re_search_check(r"包含.*管理费|包含.*服务费", str(c.get("_raw_clauses", "")))),
         "suggestion": "要求明确租金构成",
         "legal_basis": "费用透明是诚实信用原则的基本要求"},
        {"id": "A12", "category": "费用", "level": "low",
         "title": "水电费未约定结算周期",
         "check": lambda c: (c["financial"]["utility_responsibility"] and not re_search_check(r"抄表|结算|月底|月初|每.*月", c["financial"]["utility_responsibility"])),
         "suggestion": "约定水电费抄表周期和结算方式",
         "legal_basis": "明确结算周期有利于减少纠纷"},
        {"id": "A13", "category": "费用", "level": "medium",
         "title": "押金分月抵扣但无明确说明",
         "check": lambda c: re_search_check(r"押金.*抵扣|分月.*押金", str(c.get("_raw_clauses", ""))),
         "suggestion": "押金抵扣最后一期租金的方式需明确抵扣金额和条件",
         "legal_basis": "押金抵扣租金需双方明确约定"},
        {"id": "A14", "category": "费用", "level": "low",
         "title": "付款日期约定模糊",
         "check": lambda c: c["financial"]["payment_date"] is None,
         "suggestion": "明确每月几号前支付租金",
         "legal_basis": "付款期限不明确可能导致争议"},
        {"id": "A15", "category": "费用", "level": "medium",
         "title": "存在POS机手续费或其他附加收费",
         "check": lambda c: re_search_check(r"手续费|POS|附加费|服务费", str(c.get("_raw_clauses", ""))),
         "suggestion": "要求通过银行转账支付，保留凭证",
         "legal_basis": "任何附加收费都应在合同中明确告知"},
    ])

    # ========== B. 期限类（10条） ==========
    rules.extend([
        {"id": "B01", "category": "期限", "level": "medium",
         "title": "租期不足半年",
         "check": lambda c: (c["term"]["duration_months"] is not None and c["term"]["duration_months"] < 6),
         "suggestion": "短租可能导致续约困难，建议签约至少6个月",
         "legal_basis": "短期租约中房东可能不愿承担维修义务"},
        {"id": "B02", "category": "期限", "level": "medium",
         "title": "无续租条款",
         "check": lambda c: (c["term"]["duration_months"] and c["term"]["renewal_clause"] is None),
         "suggestion": "合同应包含续租条款",
         "legal_basis": "《民法典》第七百三十条"},
        {"id": "B03", "category": "期限", "level": "high",
         "title": "自动续租陷阱",
         "check": lambda c: re_search_check(r"自动续租|到期未提出.*视为|未通知.*续租", str(c.get("_raw_clauses", ""))),
         "suggestion": "警惕自动续租条款，应明确约定需双方书面确认才续约",
         "legal_basis": "《民法典》第七百三十四条"},
        {"id": "B04", "category": "期限", "level": "high",
         "title": "租期超过3年且无上限约定",
         "check": lambda c: (c["term"]["duration_months"] and c["term"]["duration_months"] > 36),
         "suggestion": "超长租约对双方均有风险，建议分阶段签约",
         "legal_basis": "《民法典》第七百零五条"},
        {"id": "B05", "category": "期限", "level": "medium",
         "title": "起租日期不明确",
         "check": lambda c: c["term"]["start_date"] is None,
         "suggestion": "起租日期必须明确",
         "legal_basis": "起租日期是计算租金和租期的基准"},
        {"id": "B06", "category": "期限", "level": "medium",
         "title": "无租期上限保障",
         "check": lambda c: c["term"]["end_date"] is None,
         "suggestion": "必须明确租赁终止日期",
         "legal_basis": "不定期租赁，任何一方可随时解除合同"},
        {"id": "B07", "category": "期限", "level": "medium",
         "title": "提前通知期限过短",
         "check": lambda c: (c["clauses"]["early_termination"]["text"] and re_search_check(r"提前\s*[56789]|提前\s*1周|提前\s*10天", c["clauses"]["early_termination"]["text"])),
         "suggestion": "提前退租通知期建议至少30天",
         "legal_basis": "一般惯例为提前30天书面通知"},
        {"id": "B08", "category": "期限", "level": "low",
         "title": "未约定装修免租期",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"免租|装修期|改造期", c["clauses"]["decoration"]["text"]) is False),
         "suggestion": "如果涉及装修入住，可协商争取3-7天免租期",
         "legal_basis": "装修免租期属于合理商业安排"},
        {"id": "B09", "category": "期限", "level": "low",
         "title": "未明确入住日期与起租日关系",
         "check": lambda c: (c["term"]["start_date"] and not re_search_check(r"入住|交付|钥匙", str(c.get("_raw_clauses", "")))),
         "suggestion": "明确入住钥匙交付日期与起租日期的关系",
         "legal_basis": "避免起租日期早于实际入住日期造成的租金损失"},
        {"id": "B10", "category": "期限", "level": "medium",
         "title": "租期覆盖特殊期间无特别约定",
         "check": lambda c: (c["term"]["start_date"] and c["term"]["end_date"] and re_search_check(r"寒暑假|春节期间", c["term"]["start_date"] + c["term"]["end_date"])),
         "suggestion": "特殊期间租约应有特别约定",
         "legal_basis": "特殊期间租赁双方权益保护应有所区别"},
    ])

    # ========== C. 违约类（12条） ==========
    rules.extend([
        {"id": "C01", "category": "违约", "level": "high",
         "title": "提前退租押金全扣",
         "check": lambda c: re_search_check(r"押金不予退还|押金全扣|押金不退", str(c.get("_raw_clauses", ""))),
         "suggestion": "押金全扣条款过于苛刻，正常情况下押金应据实结算后退还",
         "legal_basis": "《民法典》第五百八十五条"},
        {"id": "C02", "category": "违约", "level": "high",
         "title": "违约金超过2个月租金",
         "check": lambda c: (c["clauses"]["default_penalty"]["amount"] and c["financial"]["monthly_rent"] and c["clauses"]["default_penalty"]["amount"] > c["financial"]["monthly_rent"] * 2),
         "suggestion": "违约金一般不超过1-2个月租金",
         "legal_basis": "《民法典》第五百八十五条"},
        {"id": "C03", "category": "违约", "level": "medium",
         "title": "单方解约权不对等",
         "check": lambda c: (re_search_check(r"甲方.*随时|房东.*随时解|出租方.*单方", str(c.get("_raw_clauses", ""))) and not re_search_check(r"乙方.*同等", str(c.get("_raw_clauses", "")))),
         "suggestion": "解约权应对等",
         "legal_basis": "《民法典》第七百二十九条"},
        {"id": "C04", "category": "违约", "level": "high",
         "title": "滞纳金日利率过高",
         "check": lambda c: re_search_check(r"日利率|每日\s*[%％]\s*[5-9]|每日\s*[0-9]\d", str(c.get("_raw_clauses", ""))),
         "suggestion": "滞纳金日利率不应超过万分之五",
         "legal_basis": "民间借贷利率上限为LPR的4倍"},
        {"id": "C05", "category": "违约", "level": "medium",
         "title": "房东有权进入房屋无通知",
         "check": lambda c: re_search_check(r"随时进入|随时查看|不经通知|无需通知", str(c.get("_raw_clauses", ""))),
         "suggestion": "房东进入房屋应提前通知",
         "legal_basis": "《民法典》第一千零三十三条"},
        {"id": "C06", "category": "违约", "level": "medium",
         "title": "租客违约成本显著高于房东",
         "check": lambda c: (re_search_check(r"乙方.*违约金|承租人.*违约金", str(c.get("_raw_clauses", ""))) and not re_search_check(r"甲方.*违约金|出租人.*违约金", str(c.get("_raw_clauses", "")))),
         "suggestion": "双方违约责任应对等",
         "legal_basis": "《民法典》第四条"},
        {"id": "C07", "category": "违约", "level": "medium",
         "title": "逾期搬离每日罚款",
         "check": lambda c: re_search_check(r"逾期.*搬离.*每日|超期.*每天.*赔偿", str(c.get("_raw_clauses", ""))),
         "suggestion": "逾期搬离应有合理期限",
         "legal_basis": "超出合理期限的持续性罚款可能被认定为无效"},
        {"id": "C08", "category": "违约", "level": "medium",
         "title": "违约情形定义过于宽泛",
         "check": lambda c: (re_search_check(r"甲方认为|房东认为.*违约", str(c.get("_raw_clauses", ""))) and not re_search_check(r"客观标准|法定情形", str(c.get("_raw_clauses", "")))),
         "suggestion": "违约情形应有客观标准",
         "legal_basis": "违约条款的确定性是合同有效性的要求"},
        {"id": "C09", "category": "违约", "level": "medium",
         "title": "提前退租需赔偿装修损失",
         "check": lambda c: (c["clauses"]["early_termination"]["text"] and re_search_check(r"装修.*赔偿|恢复.*原状", c["clauses"]["early_termination"]["text"])),
         "suggestion": "装修赔偿应有折旧计算方式",
         "legal_basis": "装修折旧按使用年限摊销是合理方式"},
        {"id": "C10", "category": "违约", "level": "low",
         "title": "无解约违约金上限",
         "check": lambda c: (c["clauses"]["default_penalty"]["text"] and not re_search_check(r"不超过|最高|上限", c["clauses"]["default_penalty"]["text"])),
         "suggestion": "违约金应有明确上限",
         "legal_basis": "违约金兼具补偿性和惩罚性，过高部分不受法律保护"},
        {"id": "C11", "category": "违约", "level": "medium",
         "title": "拖欠租金即可解除合同无缓冲期",
         "check": lambda c: re_search_check(r"拖欠租金.*解除|未按时.*解除合同", str(c.get("_raw_clauses", ""))),
         "suggestion": "应给予租客一定缓冲期和补正机会",
         "legal_basis": "合同解除应有合理催告期"},
        {"id": "C12", "category": "违约", "level": "medium",
         "title": "房东违约但无对应惩罚",
         "check": lambda c: (re_search_check(r"乙方.*违约|承租人.*违约", str(c.get("_raw_clauses", ""))) and not re_search_check(r"甲方.*违约|房东.*违约|出租人.*违约", str(c.get("_raw_clauses", "")))),
         "suggestion": "合同应同时约束双方",
         "legal_basis": "《民法典》合同编遵循平等原则"},
    ])

    # ========== D. 维修类（8条） ==========
    rules.extend([
        {"id": "D01", "category": "维修", "level": "high",
         "title": "所有维修责任全部推给租客",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and re_search_check(r"均由.*乙方|全部.*承租人|一切.*维修", c["clauses"]["maintenance"]["text"])),
         "suggestion": "自然损耗和房屋结构问题应由房东承担",
         "legal_basis": "《民法典》第七百一十二条"},
        {"id": "D02", "category": "维修", "level": "high",
         "title": "自然损耗由租客承担",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and re_search_check(r"自然损耗|自然老化|正常使用.*损耗", c["clauses"]["maintenance"]["text"]) and re_search_check(r"承租人|乙方.*承担", c["clauses"]["maintenance"]["text"])),
         "suggestion": "自然损耗应由房东负责，租客只承担人为损坏的维修",
         "legal_basis": "《民法典》第七百一十三条"},
        {"id": "D03", "category": "维修", "level": "medium",
         "title": "家电维修责任不清",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and re_search_check(r"家电|电器|家具|设备", c["clauses"]["maintenance"]["text"]) is False),
         "suggestion": "合同应明确家电、家具的维修责任归属",
         "legal_basis": "家电维修责任不明确是常见纠纷来源"},
        {"id": "D04", "category": "维修", "level": "medium",
         "title": "未约定维修响应时间",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and not re_search_check(r"\d+小时|\d+天内?|尽快|及时", c["clauses"]["maintenance"]["text"])),
         "suggestion": "应约定房东维修响应时间",
         "legal_basis": "维修及时性影响租客正常使用权利"},
        {"id": "D05", "category": "维修", "level": "medium",
         "title": "装修折旧计算方式不公",
         "check": lambda c: re_search_check(r"折旧.*按月|每月.*折旧|装修.*折旧", str(c.get("_raw_clauses", ""))),
         "suggestion": "装修折旧应按年计算",
         "legal_basis": "装修折旧年限应参照房屋法定使用年限"},
        {"id": "D06", "category": "维修", "level": "medium",
         "title": "紧急维修定义和费用分担不明确",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and not re_search_check(r"紧急|突发|应急", c["clauses"]["maintenance"]["text"])),
         "suggestion": "紧急情况应有快速处理机制和费用分担规则",
         "legal_basis": "紧急维修关乎居住安全"},
        {"id": "D07", "category": "维修", "level": "low",
         "title": "未约定押金退还时的房屋验收标准",
         "check": lambda c: (not c["clauses"]["inspection"]["has_clause"] and c["financial"]["deposit"]),
         "suggestion": "退租验收标准应事先约定",
         "legal_basis": "验收标准不明是押金纠纷的主要原因"},
        {"id": "D08", "category": "维修", "level": "low",
         "title": "下水道/管道堵塞责任归属不明",
         "check": lambda c: (c["clauses"]["maintenance"]["text"] and re_search_check(r"管道|下水道|排水|马桶|堵塞", c["clauses"]["maintenance"]["text"]) is False),
         "suggestion": "管道堵塞应区分人为原因和自然老化",
         "legal_basis": "管道维修责任应事先约定"},
    ])

    # ========== E. 装修/改造类（8条） ==========
    rules.extend([
        {"id": "E01", "category": "装修", "level": "high",
         "title": "完全禁止装修（不合理）",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"不得.*装修|禁止.*装修|不允许.*改造", c["clauses"]["decoration"]["text"]) and c["clauses"]["decoration"]["allowed"] is False),
         "suggestion": "轻微装修通常应为租客所允许",
         "legal_basis": "合理装修属于承租人的正常使用权能"},
        {"id": "E02", "category": "装修", "level": "medium",
         "title": "装修折旧赔偿模糊",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"恢复原状|赔偿.*装修", c["clauses"]["decoration"]["text"]) and not re_search_check(r"折旧|使用年限|年限摊销", c["clauses"]["decoration"]["text"])),
         "suggestion": "装修赔偿应有折旧计算",
         "legal_basis": "装修按使用年限折旧是通行做法"},
        {"id": "E03", "category": "装修", "level": "medium",
         "title": "恢复原状要求过严",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"恢复原状|恢复.*原样", c["clauses"]["decoration"]["text"]) and re_search_check(r"全部|所有|完全", c["clauses"]["decoration"]["text"])),
         "suggestion": "要求恢复所有装修对租客不公平",
         "legal_basis": "合理使用产生的痕迹不应要求恢复"},
        {"id": "E04", "category": "装修", "level": "medium",
         "title": "改造需房东书面同意但无具体标准",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"书面同意|经.*同意", c["clauses"]["decoration"]["text"]) and not re_search_check(r"具体|标准|范围", c["clauses"]["decoration"]["text"])),
         "suggestion": "装修同意标准应具体明确",
         "legal_basis": "同意权的行使不应过于随意"},
        {"id": "E05", "category": "装修", "level": "medium",
         "title": "打墙/结构改造未明确禁止",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"打墙|拆墙|结构.*改造|改变.*布局", c["clauses"]["decoration"]["text"]) is False),
         "suggestion": "涉及建筑结构的改动必须有明确书面授权",
         "legal_basis": "擅自改变房屋结构违反物业管理规定"},
        {"id": "E06", "category": "装修", "level": "low",
         "title": "装修期间租金减免未约定",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"装修|改造", c["clauses"]["decoration"]["text"]) and c["term"]["duration_months"] and c["term"]["duration_months"] <= 3),
         "suggestion": "若需装修入住，建议争取3-7天装修免租期",
         "legal_basis": "装修期间无法正常使用房屋，应减免相应租金"},
        {"id": "E07", "category": "装修", "level": "medium",
         "title": "空调/热水器安装权受限",
         "check": lambda c: (c["clauses"]["decoration"]["text"] and re_search_check(r"不得.*安装|禁止.*挂|不允许.*空调", c["clauses"]["decoration"]["text"])),
         "suggestion": "基本生活设施安装权不应被剥夺",
         "legal_basis": "租赁目的为居住，基本生活设施安装属于合理需求"},
        {"id": "E08", "category": "装修", "level": "low",
         "title": "宠物/饲养宠物未约定",
         "check": lambda c: (not re_search_check(r"宠物|养.*动物|养猫|养狗", str(c.get("_raw_clauses", ""))) and c["property"]["furniture"] and len(c["property"]["furniture"]) > 3),
         "suggestion": "若有饲养宠物计划，应在签约时明确是否允许",
         "legal_basis": "宠物问题易引发纠纷，应事先约定"},
    ])

    # ========== F. 权属类（10条） ==========
    rules.extend([
        {"id": "F01", "category": "权属", "level": "high",
         "title": "房东身份不明",
         "check": lambda c: (c["parties"]["landlord_name"] and not _is_real_id_card(c["parties"].get("landlord_id"))),
         "suggestion": "签约前应核实房东身份（身份证+房产证）",
         "legal_basis": "核实房东身份是防范二房东的基本手段"},
        {"id": "F02", "category": "权属", "level": "high",
         "title": "疑似二房东无转租权证明",
         "check": lambda c: (c["parties"]["agent_name"] and not re_search_check(r"原房东|产权人|所有权人|委托.*出租", str(c.get("_raw_clauses", "")))),
         "suggestion": "要求二房东提供原房东的书面转租授权",
         "legal_basis": "无转租权的二房东签约，房东可解除合同"},
        {"id": "F03", "category": "权属", "level": "high",
         "title": "无房产证核验",
         "check": lambda c: (c["property"]["address"] and not re_search_check(r"房产证|产权证|不动产证|房屋所有权", str(c.get("_raw_clauses", "")))),
         "suggestion": "要求房东出示房产证原件",
         "legal_basis": "无房产证核验可能遭遇无权出租"},
        {"id": "F04", "category": "权属", "level": "high",
         "title": "房屋处于抵押状态未告知",
         "check": lambda c: re_search_check(r"抵押|已抵押|查封|被查封|限制.*登记", str(c.get("_raw_clauses", ""))),
         "suggestion": "抵押房可能被银行执行",
         "legal_basis": "《民法典》第四百零一条"},
        {"id": "F05", "category": "权属", "level": "medium",
         "title": "转租限制过于严格",
         "check": lambda c: (c["clauses"]["sublease"]["text"] and c["clauses"]["sublease"]["allowed"] is False),
         "suggestion": "紧急情况下的临时转租应有例外约定",
         "legal_basis": "完全禁止转租在某些情况下可能无效"},
        {"id": "F06", "category": "权属", "level": "medium",
         "title": "共有房屋未经全体共有人同意",
         "check": lambda c: re_search_check(r"共有|共同所有|联名", str(c.get("_raw_clauses", ""))),
         "suggestion": "共有房屋出租需全体共有人同意",
         "legal_basis": "《民法典》第三百零一条"},
        {"id": "F07", "category": "权属", "level": "medium",
         "title": "商业用途房屋按住宅租金签订",
         "check": lambda c: (c["property"]["address"] and re_search_check(r"商住|商业|办公|注册|公司地址", c["property"]["address"]) is False and c["financial"]["monthly_rent"] and c["financial"]["monthly_rent"] > 10000),
         "suggestion": "高价租赁要核实用途是否为商业",
         "legal_basis": "住宅改商用需符合城市规划要求"},
        {"id": "F08", "category": "权属", "level": "medium",
         "title": "小产权房或违建房屋",
         "check": lambda c: (c["property"]["address"] and any(k in c["property"]["address"] for k in ["小产权", "违建", "违章"])),
         "suggestion": "小产权房和违建无法办理合法租赁登记",
         "legal_basis": "小产权房租赁不受法律保护"},
        {"id": "F09", "category": "权属", "level": "medium",
         "title": "未要求留存房东联系方式",
         "check": lambda c: (c["parties"]["landlord_name"] and not re_search_check(r"电话|手机|联系方式|微信", str(c.get("_raw_clauses", "")))),
         "suggestion": "合同中应留存房东有效联系方式",
         "legal_basis": "紧急情况下及时联系房东是基本保障"},
        {"id": "F10", "category": "权属", "level": "low",
         "title": "房屋用途变更未通知",
         "check": lambda c: (c["property"]["type"] and re_search_check(r"商用|办公|注册地址|经营", c["property"]["type"])),
         "suggestion": "商用房屋应确认是否在物业允许的经营范围内",
         "legal_basis": "擅自改变房屋用途违反物业管理规约"},
    ])

    # ========== G. 附属类（9条） ==========
    rules.extend([
        {"id": "G01", "category": "附属", "level": "high",
         "title": "无家具清单",
         "check": lambda c: (c["financial"]["deposit"] and c["property"]["furniture"] and len(c["property"]["furniture"]) == 0),
         "suggestion": "有押金的情况下必须有家具清单",
         "legal_basis": "无清单的押金退还纠纷难以举证"},
        {"id": "G02", "category": "附属", "level": "high",
         "title": "无入住查验记录",
         "check": lambda c: not c["clauses"]["inspection"]["has_clause"],
         "suggestion": "入住前必须做房屋查验并记录",
         "legal_basis": "入住查验是避免退租争议的关键证据"},
        {"id": "G03", "category": "附属", "level": "medium",
         "title": "退租验收标准缺失",
         "check": lambda c: (not c["clauses"]["inspection"]["has_clause"] and c["financial"]["deposit"]),
         "suggestion": "退租验收标准应在合同中明确",
         "legal_basis": "验收标准不明导致押金扣除争议"},
        {"id": "G04", "category": "附属", "level": "medium",
         "title": "钥匙/门禁未交接",
         "check": lambda c: not re_search_check(r"钥匙|门禁|门卡|门锁", str(c.get("_raw_clauses", ""))),
         "suggestion": "钥匙、门禁卡数量应明确约定",
         "legal_basis": "钥匙交接是租赁关系成立的基本要件"},
        {"id": "G05", "category": "附属", "level": "medium",
         "title": "车位/仓库等附属设施未约定",
         "check": lambda c: (c["property"]["address"] and re_search_check(r"车位|车库|仓库|储物", c["property"]["address"]) and not re_search_check(r"车位.*归属|车位.*使用|免费|包含", str(c.get("_raw_clauses", "")))),
         "suggestion": "配套设施的使用权和费用应有明确约定",
         "legal_basis": "附属设施使用规则应事先明确"},
        {"id": "G06", "category": "附属", "level": "low",
         "title": "宽带/网络未约定",
         "check": lambda c: (c["term"]["duration_months"] and c["term"]["duration_months"] >= 6 and not re_search_check(r"宽带|网络|光纤|网络费", str(c.get("_raw_clauses", "")))),
         "suggestion": "宽带安装和费用归属应提前确认",
         "legal_basis": "网络是基本生活需求"},
        {"id": "G07", "category": "附属", "level": "low",
         "title": "宠物规定缺失",
         "check": lambda c: (not re_search_check(r"宠物|养宠|动物", str(c.get("_raw_clauses", ""))) and c["property"]["furniture"] and len(c["property"]["furniture"]) > 3),
         "suggestion": "是否允许养宠物应在合同中明确",
         "legal_basis": "宠物纠纷是租客被驱逐的常见原因"},
        {"id": "G08", "category": "附属", "level": "low",
         "title": "快递收发地址未说明",
         "check": lambda c: (c["property"]["type"] and re_search_check(r"公寓|酒店式|商住", c["property"]["type"]) and not re_search_check(r"快递|收发|代收", str(c.get("_raw_clauses", "")))),
         "suggestion": "公寓类租赁应确认快递收发规则",
         "legal_basis": "快递收发属于日常便利服务"},
        {"id": "G09", "category": "附属", "level": "low",
         "title": "物业费缴纳方式未明确",
         "check": lambda c: (c["financial"]["property_fee"] and not re_search_check(r"租客.*缴纳|房东.*缴纳|含.*物业|物业.*包含", str(c.get("_raw_clauses", "")))),
         "suggestion": "物业费由谁承担、怎么缴应明确",
         "legal_basis": "物业费是固定支出，事先约定可避免扯皮"},
    ])

    return rules


def _build_city_rules_for_city(city: str) -> list[dict]:
    rules = []
    city_data = _get_city_rules(city)

    rules.extend([
        {"id": "H01", "category": "城市政策", "level": "high",
         "title": f"{city}押金超过当地建议上限",
         "check": lambda c: (city == "北京" and c["financial"]["monthly_rent"] and c["financial"]["deposit"] and c["financial"]["deposit"] > c["financial"]["monthly_rent"] * 2),
         "suggestion": city_data.get("押金上限", "押金建议不超过2个月租金"),
         "legal_basis": f"{city}市住房租赁相关规定"},
        {"id": "H02", "category": "城市政策", "level": "high",
         "title": f"{city}单次收租周期过长",
         "check": lambda c: (city in ["北京", "上海"] and c["financial"]["payment_cycle"] and re_search_check(r"付\s*[六七八九十]", c["financial"]["payment_cycle"])),
         "suggestion": f"{city}市中介房源单次收租不应超过3个月",
         "legal_basis": f"{city}市住房租赁资金监管规定"},
        {"id": "H03", "category": "城市政策", "level": "medium",
         "title": f"{city}群租/隔断房风险",
         "check": lambda c: (city in ["北京", "上海", "深圳"] and c["property"]["address"] and any(k in c["property"]["address"] for k in ["隔断", "群租", "N+1", "胶囊"])),
         "suggestion": city_data.get("禁止事项", "该城市对隔断房/群租有整治行动"),
         "legal_basis": "违建整治相关规定"},
        {"id": "H04", "category": "城市政策", "level": "medium",
         "title": f"{city}二房东转租权未核实",
         "check": lambda c: (city in ["北京", "上海", "深圳", "广州"] and c["clauses"]["sublease"]["text"] and not re_search_check(r"书面同意|授权|有权转租", c["clauses"]["sublease"]["text"])),
         "suggestion": city_data.get("二房东", "转租需房东书面同意"),
         "legal_basis": f"{city}市住房租赁管理规定"},
        {"id": "H05", "category": "城市政策", "level": "medium",
         "title": f"{city}人均居住面积不达标",
         "check": lambda c: (city in ["上海", "深圳"] and c["property"]["area"] and c["property"]["area"] < 5),
         "suggestion": city_data.get("禁止事项", "人均居住面积不得低于5平方米"),
         "legal_basis": f"{city}市居住房屋租赁管理办法"},
        {"id": "H06", "category": "城市政策", "level": "low",
         "title": f"{city}公积金租房提取未办理",
         "check": lambda c: (city in ["北京", "上海", "深圳", "广州", "杭州"] and c["term"]["duration_months"] and c["term"]["duration_months"] >= 3),
         "suggestion": city_data.get("公积金提取", "租房可提取公积金"),
         "legal_basis": f"{city}市住房公积金提取管理办法"},
        {"id": "H07", "category": "城市政策", "level": "medium",
         "title": f"{city}租售同权权益未主张",
         "check": lambda c: (city == "深圳" and c["term"]["duration_months"] and c["term"]["duration_months"] >= 6 and not re_search_check(r"居住证|租赁登记|备案", str(c.get("_raw_clauses", "")))),
         "suggestion": "深圳租房满6个月可申请居住证",
         "legal_basis": f"{city}市居住证申领和签注规定"},
        {"id": "H08", "category": "城市政策", "level": "low",
         "title": f"{city}居住证办理条件未在合同中体现",
         "check": lambda c: (city in ["北京", "上海", "深圳", "广州", "杭州"] and c["term"]["duration_months"] and c["term"]["duration_months"] >= 6 and not re_search_check(r"配合办理|协助.*居住证|居住证.*办理", str(c.get("_raw_clauses", "")))),
         "suggestion": f"{city}租房满6个月可申请居住证，合同中应约定房东配合义务",
         "legal_basis": f"{city}市流动人口居住登记和居住证办理规定"},
    ])
    return rules


# ---------------------------------------------------------------------------
# 标准合同对比
# ---------------------------------------------------------------------------

def _load_standard_contract() -> dict:
    return _load_json(_STANDARD_CONTRACT)


def _compare_standard(contract_info: dict) -> list[dict]:
    """标准合同对比 — 扩展到15+对比项，检测缺失+是否达标"""
    standard = _load_standard_contract()
    terms = standard.get("条款", {})
    results = []
    raw = str(contract_info.get("_raw_clauses", ""))
    fin = contract_info["financial"]
    clauses = contract_info["clauses"]
    term_info = contract_info["term"]
    parties = contract_info["parties"]
    prop = contract_info["property"]

    def _term(field: str) -> dict:
        return terms.get(field, {})

    # --- 1. 押金 ---
    if fin["deposit"] is None:
        results.append({"field": "押金", "importance": "high",
                        "standard": _term("押金").get("标准", "不超过1个月租金"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("押金").get("说明", "押金是保障双方权益的重要条款")})
    elif fin["monthly_rent"] and fin["deposit"] > fin["monthly_rent"]:
        results.append({"field": "押金", "importance": "high",
                        "standard": _term("押金").get("标准", "不超过1个月租金"),
                        "actual": f"{fin['deposit']}元（{fin['deposit']/fin['monthly_rent']:.1f}个月租金）",
                        "match": False,
                        "suggestion": "押金超过1个月租金，建议协商降至1个月"})
    else:
        results.append({"field": "押金", "importance": "high",
                        "standard": _term("押金").get("标准", "不超过1个月租金"),
                        "actual": f"{fin['deposit']}元", "match": True,
                        "suggestion": ""})

    # --- 2. 付款方式 ---
    if fin["payment_cycle"] is None:
        results.append({"field": "付款方式", "importance": "medium",
                        "standard": _term("付款方式").get("标准", "押一付一 或 押一付三"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("付款方式").get("说明", "建议明确付款周期和方式")})
    elif re_search_check(r"押[二三四五六]", fin["payment_cycle"]):
        results.append({"field": "付款方式", "importance": "medium",
                        "standard": _term("付款方式").get("标准", "押一付一 或 押一付三"),
                        "actual": fin["payment_cycle"], "match": False,
                        "suggestion": "付款方式偏苛刻，建议协商为押一付三或押一付一"})
    else:
        results.append({"field": "付款方式", "importance": "medium",
                        "standard": _term("付款方式").get("标准", "押一付一 或 押一付三"),
                        "actual": fin["payment_cycle"], "match": True,
                        "suggestion": ""})

    # --- 3. 中介费 ---
    if fin["agent_fee"] is None and parties.get("agent_name"):
        results.append({"field": "中介费", "importance": "medium",
                        "standard": _term("中介费").get("标准", "半个月到1个月租金"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("中介费").get("说明", "中介费应明确金额")})
    elif fin["agent_fee"] and fin["monthly_rent"] and fin["agent_fee"] > fin["monthly_rent"]:
        results.append({"field": "中介费", "importance": "medium",
                        "standard": _term("中介费").get("标准", "半个月到1个月租金"),
                        "actual": f"{fin['agent_fee']}元（超过1个月租金）", "match": False,
                        "suggestion": "中介费超过1个月租金，偏高"})
    elif fin["agent_fee"] is not None:
        results.append({"field": "中介费", "importance": "medium",
                        "standard": _term("中介费").get("标准", "半个月到1个月租金"),
                        "actual": f"{fin['agent_fee']}元", "match": True,
                        "suggestion": ""})

    # --- 4. 违约金 ---
    dp = clauses.get("default_penalty", {})
    et = clauses.get("early_termination", {})
    if dp.get("amount") is None and et.get("penalty") is None:
        results.append({"field": "违约金", "importance": "high",
                        "standard": _term("违约金").get("标准", "不超过1个月租金"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("违约金").get("说明", "违约金应明确约定")})
    elif dp.get("amount") and fin["monthly_rent"] and dp["amount"] > fin["monthly_rent"]:
        results.append({"field": "违约金", "importance": "high",
                        "standard": _term("违约金").get("标准", "不超过1个月租金"),
                        "actual": f"{dp['amount']}元（{dp['amount']/fin['monthly_rent']:.1f}个月租金）",
                        "match": False,
                        "suggestion": "违约金超过1个月租金，建议协商降低"})
    else:
        results.append({"field": "违约金", "importance": "high",
                        "standard": _term("违约金").get("标准", "不超过1个月租金"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 5. 维修责任 ---
    maint = clauses.get("maintenance", {})
    if maint.get("text") is None:
        results.append({"field": "维修责任", "importance": "high",
                        "standard": _term("维修责任").get("标准", "自然损耗由房东承担"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("维修责任").get("说明", "维修责任应明确划分")})
    elif re_search_check(r"均由.*乙方|全部.*承租人|一切.*维修", maint["text"]):
        results.append({"field": "维修责任", "importance": "high",
                        "standard": _term("维修责任").get("标准", "自然损耗由房东承担"),
                        "actual": "全部由租客承担", "match": False,
                        "suggestion": "维修责任全部推给租客不合理，自然损耗应由房东承担"})
    else:
        results.append({"field": "维修责任", "importance": "high",
                        "standard": _term("维修责任").get("标准", "自然损耗由房东承担"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 6. 转租条款 ---
    sub = clauses.get("sublease", {})
    if sub.get("text") is None:
        results.append({"field": "转租条款", "importance": "medium",
                        "standard": _term("转租").get("标准", "经房东书面同意可转租"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("转租").get("说明", "转租条款应明确约定")})
    elif sub.get("allowed") is False:
        results.append({"field": "转租条款", "importance": "medium",
                        "standard": _term("转租").get("标准", "经房东书面同意可转租"),
                        "actual": "完全禁止转租", "match": False,
                        "suggestion": "完全禁止转租的条款可能无效，建议增加经同意可转租的例外"})
    else:
        results.append({"field": "转租条款", "importance": "medium",
                        "standard": _term("转租").get("标准", "经房东书面同意可转租"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 7. 水电费 ---
    if fin.get("utility_responsibility") is None:
        results.append({"field": "水电费", "importance": "medium",
                        "standard": _term("水电费").get("标准", "按民用标准收费"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("水电费").get("说明", "水电费标准应明确")})
    elif re_search_check(r"商水|商电|商用", fin.get("utility_responsibility", "")):
        results.append({"field": "水电费", "importance": "high",
                        "standard": _term("水电费").get("标准", "按民用标准收费"),
                        "actual": "按商用标准收费", "match": False,
                        "suggestion": "住宅用房应按民用标准缴费，商用标准价差2-3倍"})
    else:
        results.append({"field": "水电费", "importance": "medium",
                        "standard": _term("水电费").get("标准", "按民用标准收费"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 8. 提前退租 ---
    if et.get("text") is None:
        results.append({"field": "提前退租", "importance": "high",
                        "standard": _term("提前退租").get("标准", "提前30天书面通知"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("提前退租").get("说明", "提前退租应约定违约金")})
    elif re_search_check(r"押金不予退还|押金全扣|押金不退", et["text"]):
        results.append({"field": "提前退租", "importance": "high",
                        "standard": _term("提前退租").get("标准", "提前30天书面通知"),
                        "actual": "押金全扣", "match": False,
                        "suggestion": "押金全扣条款过于苛刻，应据实结算后退还"})
    else:
        results.append({"field": "提前退租", "importance": "high",
                        "standard": _term("提前退租").get("标准", "提前30天书面通知"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 9. 续租优先权 ---
    if term_info.get("renewal_clause") is None and term_info.get("duration_months"):
        results.append({"field": "续租优先权", "importance": "medium",
                        "standard": _term("续租优先权").get("标准", "同等条件下租客优先"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("续租优先权").get("说明", "续租优先权对长期租赁尤为重要")})
    else:
        results.append({"field": "续租优先权", "importance": "medium",
                        "standard": _term("续租优先权").get("标准", "同等条件下租客优先"),
                        "actual": "已约定" if term_info.get("renewal_clause") else "不适用",
                        "match": True, "suggestion": ""})

    # --- 10. 房屋用途 ---
    if not re_search_check(r"居住|住宅|生活|用途", raw):
        results.append({"field": "房屋用途", "importance": "medium",
                        "standard": _term("房屋用途").get("标准", "仅限居住使用"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("房屋用途").get("说明", "合同应明确约定房屋用途为居住")})
    elif re_search_check(r"商用|经营|办公|注册地址", raw) and not re_search_check(r"居住|住宅", raw):
        results.append({"field": "房屋用途", "importance": "high",
                        "standard": _term("房屋用途").get("标准", "仅限居住使用"),
                        "actual": "商用/经营用途", "match": False,
                        "suggestion": "房屋用途为商用时，水电和税收均按商业标准，需特别注意"})
    else:
        results.append({"field": "房屋用途", "importance": "medium",
                        "standard": _term("房屋用途").get("标准", "仅限居住使用"),
                        "actual": "居住用途", "match": True,
                        "suggestion": ""})

    # --- 11. 入住查验 ---
    insp = clauses.get("inspection", {})
    if not insp.get("has_clause"):
        results.append({"field": "入住查验", "importance": "high",
                        "standard": _term("入住查验").get("标准", "入住前双方共同查验并签署验收记录"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("入住查验").get("说明", "入住查验是避免退租争议的关键证据")})
    else:
        results.append({"field": "入住查验", "importance": "high",
                        "standard": _term("入住查验").get("标准", "入住前双方共同查验并签署验收记录"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 12. 家具清单 ---
    furniture = prop.get("furniture", [])
    if fin.get("deposit") and (not furniture or len(furniture) == 0):
        results.append({"field": "家具清单", "importance": "high",
                        "standard": _term("家具清单").get("标准", "列明所有家具家电品牌型号及状态"),
                        "actual": "无清单", "match": False,
                        "suggestion": _term("家具清单").get("说明", "无清单的押金退还纠纷难以举证")})
    elif furniture and len(furniture) > 0:
        results.append({"field": "家具清单", "importance": "high",
                        "standard": _term("家具清单").get("标准", "列明所有家具家电品牌型号及状态"),
                        "actual": f"{len(furniture)}项", "match": True,
                        "suggestion": ""})

    # --- 13. 钥匙交接 ---
    if not re_search_check(r"钥匙|门禁|门卡|门锁", raw):
        results.append({"field": "钥匙交接", "importance": "medium",
                        "standard": _term("钥匙交接").get("标准", "明确钥匙门禁卡数量并签字确认"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("钥匙交接").get("说明", "钥匙交接是租赁关系成立的基本要件")})
    else:
        results.append({"field": "钥匙交接", "importance": "medium",
                        "standard": _term("钥匙交接").get("标准", "明确钥匙门禁卡数量并签字确认"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 14. 装修约定 ---
    deco = clauses.get("decoration", {})
    if deco.get("text") is None:
        results.append({"field": "装修约定", "importance": "medium",
                        "standard": _term("装修约定").get("标准", "允许合理装修，退租时按折旧恢复"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("装修约定").get("说明", "装修条款应明确约定")})
    elif re_search_check(r"不得.*装修|禁止.*装修|不允许.*改造", deco["text"]) and deco.get("allowed") is False:
        results.append({"field": "装修约定", "importance": "medium",
                        "standard": _term("装修约定").get("标准", "允许合理装修，退租时按折旧恢复"),
                        "actual": "完全禁止装修", "match": False,
                        "suggestion": "完全禁止装修不合理，轻微装修属于租客正常使用权能"})
    else:
        results.append({"field": "装修约定", "importance": "medium",
                        "standard": _term("装修约定").get("标准", "允许合理装修，退租时按折旧恢复"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 15. 押金退还条件 ---
    if fin.get("deposit") and not re_search_check(r"退还|结算|退回|工作日.*退还", raw):
        results.append({"field": "押金退还条件", "importance": "high",
                        "standard": _term("押金退还条件").get("标准", "退租后7-15个工作日内退还，扣除合理费用后"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("押金退还条件").get("说明", "押金退还条件应在合同中明确约定")})
    else:
        results.append({"field": "押金退还条件", "importance": "high",
                        "standard": _term("押金退还条件").get("标准", "退租后7-15个工作日内退还，扣除合理费用后"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 16. 紧急维修 ---
    if maint.get("text") and not re_search_check(r"紧急|突发|应急|24小时", maint["text"]):
        results.append({"field": "紧急维修", "importance": "medium",
                        "standard": _term("紧急维修").get("标准", "紧急情况24小时内响应，费用由责任方承担"),
                        "actual": "未约定紧急维修", "match": False,
                        "suggestion": _term("紧急维修").get("说明", "紧急维修关乎居住安全，应有快速处理机制")})
    elif maint.get("text") is None:
        # 维修责任整体缺失时已在上面报告
        pass
    else:
        results.append({"field": "紧急维修", "importance": "medium",
                        "standard": _term("紧急维修").get("标准", "紧急情况24小时内响应，费用由责任方承担"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 17. 解约通知期 ---
    if not re_search_check(r"提前.*天|通知期|书面通知|解约通知", raw):
        results.append({"field": "解约通知期", "importance": "medium",
                        "standard": _term("解约通知期").get("标准", "提前30天书面通知"),
                        "actual": "未约定", "match": False,
                        "suggestion": _term("解约通知期").get("说明", "解约通知期应双方对等，不少于30天")})
    elif re_search_check(r"提前\s*[57]|提前\s*1周|提前\s*10天", raw):
        results.append({"field": "解约通知期", "importance": "medium",
                        "standard": _term("解约通知期").get("标准", "提前30天书面通知"),
                        "actual": "通知期过短", "match": False,
                        "suggestion": "解约通知期不足30天，建议协商延长至30天"})
    else:
        results.append({"field": "解约通知期", "importance": "medium",
                        "standard": _term("解约通知期").get("标准", "提前30天书面通知"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    # --- 18. 房东进入权 ---
    if re_search_check(r"随时进入|随时查看|不经通知|无需通知", raw):
        results.append({"field": "房东进入权", "importance": "medium",
                        "standard": _term("房东进入权").get("标准", "房东进入需提前24小时通知并征得同意"),
                        "actual": "房东可随时进入", "match": False,
                        "suggestion": "房东进入房屋应提前通知，不得随意进入"})
    elif not re_search_check(r"通知|同意|预约", raw):
        results.append({"field": "房东进入权", "importance": "low",
                        "standard": _term("房东进入权").get("标准", "房东进入需提前24小时通知并征得同意"),
                        "actual": "未约定", "match": False,
                        "suggestion": "建议约定房东进入需提前通知"})
    else:
        results.append({"field": "房东进入权", "importance": "low",
                        "standard": _term("房东进入权").get("标准", "房东进入需提前24小时通知并征得同意"),
                        "actual": "已约定", "match": True,
                        "suggestion": ""})

    return results


# ---------------------------------------------------------------------------
# 评分算法
# ---------------------------------------------------------------------------

def _calculate_score(risks: list[dict], missing: list[dict], contract_info: dict) -> tuple[int, str]:
    high = sum(1 for r in risks if r["level"] == "high")
    medium = sum(1 for r in risks if r["level"] == "medium")
    low = sum(1 for r in risks if r["level"] == "low")
    miss = len(missing)

    # 非线性衰减，避免规则过多时直接归零
    high_deduct = min(high * 6, 35)
    medium_deduct = min(medium * 2, 25)
    low_deduct = min(low * 1, 8)
    miss_deduct = min(miss * 2, 8)
    score = 100 - high_deduct - medium_deduct - low_deduct - miss_deduct

    # bonus
    bonus = 0
    if contract_info["clauses"]["inspection"]["has_clause"]:
        bonus += 5
    if contract_info["clauses"]["early_termination"]["penalty"]:
        text = str(contract_info["clauses"]["early_termination"]["penalty"])
        if re_search_check(r"分月|逐月|按月", text):
            bonus += 5
    if contract_info["clauses"]["maintenance"]["landlord_responsibility"]:
        bonus += 3
    if contract_info["property"]["furniture"] and len(contract_info["property"]["furniture"]) > 0:
        bonus += 3

    score += bonus
    score = max(0, min(100, score))

    if score >= 90:
        level = "safe"
    elif score >= 70:
        level = "caution"
    elif score >= 50:
        level = "warning"
    else:
        level = "danger"

    return score, level


def _score_level_display(level: str) -> str:
    mapping = {
        "safe": "\U0001f7e2 安全",
        "caution": "\U0001f7e1 需谨慎",
        "warning": "\U0001f7e0 风险较大",
        "danger": "\U0001f534 危险",
    }
    return mapping.get(level, level)


# ---------------------------------------------------------------------------
# ContractReviewer 主类
# ---------------------------------------------------------------------------

class ContractReviewer:
    def __init__(self, user_id: str = "default"):
        self.parser = ContractParser()
        self.user_id = user_id
        self._all_rules: list[dict] | None = None

    def review(self, contract_text: str, enable_ai_review: bool = True) -> dict:
        # 1. 结构化提取
        contract_info = self.parser.extract(contract_text)
        contract_info["_raw_clauses"] = contract_text

        # 推断城市
        city = _detect_city_from_address(contract_info["property"]["address"])

        # 2. 规则扫描
        risks = self._scan_rules(contract_info, city)

        # 3. 标准对比
        missing = _compare_standard(contract_info)

        # 4. 评分
        score, level = _calculate_score(risks, missing, contract_info)

        # 5. 生成报告
        report = self._build_report(score, level, risks, missing, contract_info)

        # 6. AI 深度审查（可选，带超时保护）
        if enable_ai_review:
            report["ai_review"] = self._do_ai_review(contract_info, risks)
        else:
            report["ai_review"] = ""

        # 7. 谈判话术 — 始终用模板，LLM 话术由 /ai-review 独立接口提供
        report["negotiation_speech"] = self._template_only_speech(risks)

        return report

    def review_with_llm(self, contract_text: str) -> str:
        """LLM 深度审查（独立调用，保持向后兼容）"""
        try:
            llm = LLM()
            prompt = (
                "你是中国租房合同法律审查专家。请对以下合同文本进行深度审查，"
                "重点关注：1)隐藏的不公平条款 2)法律风险 3)租客权益保障不足之处。\n\n"
                f"合同文本：\n{contract_text[:2000]}\n\n"
                "请给出简洁的审查意见（300字以内）。"
            )
            return llm.generate(prompt, system="你是一个专业的中国租房合同审查专家。")
        except Exception as e:
            return f"AI 审查暂不可用: {e}"

    def _do_ai_review(self, contract_info: dict, risks: list[dict]) -> dict | str:
        """AI 深度审查 — 基于结构化信息+风险列表，10秒超时保护"""
        try:
            # 构造结构化摘要给 LLM
            fin = contract_info["financial"]
            high_risks = [r for r in risks if r["level"] == "high"]
            medium_risks = [r for r in risks if r["level"] == "medium"]

            risk_summary = "高风险条款：" + ", ".join(f"[{r['id']}]{r['title']}" for r in high_risks)
            risk_summary += "\n中风险条款：" + ", ".join(f"[{r['id']}]{r['title']}" for r in medium_risks)

            contract_summary = (
                f"月租金：{fin.get('monthly_rent', '未知')}元，"
                f"押金：{fin.get('deposit', '未知')}元，"
                f"付款方式：{fin.get('payment_cycle', '未知')}"
            )

            prompt = (
                "你是中国租房合同法律审查专家。以下是合同的结构化提取结果和已识别风险，"
                "请基于这些信息进行深度分析：\n\n"
                f"合同基本信息：{contract_summary}\n"
                f"已识别风险：\n{risk_summary}\n\n"
                "请分析：1)这些风险条款中最需要警惕的隐藏陷阱 2)租客最应优先谈判的条款 "
                "3)其他潜在法律风险\n\n"
                "请以JSON格式返回：{\"summary\": \"总体评价(50字内)\", "
                "\"key_risks\": [\"关键风险1\", \"关键风险2\"], "
                "\"negotiation_tips\": [\"谈判建议1\", \"谈判建议2\"]}"
            )

            llm = LLM()
            result_text = llm.generate(
                prompt,
                system="你是专业的中国租房合同审查专家。只返回JSON，不要其他文字。",
                timeout=10,
            )

            # 检测超时/错误返回
            if result_text.startswith("⚠️"):
                logger.warning("AI 审查 LLM 返回错误: %s", result_text[:80])
                return "AI 审查暂不可用"

            # 解析 JSON 结果
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return {
                    "summary": parsed.get("summary", ""),
                    "key_risks": parsed.get("key_risks", []),
                    "negotiation_tips": parsed.get("negotiation_tips", []),
                }
            return {"summary": result_text[:200], "key_risks": [], "negotiation_tips": []}

        except json.JSONDecodeError:
            logger.warning("AI 审查返回非JSON格式")
            return {"summary": "AI 审查结果解析失败", "key_risks": [], "negotiation_tips": []}
        except Exception as e:
            logger.warning("AI 审查失败: %s", e)
            return "AI 审查暂不可用"

    # ------------------------------------------------------------------
    # 谈判话术
    # ------------------------------------------------------------------

    # 预置话术模板（高频风险）
    _SPEECH_TEMPLATES: dict[str, dict] = {
        "A01": {"tone": "firm",
                 "speech": "您好，关于押金的问题，一般租房押金是1个月租金，目前要求押金偏高。能否调整为1个月租金作为押金？这样对我们双方都比较合理。"},
        "A02": {"tone": "polite",
                 "speech": "押金金额我可以接受，但希望能明确退还条件——比如退租后多少个工作日内、扣除什么费用后退还。咱们可以在合同中写清楚吗？"},
        "A03": {"tone": "firm",
                 "speech": "中介费超过了一个月租金，这个收费偏高。市场行情通常是半个月到一个月租金，能否按半个月租金收？"},
        "C01": {"tone": "firm",
                 "speech": "提前退租押金全扣这条太苛刻了。按照法律规定，押金应该据实结算后退还，不能一律全扣。建议改为：提前30天书面通知，押金扣除合理违约金后退还。"},
        "C02": {"tone": "firm",
                 "speech": "违约金超过了2个月租金，这不符合《民法典》关于违约金上限的规定。建议调整为1个月租金，这样对双方都公平。"},
        "D01": {"tone": "firm",
                 "speech": "合同里写维修全部由我承担，但房屋自然老化和结构问题是房东的责任，这在《民法典》里有明确规定。建议修改为：自然损耗和房屋结构问题由房东承担，人为损坏由我承担。"},
        "D02": {"tone": "firm",
                 "speech": "自然损耗不应该由租客承担，正常使用产生的磨损属于房东维修范围。建议明确：自然老化由房东负责，人为损坏由租客负责。"},
        "B03": {"tone": "polite",
                 "speech": "关于自动续租这条，我希望改为：到期前双方协商，需书面确认才续约。不通知就自动续约容易造成误解。"},
        "G01": {"tone": "polite",
                 "speech": "有押金的情况下，我希望能列一份详细的家具家电清单，注明品牌、型号和现有状态，这样退租时双方都有依据，避免扯皮。"},
        "G02": {"tone": "polite",
                 "speech": "建议我们在入住前一起做一次房屋查验，拍照记录现有状况并签字确认。这样退租时对比一下就行，对双方都是保障。"},
        "A08": {"tone": "polite",
                 "speech": "合同中没有明确押金退还条件，建议加上：退租后15个工作日内，扣除合理费用后退还押金。这样对双方都有保障。"},
        "C03": {"tone": "firm",
                 "speech": "合同中只给了甲方单方解约权，这不公平。建议双方解约权利对等，任何一方提前解约都应提前30天书面通知。"},
    }

    def generate_negotiation_speech(self, risks: list[dict]) -> list[dict]:
        """为高/中风险生成谈判话术 — 模板+LLM混合策略"""
        speeches = []
        target_risks = [r for r in risks if r["level"] in ("high", "medium")]
        llm_used = 0  # 限制 LLM 调用次数，避免超时

        for risk in target_risks:
            risk_id = risk.get("id", "")
            template = self._SPEECH_TEMPLATES.get(risk_id)

            if template:
                # 有预置模板的高频风险
                speeches.append({
                    "risk_id": risk_id,
                    "title": risk.get("title", ""),
                    "speech": template["speech"],
                    "tone": template["tone"],
                })
            elif llm_used < 2:
                # 无模板的风险，用 LLM 生成（最多2次），5秒超时回退通用话术
                speech = self._llm_generate_speech(risk)
                speeches.append({
                    "risk_id": risk_id,
                    "title": risk.get("title", ""),
                    "speech": speech,
                    "tone": self._infer_tone(risk),
                })
                llm_used += 1
            else:
                # LLM 次数用完，用通用话术
                fallback = (
                    f"关于「{risk.get('title', '该条款')}」，"
                    "我希望能和您协商一下，这个条款对租客来说偏不利，能否调整得更公平一些？"
                )
                speeches.append({
                    "risk_id": risk_id,
                    "title": risk.get("title", ""),
                    "speech": fallback,
                    "tone": self._infer_tone(risk),
                })

        return speeches

    def _llm_generate_speech(self, risk: dict) -> str:
        """用 LLM 生成单条风险的谈判话术，5秒超时回退"""
        fallback = f"关于「{risk.get('title', '该条款')}」，我希望能和您协商一下，这个条款对租客来说偏不利，能否调整得更公平一些？"
        try:
            llm = LLM()
            prompt = (
                f"你是租房谈判顾问。以下是一个合同风险点：\n"
                f"风险ID: {risk.get('id', '')}\n"
                f"标题: {risk.get('title', '')}\n"
                f"建议: {risk.get('suggestion', '')}\n"
                f"法律依据: {risk.get('legal_basis', '')}\n\n"
                f"请生成一段50字以内的谈判话术，语气礼貌但有原则，让租客可以用在和房东/中介沟通时。"
                f"只输出话术文本，不要加引号或其他格式。"
            )
            result = llm.generate(
                prompt,
                system="你是租房谈判顾问，只输出话术文本。",
                timeout=5,
            )
            if result.startswith("⚠️"):
                return fallback
            return result.strip() if result.strip() else fallback
        except Exception as e:
            logger.debug("谈判话术LLM生成失败: %s", e)
            return fallback

    @staticmethod
    def _infer_tone(risk: dict) -> str:
        """根据风险级别和类别推断语气"""
        if risk.get("level") == "high":
            return "firm"
        return "polite"

    def _template_only_speech(self, risks: list[dict]) -> list[dict]:
        """仅使用预置模板生成话术，不调用 LLM（用于 enable_ai_review=False 场景）"""
        speeches = []
        target_risks = [r for r in risks if r["level"] in ("high", "medium")]

        for risk in target_risks:
            risk_id = risk.get("id", "")
            template = self._SPEECH_TEMPLATES.get(risk_id)

            if template:
                speeches.append({
                    "risk_id": risk_id,
                    "title": risk.get("title", ""),
                    "speech": template["speech"],
                    "tone": template["tone"],
                })
            else:
                # 无模板时使用通用话术，不调 LLM
                fallback = (
                    f"关于「{risk.get('title', '该条款')}」，"
                    "我希望能和您协商一下，这个条款对租客来说偏不利，能否调整得更公平一些？"
                )
                speeches.append({
                    "risk_id": risk_id,
                    "title": risk.get("title", ""),
                    "speech": fallback,
                    "tone": self._infer_tone(risk),
                })

        return speeches

    def _scan_rules(self, contract_info: dict, city: str) -> list[dict]:
        if self._all_rules is None:
            self._all_rules = _build_rules()
            self._all_rules.extend(_build_city_rules_for_city(city))

        risks = []
        for rule in self._all_rules:
            try:
                triggered = rule["check"](contract_info)
            except Exception as e:
                logger.debug("规则 %s 执行失败: %s", rule["id"], e)
                triggered = False

            if triggered:
                original_text = self._extract_original_snippet(rule, contract_info)
                risks.append({
                    "id": rule["id"],
                    "category": rule["category"],
                    "level": rule["level"],
                    "title": rule["title"],
                    "original_text": original_text,
                    "suggestion": rule["suggestion"],
                    "legal_basis": rule["legal_basis"],
                    "analysis": "",
                })

        return risks

    def _extract_original_snippet(self, rule: dict, contract_info: dict) -> str:
        import re as _re
        category = rule["category"]
        title = rule["title"]
        raw = str(contract_info.get("_raw_clauses", ""))

        if category == "费用":
            if "押金" in title:
                m = _re.search(r"押金.{0,80}", raw)
                return m.group(0) if m else ""
            elif "中介" in title:
                m = _re.search(r"中介费.{0,80}", raw)
                return m.group(0) if m else ""
            elif "水电" in title:
                return str(contract_info["financial"]["utility_responsibility"] or "")
            elif "付款周期" in title or "押二" in title:
                return str(contract_info["financial"]["payment_cycle"] or "")
            elif "物业" in title:
                m = _re.search(r"物业费.{0,80}", raw)
                return m.group(0) if m else ""
            else:
                m = _re.search(r"费用.{0,80}", raw)
                return m.group(0) if m else ""
        elif category == "期限":
            if "租期" in title or "起租" in title:
                m = _re.search(r"租赁期.{0,100}|租期.{0,80}", raw)
                return m.group(0) if m else ""
            elif "续租" in title:
                return str(contract_info["term"].get("renewal_clause") or "")
            elif "到期" in title:
                m = _re.search(r"自动续租.{0,100}|到期.{0,80}", raw)
                return m.group(0) if m else ""
        elif category == "违约":
            et = contract_info["clauses"].get("early_termination", {})
            dp = contract_info["clauses"].get("default_penalty", {})
            text = str(et.get("text") or dp.get("text") or "")
            if not text:
                m = _re.search(r"违约.{0,100}", raw)
                return m.group(0) if m else ""
            return text
        elif category == "维修":
            return str(contract_info["clauses"].get("maintenance", {}).get("text") or "")
        elif category == "装修":
            return str(contract_info["clauses"].get("decoration", {}).get("text") or "")
        elif category == "权属":
            parties = contract_info["parties"]
            parts = []
            if parties.get("landlord_name"):
                parts.append("甲方：" + parties["landlord_name"])
            if parties.get("landlord_id"):
                parts.append("身份证：" + parties["landlord_id"])
            return "；".join(parts)
        elif category == "附属":
            furniture = contract_info["property"].get("furniture", [])
            return "、".join(furniture) if furniture else ""
        elif category == "城市政策":
            if "押金" in title:
                m = _re.search(r"押金.{0,80}", raw)
                return m.group(0) if m else ""
            elif "转租" in title:
                return str(contract_info["clauses"].get("sublease", {}).get("text") or "")
            elif "面积" in title:
                return str(contract_info["property"].get("area") or "")
            return ""

        return ""

    def _build_report(self, score: int, level: str,
                      risks: list[dict], missing: list[dict],
                      contract_info: dict) -> dict:
        level_display = {
            "safe": "\U0001f7e2 安全",
            "caution": "\U0001f7e1 需谨慎",
            "warning": "\U0001f7e0 风险较大",
            "danger": "\U0001f534 危险",
        }

        high_count = sum(1 for r in risks if r["level"] == "high")
        medium_count = sum(1 for r in risks if r["level"] == "medium")
        summary = (
            f"发现 {len(risks)} 个风险点（高风险 {high_count} 个，中风险 {medium_count} 个），"
            f"缺失 {len(missing)} 个重要条款。"
        )

        fin = contract_info["financial"]
        term = contract_info["term"]
        parties = contract_info["parties"]

        contract_summary = {
            "landlord": parties.get("landlord_name") or "未提取",
            "address": contract_info["property"]["address"] or "未提取",
            "rent": fin["monthly_rent"] or 0,
            "deposit": fin["deposit"] or 0,
            "term": (
                f"{term.get('start_date', '')} 至 {term.get('end_date', '')}"
                if term.get("start_date") else "未提取"
            ),
            "payment": fin["payment_cycle"] or "未提取",
        }

        return {
            "score": score,
            "level": level_display.get(level, level),
            "risk_level_code": level,
            "summary": summary,
            "risks": risks,
            "missing": missing,
            "contract_summary": contract_summary,
            "contract_info": {k: v for k, v in contract_info.items() if k != "_raw_clauses"},
        }
