"""基础测试"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_tools():
    """测试工具函数"""
    from src.core.tools import calc_rent_cost, calc_deposit_return, get_checklist, review_contract

    # 1. 费用计算
    print("=" * 40)
    print("测试费用计算")
    result = calc_rent_cost(3000, agent_fee=1500, utilities=200, payment_cycle="押一付三")
    print(result)
    assert "月租金" in result
    assert "9000" in result  # 首期3个月
    print("✅ 通过")

    # 2. 押金退还
    print("=" * 40)
    print("测试押金退还")
    result = calc_deposit_return(3000, early_termination="否")
    print(result)
    assert "退租" in result
    print("✅ 通过")

    # 3. 看房清单
    print("=" * 40)
    print("测试看房清单")
    result = get_checklist("看房中")
    print(result)
    assert "水电" in result or "采光" in result
    print("✅ 通过")

    # 4. 合同审查
    print("=" * 40)
    print("测试合同审查")
    contract = "押金概不退还。乙方不得养宠物。每天收取千分之五滞纳金。"
    result = review_contract(contract)
    print(result)
    assert "🚨" in result or "⚠️" in result
    print("✅ 通过")


def test_database():
    """测试数据库"""
    from src.utils.db import Database
    import tempfile

    # 用临时数据库
    db = Database()
    db.add_message("test-session", "user", "你好")
    db.add_message("test-session", "assistant", "你好！我是租房助手")

    messages = db.get_messages("test-session")
    assert len(messages) >= 2
    print("✅ 数据库测试通过")

    # 用户偏好
    db.set_profile("city", "北京")
    assert db.get_profile("city") == "北京"
    print("✅ 用户偏好测试通过")

    # 黑名单
    db.add_blacklist_entry("某黑中介", "中介", "押金不退", "北京")
    results = db.check_blacklist("某黑中介", "北京")
    assert len(results) >= 1
    print("✅ 黑名单测试通过")


def test_config():
    """测试配置"""
    from src.utils.config import Config
    cfg = Config()
    assert cfg.get("llm.model") == "qwen2.5"
    assert cfg.get("city") == "北京"
    print("✅ 配置测试通过")


if __name__ == "__main__":
    test_config()
    test_database()
    test_tools()
    print("\n🎉 所有测试通过！")
