"""基础测试 - 适配多用户版"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 清除单例缓存，避免测试间污染
from src.utils.db import Database
from src.utils.config import Config
from src.core.llm import LLM
from src.core.embedder import Embedder

Database._instance = None
Config._instance = None
Config._data = None
LLM._instance = None
Embedder._instance = None


def test_database():
    """测试数据库（含 user_id）"""
    db = Database()

    # 用户管理
    user = db.ensure_user("test_user_001", "测试用户")
    assert user["user_id"] == "test_user_001"
    print("✅ 用户创建通过")

    # 对话（带 user_id）
    db.add_message("test_user_001", "session_1", "user", "你好")
    db.add_message("test_user_001", "session_1", "assistant", "你好！我是租房助手")
    messages = db.get_messages("test_user_001", "session_1")
    assert len(messages) >= 2
    print("✅ 对话存储通过")

    # 用户隔离：另一个用户看不到 user_001 的消息
    db.add_message("test_user_002", "session_1", "user", "我是另一个用户")
    messages_2 = db.get_messages("test_user_002", "session_1")
    # user_002 只能看到自己的消息（之前测试可能残留数据）
    assert all(m["user_id"] == "test_user_002" for m in messages_2)
    print("✅ 用户隔离通过")

    # 用户偏好
    db.set_profile("test_user_001", "city", "北京")
    db.set_profile("test_user_001", "budget", "3000")
    assert db.get_profile("test_user_001", "city") == "北京"
    profiles = db.get_all_profiles("test_user_001")
    assert "city" in profiles
    print("✅ 用户偏好通过")

    # 黑名单
    db.add_blacklist_entry("某黑中介", "中介", "押金不退", "北京", "test_user_001")
    results = db.check_blacklist("某黑中介", "北京")
    assert len(results) >= 1
    stats = db.get_blacklist_stats()
    assert stats["total"] >= 1
    print("✅ 黑名单通过")


def test_tools():
    """测试工具函数"""
    from src.core.tools import calc_rent_cost, calc_deposit_return, get_checklist, review_contract

    result = calc_rent_cost(3000, agent_fee=1500, utilities=200, payment_cycle="押一付三")
    assert "月租金" in result
    print("✅ 费用计算通过")

    result = calc_deposit_return(3000, early_termination="否")
    assert "退租" in result
    print("✅ 押金模拟通过")

    result = get_checklist("看房中")
    assert "水电" in result or "采光" in result
    print("✅ 看房清单通过")

    contract = "押金概不退还。乙方不得养宠物。每天收取千分之五滞纳金。"
    result = review_contract(contract)
    assert "风险" in result or "⚠️" in result or "🟡" in result or "🟠" in result or "🔴" in result
    print("✅ 合同审查通过")


def test_config():
    """测试配置"""
    cfg = Config()
    assert cfg.get("llm.model") == ""  # 留空自动检测
    print("✅ 配置测试通过")


def test_memory():
    """测试记忆系统"""
    from src.core.memory import Memory

    mem = Memory("test_user_001")
    mem.save_interaction("test_mem_session", "我预算3000", "好的，已记住你的预算")
    context = mem.get_context("test_mem_session", "预算")
    assert len(context) > 0
    print("✅ 记忆系统通过")


def test_contract_parser():
    """测试合同结构化提取"""
    from src.core.contract_parser import ContractParser
    parser = ContractParser()
    sample = """房屋租赁合同

甲方（出租方）：张三
身份证号：110101199001011234
乙方（承租方）：李四
身份证号：310101199505052345

第一条 房屋基本情况
房屋坐落：北京市朝阳区建国路88号3栋502室
建筑面积：65.5㎡
户型：2室1厅1卫
家具：空调、洗衣机、冰箱、热水器、床、衣柜、沙发
房屋现状：精装修，保养良好

第二条 租赁期限
租赁期限自2025年1月1日至2026年12月31日，共计24个月。

第三条 租金及支付方式
月租金：人民币3500元
押金：人民币3500元
付款方式：押一付三
每月5日前支付当月租金。
水电费由乙方承担，物业费由甲方承担。

第四条 维修责任
房屋主体结构及自然损耗由甲方负责修缮，日常维护及人为损坏由乙方负责维修。

第五条 装修条款
经甲方书面同意，乙方可以对房屋进行装修，退租时应恢复原状。

第六条 转租条款
未经甲方书面同意，乙方不得将房屋转租、转借给他人。

第七条 续租条款
租赁期满，乙方在同等条件下享有优先续租权。

第八条 入住查验
入住时甲乙双方应进行房屋查验，确认房屋现状及家具设备情况。

第九条 违约责任
提前退租，押金不予退还。逾期支付租金，每日按月租金的千分之五收取滞纳金。
"""
    info = parser.extract(sample)

    # 当事人
    assert info["parties"]["landlord_name"] is not None, "房东姓名未提取"
    assert info["parties"]["tenant_name"] is not None, "租客姓名未提取"

    # 财务
    assert info["financial"]["monthly_rent"] is not None, "月租金未提取"
    assert info["financial"]["deposit"] is not None, "押金未提取"
    assert info["financial"]["payment_cycle"] is not None, "付款方式未提取"

    # 条款 - 转租
    sub = info["clauses"]["sublease"]
    assert sub["text"] is not None or sub["allowed"] is not None, "转租条款未提取"
    assert sub["allowed"] is False, f"转租条款 allowed 应为 False，实际为 {sub['allowed']}"

    # 条款 - 维修
    maint = info["clauses"]["maintenance"]
    assert maint["text"] is not None or maint["landlord_responsibility"] is not None, "维修条款未提取"
    assert maint["landlord_responsibility"] is True, f"甲方维修责任应为 True，实际为 {maint['landlord_responsibility']}"
    assert maint["tenant_responsibility"] is True, f"乙方维修责任应为 True，实际为 {maint['tenant_responsibility']}"

    # 条款 - 装修
    deco = info["clauses"]["decoration"]
    assert deco["text"] is not None or deco["allowed"] is not None, "装修条款未提取"
    assert deco["allowed"] is True, f"装修 allowed 应为 True，实际为 {deco['allowed']}"
    assert deco["restore_required"] is True, f"装修恢复原状应为 True，实际为 {deco['restore_required']}"

    # 条款 - 入住查验
    insp = info["clauses"]["inspection"]
    assert insp["has_clause"] is True, "入住查验条款未检测到"
    assert insp["has_inspection_clause"] is True, "入住查验专项未检测到"

    # 续租
    assert info["term"]["renewal_clause"] is not None, "续租条款未提取"
    assert "续租" in info["term"]["renewal_clause"], f"续租条款内容异常: {info['term']['renewal_clause']}"

    print("✅ 合同结构化提取通过")


def test_risk_engine():
    """测试风险评分"""
    from src.core.risk_engine import ContractReviewer
    reviewer = ContractReviewer()
    sample = """房屋租赁合同

甲方（出租方）：王五
身份证号：110101198501011234
乙方（承租方）：赵六
身份证号：310101199505052345

房屋坐落：上海市浦东新区世纪大道100号
月租金：人民币5000元
押金：人民币15000元
付款方式：押三付六

未经甲方同意不得转租。
所有维修费用均由乙方承担。
不得装修。
押金概不退还。
每天收取千分之五滞纳金。
"""
    report = reviewer.review(sample, enable_ai_review=False)

    # 评分范围
    assert 0 <= report["score"] <= 100, f"评分超出范围: {report['score']}"
    assert report["risk_level_code"] in ["safe", "caution", "warning", "danger"], \
        f"风险等级异常: {report['risk_level_code']}"

    # 基本结构
    assert isinstance(report["risks"], list), "risks 应为列表"
    assert isinstance(report["missing"], list), "missing 应为列表"
    assert isinstance(report.get("negotiation_speech", []), list), "negotiation_speech 应为列表"
    assert isinstance(report.get("ai_review", ""), (str, dict)), "ai_review 应为字符串或字典"

    # 高风险合同应该评分较低
    assert report["score"] < 70, f"高风险合同评分应低于70，实际为 {report['score']}"
    assert report["risk_level_code"] in ["warning", "danger"], \
        f"高风险合同应为 warning/danger，实际为 {report['risk_level_code']}"

    # 应检测到风险项
    assert len(report["risks"]) > 0, "应检测到风险项"

    print("✅ 风险评分测试通过")


if __name__ == "__main__":
    test_config()
    test_database()
    test_tools()
    test_memory()
    test_contract_parser()
    test_risk_engine()
    print("\n🎉 所有测试通过！")
