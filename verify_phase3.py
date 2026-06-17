#!/usr/bin/env python3
"""Phase 3 端到端验证"""
import json
from src.core.contract_parser import ContractParser
from src.core.risk_engine import ContractReviewer

SAMPLE = """房屋租赁合同

甲方（出租方）：张三
乙方（承租方）：李四

房屋地址：北京市朝阳区建国路88号
建筑面积：85平方米

月租金人民币3500元
押金为人民币7000元
中介费3500元
付款方式：押二付三

租赁期限：2026年1月1日至2027年12月31日

不得转租
维修由甲方负责，自然损耗由甲方承担
不得装修
押金概不退还
每天收取千分之五滞纳金
甲方有权随时进入房屋查看
"""

parser = ContractParser()
info = parser.extract(SAMPLE)

print("=== 条款提取 ===")
for key in ["sublease", "maintenance", "decoration"]:
    clause = info["clauses"].get(key, {})
    print(f"  {key}: allowed={clause.get('allowed')}, text={clause.get('text')}")

print(f"  inspection: has={info['clauses'].get('inspection', {}).get('has_clause')}")
print(f"  renewal: {info['term'].get('renewal_clause')}")

reviewer = ContractReviewer()
report = reviewer.review(SAMPLE, enable_ai_review=False)

print(f"\n=== 风险评分 ===")
print(f"  Score: {report['score']}/100")
print(f"  Level: {report['risk_level_code']}")
print(f"  Risks: {len(report['risks'])} (high={sum(1 for r in report['risks'] if r['level']=='high')})")
print(f"  Missing: {len(report['missing'])}")

print(f"\n=== AI 深度审查 ===")
ai = report.get("ai_review", "")
if isinstance(ai, dict):
    print(f"  Summary: {ai.get('summary', 'N/A')[:100]}")
    print(f"  Key risks: {len(ai.get('key_risks', []))}")
    print(f"  Tips: {len(ai.get('negotiation_tips', []))}")
elif isinstance(ai, str):
    print(f"  {ai[:200] if ai else 'N/A'}")

print(f"\n=== 谈判话术 ===")
speech = report.get("negotiation_speech", [])
print(f"  话术数量: {len(speech)}")
for s in speech[:3]:
    print(f"  [{s.get('risk_id')}] {s.get('title')}: {s.get('speech', '')[:60]}... (tone={s.get('tone')})")

print(f"\n=== 标准对比 ===")
# 检查 missing 里是否有 match 字段
for m in report.get("missing", [])[:5]:
    match = m.get("match", "N/A")
    std = m.get("standard", "N/A")
    print(f"  {m.get('field')}: standard={std}, match={match}")

print("\n=== PASS ===")
