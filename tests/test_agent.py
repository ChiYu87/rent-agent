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
    assert "🚨" in result or "⚠️" in result
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


if __name__ == "__main__":
    test_config()
    test_database()
    test_tools()
    test_memory()
    print("\n🎉 所有测试通过！")
