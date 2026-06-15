"""工具路由 - 费用计算、看房清单、黑名单、城市政策"""
from fastapi import APIRouter
from api.models import (
    CostCalcRequest, DepositCalcRequest,
    ChecklistRequest, ViewingSaveRequest,
    BlacklistCheckRequest, BlacklistReportRequest,
    UserProfileUpdate,
)
from src.core.tools import (
    calc_rent_cost, calc_deposit_return, get_checklist,
    check_blacklist, add_blacklist, city_rules,
    generate_speech, calc_commute,
)
from src.utils.db import Database

router = APIRouter(prefix="/tools", tags=["工具"])


# ==================== 费用计算 ====================

@router.post("/cost")
async def calc_cost(req: CostCalcRequest):
    """租房真实成本计算"""
    result = calc_rent_cost(
        rent=req.rent,
        deposit=req.deposit,
        agent_fee=req.agent_fee,
        utilities=req.utilities,
        property_fee=req.property_fee,
        payment_cycle=req.payment_cycle,
    )
    return {"result": result}


@router.post("/deposit")
async def calc_deposit(req: DepositCalcRequest):
    """押金退还模拟"""
    result = calc_deposit_return(
        deposit=req.deposit,
        contract_months=req.contract_months,
        has_damage=req.has_damage,
        early_termination=req.early_termination,
    )
    return {"result": result}


# ==================== 看房清单 ====================

@router.post("/checklist")
async def get_checklist_api(req: ChecklistRequest):
    """获取看房检查清单"""
    result = get_checklist(req.phase)
    return {"checklist": result, "phase": req.phase}


@router.post("/viewing/save")
async def save_viewing(req: ViewingSaveRequest):
    """保存看房记录"""
    db = Database()
    viewing_id = db.add_viewing(
        user_id=req.user_id,
        address=req.address,
        checklist=req.checklist,
        photos=req.photos,
        notes=req.notes,
        score=req.score,
    )
    return {"id": viewing_id, "status": "saved"}


@router.get("/viewing/list")
async def list_viewings(user_id: str, limit: int = 20):
    """获取看房记录列表"""
    db = Database()
    return {"viewings": db.get_viewings(user_id, limit)}


# ==================== 黑名单 ====================

@router.post("/blacklist/check")
async def check_blacklist_api(req: BlacklistCheckRequest):
    """查询黑名单"""
    db = Database()
    results = db.check_blacklist(req.name, req.city)
    return {"results": results, "count": len(results)}


@router.post("/blacklist/report")
async def report_blacklist(req: BlacklistReportRequest):
    """匿名上报黑中介/黑房东"""
    db = Database()
    db.add_blacklist_entry(
        name=req.name,
        type_=req.type,
        reason=req.reason,
        city=req.city,
        reported_by=req.user_id,
    )
    return {"status": "reported", "message": "感谢你的反馈，这将帮助其他人避坑！"}


@router.get("/blacklist/stats")
async def blacklist_stats():
    """黑名单统计"""
    db = Database()
    return db.get_blacklist_stats()


# ==================== 城市政策 ====================

@router.get("/city-rules")
async def get_city_rules(city: str = "北京"):
    """查询城市租房政策"""
    result = city_rules(city)
    return {"rules": result, "city": city}


# ==================== 话术生成 ====================

@router.get("/speech")
async def get_speech(situation: str = "问价格"):
    """生成'假装很懂'的沟通话术"""
    result = generate_speech(situation)
    return {"speech": result, "situation": situation}


# ==================== 通勤估算 ====================

@router.get("/commute")
async def calc_commute_api(distance_km: float = 5.0, method: str = "地铁"):
    """通勤时间估算"""
    result = calc_commute(distance_km, method)
    return {"result": result}


# ==================== 用户偏好 ====================

@router.post("/profile")
async def update_profile(req: UserProfileUpdate):
    """更新用户偏好"""
    db = Database()
    db.set_profile(req.user_id, req.key, req.value)
    return {"status": "updated"}


@router.get("/profile")
async def get_profile(user_id: str):
    """获取用户偏好"""
    db = Database()
    profiles = db.get_all_profiles(user_id)
    return {"profiles": profiles}
