"""Pydantic 数据模型"""
from pydantic import BaseModel, Field
from typing import Optional


# ==================== 对话 ====================

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="用户ID", min_length=1)
    message: str = Field(..., description="用户消息", min_length=1)
    session_id: Optional[str] = Field(None, description="会话ID，空则创建新会话")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    user_id: str


# ==================== 合同审查 ====================

class ContractReviewRequest(BaseModel):
    user_id: str = Field(..., description="用户ID", min_length=1)
    contract_text: str = Field(..., description="合同文本内容", min_length=10)


class ContractReviewResponse(BaseModel):
    local_scan: str
    ai_review: str
    risk_level: str  # high / medium / low


# ==================== 费用计算 ====================

class CostCalcRequest(BaseModel):
    rent: float = Field(..., description="月租金（元）", gt=0)
    deposit: Optional[float] = Field(None, description="押金金额，空=1个月租金")
    agent_fee: float = Field(0, description="中介费（元）")
    utilities: float = Field(200, description="水电燃网月均（元）")
    property_fee: float = Field(0, description="物业费月均（元）")
    payment_cycle: str = Field("押一付三", description="付款方式")


class DepositCalcRequest(BaseModel):
    deposit: float = Field(..., description="押金金额（元）", gt=0)
    contract_months: int = Field(12, description="合同月数")
    early_termination: str = Field("否", description="是否提前退租")
    has_damage: str = Field("不确定", description="是否有损坏")


# ==================== 看房清单 ====================

class ChecklistRequest(BaseModel):
    phase: str = Field("看房中", description="阶段：看房前/看房中/看房后")


class ViewingSaveRequest(BaseModel):
    user_id: str = Field(..., description="用户ID", min_length=1)
    address: str = Field(..., description="房源地址")
    checklist: dict = Field(default_factory=dict, description="检查清单")
    photos: list = Field(default_factory=list, description="照片列表")
    notes: str = Field("", description="备注")
    score: float = Field(0, description="评分")


# ==================== 黑名单 ====================

class BlacklistCheckRequest(BaseModel):
    name: str = Field(..., description="中介/房东姓名或公司名")
    city: Optional[str] = Field(None, description="城市名")


class BlacklistReportRequest(BaseModel):
    user_id: str = Field(..., description="上报者用户ID")
    name: str = Field(..., description="中介/房东姓名或公司名")
    type: str = Field(..., description="类型：中介/房东/二房东")
    reason: str = Field(..., description="踩坑原因")
    city: str = Field(..., description="城市")


# ==================== 用户 ====================

class UserProfileUpdate(BaseModel):
    user_id: str = Field(..., description="用户ID", min_length=1)
    key: str = Field(..., description="偏好键")
    value: str = Field(..., description="偏好值")
