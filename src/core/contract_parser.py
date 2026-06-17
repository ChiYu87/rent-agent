"""
合同结构化提取引擎 — ContractParser
规则引擎 + LLM 双引擎，从合同文本提取 25 个关键字段
"""
import re
import json
import logging
from typing import Any

from ..utils.text import normalize_price
from .llm import LLM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

_ID_CARD_RE = re.compile(r"\b\d{17}[\dXx]\b")
_DATE_RES = [
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})"),
]
_AMOUNT_RE = re.compile(r"[¥￥]?\s*([\d,]+(?:\.\d+)?)\s*(万|千|元|块)?")
_CHINESE_NUM_RE = re.compile(r"([一二两三四五六七八九十]+)\s*(万|千|百|元|块)?")

# 简单中文数字 → 阿拉伯数字
_CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "两": 2,
}


def _chinese_to_float(text: str) -> float | None:
    """把『三千五百』『三万五千』等转成 float"""
    text = text.replace(" ", "")
    for k, v in _CN_NUM_MAP.items():
        text = text.replace(k, str(v))
    m = re.search(r"(\d+)", text)
    if not m:
        return None
    val = float(m.group(1))
    if "万" in text:
        val *= 10000
    elif "千" in text:
        val *= 1000
    return val


def _extract_id_card(text: str) -> str | None:
    m = _ID_CARD_RE.search(text)
    return m.group(0) if m else None


def _mask_id_card(id_card: str) -> str:
    """18 位身份证号脱敏：中间 10 位用 * 替换"""
    if not id_card or len(id_card) < 18:
        return id_card
    return id_card[:4] + "*" * 10 + id_card[-4:]


def _extract_dates(text: str) -> list[str]:
    """返回合同里所有日期字符串（保持原文格式）"""
    dates = []
    for pattern in _DATE_RES:
        for m in pattern.finditer(text):
            dates.append(m.group(0))
    return dates


def _extract_amount(text: str) -> float | None:
    """
    从一段文本中提取金额，优先用 normalize_price，
    其次匹配中文数字金额。
    """
    # 先尝试 normalize_price（处理带单位的片段）
    try:
        val = normalize_price(text)
        if val > 0:
            return val
    except Exception:
        pass

    # 匹配 ¥3,500 / 3500元
    m = _AMOUNT_RE.search(text)
    if m:
        num_str = m.group(1).replace(",", "")
        try:
            val = float(num_str)
        except ValueError:
            return None
        unit = m.group(2)
        if unit == "万":
            val *= 10000
        elif unit == "千":
            val *= 1000
        return val

    # 中文数字
    m = _CHINESE_NUM_RE.search(text)
    if m:
        return _chinese_to_float(m.group(0))

    return None


def _extract_area(text: str) -> float | None:
    """提取面积（平米）"""
    pattern = re.compile(r"(\d+\.?\d*)\s*(㎡|平|平方|米\s*2)", re.IGNORECASE)
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _keyword_before_after(text: str, keywords: list[str], window: int = 40) -> str:
    """
    在文本中找关键词，返回关键词前后 window 个字符的片段（用于 LLM 补充提取）。
    """
    for kw in keywords:
        idx = text.find(kw)
        if idx != -1:
            start = max(0, idx - window)
            end = min(len(text), idx + len(kw) + window)
            return text[start:end]
    return ""


# ---------------------------------------------------------------------------
# ContractParser
# ---------------------------------------------------------------------------

class ContractParser:
    """
    从合同文本中提取结构化字段。

    策略：
      1. 规则引擎（正则 + 关键词定位）先跑
      2. 未命中的字段交给 LLM 补充
      3. 合并结果，规则优先，冲突取规则
      4. 最终未提取的字段记入 missing_fields
    """

    def __init__(self):
        self.llm = LLM()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def extract(self, text: str) -> dict:
        """
        输入合同全文，返回 ContractInfo 字典。
        """
        result: dict = {
            "parties": {
                "landlord_name": None,
                "landlord_id": None,
                "tenant_name": None,
                "tenant_id": None,
                "agent_name": None,
            },
            "property": {
                "address": None,
                "area": None,
                "type": None,
                "furniture": [],
                "current_condition": None,
            },
            "financial": {
                "monthly_rent": None,
                "deposit": None,
                "payment_cycle": None,
                "payment_date": None,
                "utility_responsibility": None,
                "property_fee": None,
                "agent_fee": None,
                "other_fees": [],
            },
            "term": {
                "start_date": None,
                "end_date": None,
                "duration_months": None,
                "renewal_clause": None,
            },
            "clauses": {
                "early_termination": {"text": None, "penalty": None},
                "sublease": {"text": None, "allowed": None},
                "rent_increase": {"text": None, "has_clause": False},
                "maintenance": {"text": None, "landlord_responsibility": None, "tenant_responsibility": None},
                "decoration": {"text": None, "allowed": None, "restore_required": None},
                "default_penalty": {"text": None, "amount": None},
                "inspection": {"text": None, "has_clause": False, "has_inspection_clause": None},
            },
            "missing_fields": [],
        }

        # 第一遍：规则引擎
        self._rule_extract(text, result)

        # 第二遍：LLM 补充（当前模型推理慢，暂时禁用，后续换模型后开启）
        # missing_keys = self._collect_missing_for_llm(result)
        # if missing_keys:
        #     raw = self.llm.generate(
        #         self._build_llm_prompt(text, missing_keys),
        #         system=(...),
        #         timeout=5,
        #     )
        #     parsed = self._parse_llm_json(raw)
        #     if parsed:
        #         self._merge_llm_result(result, parsed)

        # 第三遍：合并 & 脱敏
        self._post_process(result)

        # 第四遍：检查缺失字段
        self._check_missing(result)

        return result

    # ------------------------------------------------------------------
    # 规则引擎
    # ------------------------------------------------------------------

    def _rule_extract(self, text: str, result: dict):
        """用正则 + 关键词从合同文本提取字段"""

        # ---- 当事人 ----
        self._extract_parties(text, result)

        # ---- 房屋信息 ----
        self._extract_property(text, result)

        # ---- 财务信息 ----
        self._extract_financial(text, result)

        # ---- 租期 ----
        self._extract_term(text, result)

        # ---- 条款 ----
        self._extract_clauses(text, result)

    def _extract_parties(self, text: str, result: dict):
        parties = result["parties"]

        # 甲方/乙方 名称 — 找『甲方（出租方）：某某』或『甲方：张三』
        landlord_match = re.search(
            r"甲方\s*(?:[（(].*?[）)])?\s*[：:]\s*([^\n，,。；;]{2,30})",
            text[:600]
        )
        if landlord_match:
            name = landlord_match.group(1).strip()
            # 过滤掉描述性词语
            for kw in ["出租方", "房东", "出租人"]:
                name = name.replace(kw, "").strip()
            if name:
                parties["landlord_name"] = name

        tenant_match = re.search(
            r"乙方\s*(?:[（(].*?[）)])?\s*[：:]\s*([^\n，,。；;]{2,30})",
            text[:600]
        )
        if tenant_match:
            name = tenant_match.group(1).strip()
            for kw in ["承租方", "租客", "承租人"]:
                name = name.replace(kw, "").strip()
            if name:
                parties["tenant_name"] = name

        # 如果上面没匹配到，用更宽松的模式
        if not parties["landlord_name"]:
            m = re.search(r"出租方\s*[：:]\s*([^\n，,。；;]{2,30})", text[:600])
            if m:
                parties["landlord_name"] = m.group(1).strip()
        if not parties["tenant_name"]:
            m = re.search(r"承租方\s*[：:]\s*([^\n，,。；;]{2,30})", text[:600])
            if m:
                parties["tenant_name"] = m.group(1).strip()

        # 身份证号
        id_cards = _ID_CARD_RE.findall(text)
        if len(id_cards) >= 2:
            parties["landlord_id"] = id_cards[0]
            parties["tenant_id"] = id_cards[1]
        elif len(id_cards) == 1:
            # 判断属于哪一方（在『甲方』附近还是『乙方』附近）
            pos = text.find(id_cards[0])
            if pos < len(text) // 2:
                parties["landlord_id"] = id_cards[0]
            else:
                parties["tenant_id"] = id_cards[0]

        # 中介/代理人
        agent_kw = re.search(r"(中介|代理|经纪人|经办人)\s*[：:]\s*([^\n，,。；;]{2,20})", text)
        if agent_kw:
            parties["agent_name"] = agent_kw.group(2).strip()

    def _extract_property(self, text: str, result: dict):
        prop = result["property"]

        # 地址
        addr_patterns = [
            r"房屋坐落\s*[：:]\s*([^\n]{5,80})",
            r"位于\s*([\u4e00-\u9fa5\d\s路街巷弄栋楼号室]{5,80})",
            r"地址\s*[：:]\s*([^\n]{5,80})",
        ]
        for p in addr_patterns:
            m = re.search(p, text)
            if m:
                prop["address"] = m.group(1).strip()
                break

        # 面积
        prop["area"] = _extract_area(text)

        # 户型
        type_patterns = [
            r"(\d\s*室\s*\d\s*厅\s*\d\s*卫?)",
            r"户型\s*[：:]\s*([^\n]{2,20})",
        ]
        for p in type_patterns:
            m = re.search(p, text)
            if m:
                prop["type"] = m.group(1).strip()
                break

        # 家具清单
        furniture_kw = re.search(r"家具.*?[：:]\s*([^\n]{2,100})", text)
        if furniture_kw:
            items = re.split(r"[、,，;；]", furniture_kw.group(1))
            prop["furniture"] = [i.strip() for i in items if i.strip()]

        # 现状
        condition_kw = re.search(r"房屋现状\s*[：:]\s*([^\n]{2,50})", text)
        if condition_kw:
            prop["current_condition"] = condition_kw.group(1).strip()

    def _extract_financial(self, text: str, result: dict):
        fin = result["financial"]

        # 月租金 — 多种表达方式
        rent_patterns = [
            r"月租金\s*[：:]?\s*(?:人民币|RMB|rmb)??\s*([\d,]+(?:\.\d+)?|([一二两三四五六七八九十百千万]+))\s*(万|千|元|块)?",
            r"每月租金\s*[：:]?\s*(?:人民币|RMB|rmb)??\s*([\d,]+(?:\.\d+)?|([一二两三四五六七八九十百千万]+))\s*(万|千|元|块)?",
            r"租金\s*(?:为|：|:)?\s*(?:人民币|RMB|rmb)?\s*([\d,]+(?:\.\d+)?|([一二两三四五六七八九十百千万]+))\s*(万|千|元|块)?",
            r"月租\s*[：:]\s*([^\n]{2,30})",
        ]
        for p in rent_patterns:
            m = re.search(p, text)
            if m:
                raw_val = m.group(1)
                unit = m.group(3) if m.group(3) else ""
                # 中文数字转阿拉伯
                if raw_val and any(c in raw_val for c in "一二两三四五六七八九十百千万"):
                    fin["monthly_rent"] = _chinese_to_float(raw_val + unit)
                else:
                    fin["monthly_rent"] = _extract_amount(raw_val + unit)
                if fin["monthly_rent"]:
                    break

        # 如果上面没拿到，找『元/月』附近的数字
        if not fin["monthly_rent"]:
            m = re.search(r"([\d,]+(?:\.\d+)?)\s*元\s*/\s*月", text)
            if m:
                fin["monthly_rent"] = normalize_price(m.group(1) + "元")

        # 还没拿到，尝试更宽泛的匹配：人民币3500元
        if not fin["monthly_rent"]:
            m = re.search(r"(?:人民币|RMB|rmb)\s*([\d,]+(?:\.\d+)?)\s*元", text)
            if m:
                fin["monthly_rent"] = _extract_amount(m.group(1) + "元")

    # 押金
        deposit_patterns = [
            r"押金\s*[：:]?\s*(?:为\s*)?(?:人民币|RMB|rmb)?\s*([\d,]+(?:\.\d+)?|([一二两三四五六七八九十百千万]+))\s*(万|千|元|块)?",
            r"保证金\s*[：:]\s*([^\n]{2,30})",
        ]
        for p in deposit_patterns:
            m = re.search(p, text)
            if m:
                raw_val = m.group(1)
                unit = m.group(3) if m.group(3) else ""
                if raw_val and any(c in raw_val for c in "一二两三四五六七八九十百千万"):
                    fin["deposit"] = _chinese_to_float(raw_val + unit)
                else:
                    fin["deposit"] = _extract_amount(raw_val + unit)
                if fin["deposit"]:
                    break

        # 付款方式（押一付三等）
        payment_patterns = [
            r"(押\s*[一二两三四五六]\s*付\s*[一二两三四五六七八])",
            r"(押\s*\d\s*付\s*\d)",
            r"付款方式\s*[：:]\s*([^\n]{2,30})",
        ]
        for p in payment_patterns:
            m = re.search(p, text)
            if m:
                fin["payment_cycle"] = m.group(1).strip()
                break

        # 每月付款日
        date_patterns = [
            r"每月\s*(\d{1,2})\s*日",
            r"于每月\s*(\d{1,2})\s*号",
        ]
        for p in date_patterns:
            m = re.search(p, text)
            if m:
                fin["payment_date"] = int(m.group(1))
                break

        # 水电费责任
        utility_patterns = [
            r"水电费\s*[：:]\s*([^\n]{2,50})",
            r"物业费\s*[：:]\s*([^\n]{2,50})",
            r"公用事业费\s*[：:]\s*([^\n]{2,50})",
        ]
        for p in utility_patterns:
            m = re.search(p, text)
            if m:
                fin["utility_responsibility"] = m.group(1).strip()
                break

        # 物业费
        prop_fee = re.search(r"物业费\s*[：:]\s*([^\n]{2,50})", text)
        if prop_fee:
            fin["property_fee"] = prop_fee.group(1).strip()

        # 中介费
        agent_fee = re.search(r"中介费\s*[：:]?\s*(?:为|人民币|RMB|rmb)?\s*([\d,]+(?:\.\d+)?|([一二两三四五六七八九十百千万]+))\s*(万|千|元|块)?", text)
        if agent_fee:
            raw_val = agent_fee.group(1)
            unit = agent_fee.group(3) if agent_fee.group(3) else ""
            if raw_val and any(c in raw_val for c in "一二两三四五六七八九十百千万"):
                fin["agent_fee"] = _chinese_to_float(raw_val + unit)
            else:
                fin["agent_fee"] = _extract_amount(raw_val + unit)
        # 备选：中介费XXX元由...
        if not fin["agent_fee"]:
            m = re.search(r"中介费\s*([\d,]+(?:\.\d+)?)\s*元", text)
            if m:
                fin["agent_fee"] = _extract_amount(m.group(1) + "元")

        # 其他费用
        other = re.search(r"其他费用\s*[：:]\s*([^\n]{2,100})", text)
        if other:
            # 尝试解析『管理费200元/月』格式
            items = re.split(r"[、,，;；]", other.group(1))
            for item in items:
                item = item.strip()
                if not item:
                    continue
                amt = _extract_amount(item)
                name = re.sub(r"[¥￥\d,\.万块元/月]+", "", item).strip()
                fin["other_fees"].append({
                    "name": name or item,
                    "amount": amt,
                })

    def _extract_term(self, text: str, result: dict):
        term = result["term"]

        dates = _extract_dates(text)
        if len(dates) >= 2:
            term["start_date"] = dates[0]
            term["end_date"] = dates[1]
        elif len(dates) == 1:
            term["start_date"] = dates[0]

        # 租期月数
        duration_patterns = [
            r"租期\s*[：:]\s*(\d+)\s*个?\s*月",
            r"租赁期限\s*[：:]\s*(\d+)\s*个?\s*月",
            r"期限\s*为\s*(\d+)\s*个?\s*月",
        ]
        for p in duration_patterns:
            m = re.search(p, text)
            if m:
                term["duration_months"] = int(m.group(1))
                break

        # 如果没拿到租期月数，用起止日期推算
        if not term["duration_months"] and term["start_date"] and term["end_date"]:
            term["duration_months"] = self._calc_duration_months(term["start_date"], term["end_date"])

        # 续租条款 — 增强匹配
        renewal_patterns = [
            r"同等条件下.{0,20}续租.{0,60}",
            r"优先续租.{0,60}",
            r"优先续约.{0,60}",
            r"续租优先权.{0,60}",
            r"(?:乙方|承租人).{0,10}享有.{0,10}续租.{0,60}",
            r"(?:经|经甲方|经出租方)(?:书面)?同意.{0,10}续租.{0,60}",
            r"(续租|续约).{0,80}",
        ]
        renewal_text = ""
        for p in renewal_patterns:
            m = re.search(p, text)
            if m:
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 30)
                renewal_text = text[start:end].strip()
                break

        if renewal_text:
            term["renewal_clause"] = renewal_text

    def _calc_duration_months(self, start: str, end: str) -> int | None:
        """从两个日期字符串（中文或 ISO 格式）推算间隔月数"""
        try:
            import datetime
            for fmt in ["%Y年%m月%d日", "%Y.%m.%d", "%Y-%m-%d"]:
                try:
                    sd = datetime.datetime.strptime(start, fmt)
                    ed = datetime.datetime.strptime(end, fmt)
                    return (ed.year - sd.year) * 12 + (ed.month - sd.month)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def _extract_clauses(self, text: str, result: dict):
        clauses = result["clauses"]

        # 辅助函数：从合同文本中截取某个条条的全部内容（到下一个『第X条』）
        def _get_section(keyword: str) -> str:
            """找到包含关键词的『第X条』，返回该条的完整内容"""
            # 找关键词所在的第X条
            m = re.search(r"第[一二三四五六七八九十百]+条\s*[^\n]*" + keyword + r"[^\n]*", text)
            if not m:
                # 尝试只找关键词附近
                m = re.search(keyword + r".{0,200}", text)
                return m.group(0).strip() if m else ""
            start = m.start()
            # 找下一个『第X条』
            next_section = re.search(r"\n第[一二三四五六七八九十百]+条", text[start + 10:])
            if next_section:
                return text[start:start + 10 + next_section.start()].strip()
            else:
                return text[start:start + 300].strip()

        # 提前退租
        early = _get_section("退租|解除|违约")
        if early:
            clauses["early_termination"]["text"] = early
            penalty = re.search(r"(押金不予退还|违约金\s*[¥￥]?\s*[\d,]+|赔偿\s*[¥￥]?\s*[\d,]+)", early)
            if penalty:
                clauses["early_termination"]["penalty"] = penalty.group(1).strip()

        # 转租 — 增强正则匹配
        # 优先用精细化正则直接定位转租条款
        sublease_patterns = [
            r"(?:乙方|承租人|租客).{0,10}不得.{0,6}转租",
            r"未经(?:甲方|出租方|房东).{0,6}同意.{0,6}(?:不得|不可|不能)转租",
            r"不得(?:擅自)?转租",
            r"禁止转租",
            r"不允许转租",
            r"(?:经|经甲方|经出租方|经房东)(?:书面)?同意.{0,10}(?:可|可以|方可|方可)转租",
            r"(?:经|经甲方|经出租方|经房东)(?:书面)?同意.{0,10}(?:可|可以)?转租",
            r"转租.{0,20}",
            r"转借.{0,20}",
            r"分租.{0,20}",
        ]
        sublease_text = ""
        for p in sublease_patterns:
            m = re.search(p, text)
            if m:
                # 扩展上下文到整句
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 50)
                sublease_text = text[start:end].strip()
                break

        # 也可通过 _get_section 获取更完整的条款
        if not sublease_text:
            sublease_text = _get_section("转租|转借|分租")

        if sublease_text:
            clauses["sublease"]["text"] = sublease_text
            if re.search(r"不得.{0,6}转租|禁止转租|不允许转租|不能转租|不可转租|未经.*同意.*不得.*转租", sublease_text):
                clauses["sublease"]["allowed"] = False
            elif re.search(r"经.{0,6}同意.{0,10}(可|可以|方可)?转租|允许转租|可以转租", sublease_text):
                clauses["sublease"]["allowed"] = True

        # 租金调整
        rent_inc = re.search(r"(租金调整|租金上涨|涨租|调整租金).{0,100}", text)
        if rent_inc:
            clauses["rent_increase"]["text"] = rent_inc.group(0).strip()
            clauses["rent_increase"]["has_clause"] = True

        # 维修责任 — 增强正则匹配
        maint_patterns = [
            r"维修.{0,5}(由|归).{0,10}(甲方|出租方|房东|乙方|承租方|租客).{0,20}",
            r"(?:甲方|出租方|房东).{0,10}负责.{0,10}维修",
            r"(?:乙方|承租方|租客).{0,10}负责.{0,10}(日常)?维修",
            r"自然损耗.{0,20}(甲方|出租方|房东|乙方|承租方|租客).{0,10}(承担|负责)",
            r"人为损坏.{0,20}(甲方|出租方|房东|乙方|承租方|租客).{0,10}(承担|负责)",
            r"维修责任.{0,40}",
            r"修缮.{0,30}",
            r"养护.{0,30}",
        ]
        maint = ""
        for p in maint_patterns:
            m = re.search(p, text)
            if m:
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 60)
                maint = text[start:end].strip()
                break

        if not maint:
            maint = _get_section("维修|养护|修缮")

        if maint:
            clauses["maintenance"]["text"] = maint
            # 房东维修责任判断
            if re.search(r"(出租方|甲方|房东)\s*(负责|承担|修缮)", maint):
                clauses["maintenance"]["landlord_responsibility"] = True
            elif re.search(r"维修.{0,5}(由|归).{0,10}(甲方|出租方|房东)", maint):
                clauses["maintenance"]["landlord_responsibility"] = True
            elif re.search(r"自然损耗.{0,20}(甲方|出租方|房东).{0,10}(承担|负责|修缮)", maint):
                clauses["maintenance"]["landlord_responsibility"] = True
            elif re.search(r"(承租方|乙方|租客)\s*(全部|均|自行)?负责", maint):
                clauses["maintenance"]["landlord_responsibility"] = False
            elif re.search(r"维修.{0,5}(由|归).{0,10}(乙方|承租方|租客)", maint):
                clauses["maintenance"]["landlord_responsibility"] = False

            # 租客维修责任判断
            if re.search(r"(承租方|乙方|租客)\s*(负责|承担).{0,10}(日常)?维修", maint):
                clauses["maintenance"]["tenant_responsibility"] = True
            elif re.search(r"维修.{0,5}(由|归).{0,10}(乙方|承租方|租客)", maint):
                clauses["maintenance"]["tenant_responsibility"] = True
            elif re.search(r"人为损坏.{0,20}(乙方|承租方|租客).{0,10}(承担|负责)", maint):
                clauses["maintenance"]["tenant_responsibility"] = True
            elif re.search(r"(日常|小型|日常维护).{0,10}(乙方|承租方|租客).{0,10}(负责|承担)", maint):
                clauses["maintenance"]["tenant_responsibility"] = True
            elif re.search(r"(出租方|甲方|房东).{0,10}(负责|承担).{0,10}(全部|所有).{0,10}维修", maint):
                clauses["maintenance"]["tenant_responsibility"] = False

        # 装修/改造 — 增强正则匹配
        deco_patterns = [
            r"(?:不得|禁止|不允许|不能).{0,6}装修",
            r"(?:经|经甲方|经出租方|经房东)(?:书面)?同意.{0,10}(?:可|可以|方可)?装修",
            r"(?:乙方|承租人|租客).{0,10}不得.{0,6}装修",
            r"(?:恢复原状|恢复原有状态|恢复原样)",
            r"装修.{0,30}",
            r"改造.{0,30}",
            r"改建.{0,30}",
            r"装饰.{0,30}",
        ]
        deco = ""
        for p in deco_patterns:
            m = re.search(p, text)
            if m:
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 60)
                deco = text[start:end].strip()
                break

        if not deco:
            deco = _get_section("装修|改造|改建|装饰")

        if deco:
            clauses["decoration"]["text"] = deco
            if re.search(r"不得.{0,6}装修|禁止装修|不允许装修|不能装修", deco):
                clauses["decoration"]["allowed"] = False
            elif re.search(r"经.{0,6}同意.{0,10}(可|可以)?装修|允许装修|可以装修", deco):
                clauses["decoration"]["allowed"] = True

            # 恢复原状判断
            if re.search(r"恢复原状|恢复原有状态|恢复原样|恢复原来", deco):
                clauses["decoration"]["restore_required"] = True
            elif clauses["decoration"]["allowed"] is True:
                # 允许装修但未要求恢复原状
                if not re.search(r"恢复原状|恢复原有状态|恢复原样", text):
                    clauses["decoration"]["restore_required"] = False

        # 逾期违约金
        default_penalty = re.search(r"(逾期|违约)\s*(违约金|罚金|滞纳金).{0,100}", text)
        if default_penalty:
            snippet = default_penalty.group(0).strip()
            clauses["default_penalty"]["text"] = snippet
            amt = _extract_amount(snippet)
            clauses["default_penalty"]["amount"] = amt

        # 查验/验收 — 增强匹配（含入住查验/房屋交接/入住确认）
        inspect_patterns = [
            r"入住查验.{0,80}",
            r"房屋交接.{0,80}",
            r"入住确认.{0,80}",
            r"入住验收.{0,80}",
            r"交房验收.{0,80}",
            r"房屋查验.{0,80}",
            r"(查验|验收|交接).{0,100}",
        ]
        inspect_text = ""
        for p in inspect_patterns:
            m = re.search(p, text)
            if m:
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 30)
                inspect_text = text[start:end].strip()
                break

        if inspect_text:
            clauses["inspection"]["text"] = inspect_text
            clauses["inspection"]["has_clause"] = True
            # 入住查验专项
            if re.search(r"入住查验|房屋交接|入住确认|入住验收|交房验收|房屋查验", inspect_text):
                clauses["inspection"]["has_inspection_clause"] = True
            else:
                clauses["inspection"]["has_inspection_clause"] = True  # 有查验/验收/交接也算
        else:
            clauses["inspection"]["has_inspection_clause"] = False

    # ------------------------------------------------------------------
    # LLM 补充提取
    # ------------------------------------------------------------------

    def _llm_supplement(self, text: str, result: dict):
        """
        对规则引擎未命中的字段，构造 prompt 让 LLM 补充提取。
        只提取仍为空（None 或空字符串）的字段。
        """
        missing_keys = self._collect_missing_for_llm(result)
        if not missing_keys:
            return

        prompt = self._build_llm_prompt(text, missing_keys)
        system = (
            "你是一个专业的 Chinese rental contract information extractor. "
            "从给出的合同文本中提取指定字段，以 JSON 格式输出。"
            "不要输出 JSON 以外的任何内容。"
        )

        try:
            raw = self.llm.generate(prompt, system=system)
            parsed = self._parse_llm_json(raw)
            if parsed:
                self._merge_llm_result(result, parsed)
        except Exception as e:
            logger.warning("LLM 补充提取失败: %s", e)

    def _collect_missing_for_llm(self, result: dict) -> list[str]:
        """收集需要 LLM 补充的字段路径"""
        missing = []
        for section, fields in result.items():
            if section == "missing_fields":
                continue
            if isinstance(fields, dict):
                for k, v in fields.items():
                    if v is None or v == "" or (isinstance(v, list) and len(v) == 0):
                        missing.append(f"{section}.{k}")
        return missing

    def _build_llm_prompt(self, text: str, missing_keys: list[str]) -> str:
        """构造 LLM 提取 prompt"""
        # 截断超长文本，保留前后各 2000 字
        if len(text) > 4000:
            truncated = text[:2000] + "\n...（中间省略）...\n" + text[-2000:]
        else:
            truncated = text

        prompt = (
            "请从以下中国房屋租赁合同中提取这些字段：\n"
            + "\n".join(f"  - {k}" for k in missing_keys)
            + "\n\n合同内容：\n```\n" + truncated + "\n```\n\n"
            "输出 JSON，字段名用英文，金额用数字（float），"
            "日期用 'YYYY年MM月DD日' 格式，无法提取的字段设为 null。"
        )
        return prompt

    def _parse_llm_json(self, raw: str) -> dict | None:
        """从 LLM 输出中提取 JSON"""
        try:
            # 找 ```json ... ``` 代码块
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
            if m:
                return json.loads(m.group(1))
            # 直接解析
            return json.loads(raw)
        except Exception:
            return None

    def _merge_llm_result(self, result: dict, llm_data: dict):
        """
        将 LLM 提取结果合并到 result 中。
        规则优先：只在 result 中对应字段为 None/空 时才写入。
        """
        for section, fields in llm_data.items():
            if section not in result:
                continue
            if not isinstance(fields, dict):
                continue
            for k, v in fields.items():
                if k not in result[section]:
                    continue
                current = result[section][k]
                if current is None or current == "" or (isinstance(current, list) and len(current) == 0):
                    result[section][k] = v

    # ------------------------------------------------------------------
    # 后处理
    # ------------------------------------------------------------------

    def _post_process(self, result: dict):
        """脱敏、类型修正等后处理"""
        # 身份证脱敏
        parties = result["parties"]
        if parties["landlord_id"]:
            parties["landlord_id"] = _mask_id_card(parties["landlord_id"])
        if parties["tenant_id"]:
            parties["tenant_id"] = _mask_id_card(parties["tenant_id"])

        # 金额字段确保为 float
        fin = result["financial"]
        for key in ["monthly_rent", "deposit", "agent_fee"]:
            if fin[key] is not None:
                try:
                    fin[key] = float(fin[key])
                except (ValueError, TypeError):
                    fin[key] = None

        # payment_date 确保为 int
        if fin["payment_date"] is not None:
            try:
                fin["payment_date"] = int(fin["payment_date"])
            except (ValueError, TypeError):
                fin["payment_date"] = None

    def _check_missing(self, result: dict):
        """检查哪些关键字段仍未提取，记入 missing_fields"""
        important = [
            ("parties.landlord_name", "房东姓名"),
            ("parties.tenant_name", "租客姓名"),
            ("property.address", "房屋地址"),
            ("financial.monthly_rent", "月租金"),
            ("financial.deposit", "押金"),
            ("term.start_date", "起租日期"),
            ("term.end_date", "到期日期"),
        ]
        missing = []
        for path, label in important:
            section, field = path.split(".", 1)
            if not result.get(section, {}).get(field):
                missing.append(label)

        # 增强缺失检测 — 条款类和附属类
        enhanced_checks = [
            ("入住查验记录", lambda: not result.get("clauses", {}).get("inspection", {}).get("has_inspection_clause")),
            ("家具清单", lambda: not result.get("property", {}).get("furniture") or len(result.get("property", {}).get("furniture", [])) == 0),
            ("钥匙交接", lambda: not self._text_has_keyword(result, r"钥匙|门禁|门卡|门锁")),
            ("水电费标准", lambda: not result.get("financial", {}).get("utility_responsibility")),
            ("押金退还条件", lambda: not self._text_has_keyword(result, r"退还|结算|退回|返还")),
        ]
        for label, check_fn in enhanced_checks:
            if check_fn():
                missing.append(label)

        result["missing_fields"] = missing

    def _text_has_keyword(self, result: dict, pattern: str) -> bool:
        """检查条款文本中是否包含指定关键词模式"""
        # 检查各个条款的 text 字段
        for clause_name, clause_data in result.get("clauses", {}).items():
            if isinstance(clause_data, dict) and clause_data.get("text"):
                if re.search(pattern, str(clause_data["text"])):
                    return True
        # 检查财务相关字段
        for fin_key in ["utility_responsibility", "property_fee"]:
            val = result.get("financial", {}).get(fin_key)
            if val and re.search(pattern, str(val)):
                return True
        # 检查续租条款
        renewal = result.get("term", {}).get("renewal_clause")
        if renewal and re.search(pattern, str(renewal)):
            return True
        return False
