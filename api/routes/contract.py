"""合同审查路由"""
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from api.models import ContractReviewRequest, ContractReviewResponse
from src.core.agent import ReActAgent
from src.core.ocr import ContractOCR
from src.core.risk_engine import ContractReviewer
from src.utils.db import Database

router = APIRouter(prefix="/contract", tags=["合同审查"])

# OCR 引擎（延迟初始化，全局复用）
_ocr_engine = None


def _get_ocr() -> ContractOCR:
    """获取 OCR 引擎实例（懒加载单例）"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = ContractOCR()
    return _ocr_engine


# 文件大小限制：10MB
MAX_FILE_SIZE = 10 * 1024 * 1024
# 最多9张图片
MAX_IMAGES = 9


@router.post("/review", response_model=ContractReviewResponse)
async def review_contract(req: ContractReviewRequest):
    """
    合同文本审查（旧接口，保持向后兼容）

    - 上传合同文本，返回本地规则扫描 + AI 深度审查结果
    """
    agent = ReActAgent(req.user_id)
    try:
        result = agent.review_contract_text(req.contract_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审查失败: {e}")

    return ContractReviewResponse(**result)


@router.post("/review/text", response_model=ContractReviewResponse)
async def review_contract_text(req: ContractReviewRequest):
    """
    文本合同审查（结构化提取 + 风险评分）

    - 替代原有 /review 接口，返回更丰富的结构化结果
    """
    reviewer = ContractReviewer(user_id=req.user_id)

    # 同步执行审查
    loop = asyncio.get_event_loop()
    report = await loop.run_in_executor(
        None,
        lambda: reviewer.review(req.contract_text, enable_ai_review=False)
    )

    # 兼容旧字段
    report.setdefault("local_scan", report.get("summary", ""))
    report.setdefault("risk_level", report.get("risk_level_code", "low"))
    report.setdefault("negotiation_speech", [])

    # 保存审查记录
    db = Database()
    db.add_contract(
        req.user_id,
        "",
        req.contract_text[:500],
        {"score": report["score"], "risks": len(report.get("risks", []))},
        report.get("risk_level_code", "low"),
    )

    return ContractReviewResponse(**report)


@router.post("/review/upload", response_model=ContractReviewResponse)
async def review_contract_upload(
    user_id: str = Query(..., description="用户ID"),
    files: list[UploadFile] = File(..., description="合同图片，最多9张"),
):
    """
    上传合同图片审查（OCR + 结构化提取 + 风险评分）

    - 支持多张图片（多页合同），最多9张
    - 单张图片不超过10MB
    - 支持 jpg/png/bmp 等常见图片格式
    """
    if len(files) > MAX_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"最多上传{MAX_IMAGES}张图片，当前{len(files)}张"
        )

    # 1. 读取图片
    image_data_list = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"图片 {f.filename} 超过10MB限制"
            )
        image_data_list.append(content)

    if not image_data_list:
        raise HTTPException(status_code=400, detail="未提供图片")

    # 2. OCR 识别（同步操作，使用线程池）
    ocr = _get_ocr()
    loop = asyncio.get_event_loop()
    ocr_result = await loop.run_in_executor(
        None,
        lambda: ocr.recognize_images(image_data_list)
    )

    # 检查 OCR 结果
    full_text = ocr_result.get("full_text", "")
    if not full_text.strip():
        error_msg = ocr_result.get("pages", [{}])[0].get("error", "") if ocr_result.get("pages") else ""
        if "不可用" in error_msg or error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"OCR 识别失败: {error_msg}。请安装 PaddleOCR 或改用文本输入。"
            )
        raise HTTPException(status_code=400, detail="OCR 未识别出文字，请确认图片清晰度")

    # 3. 结构化提取 + 风险评分
    reviewer = ContractReviewer(user_id=user_id)
    report = await loop.run_in_executor(
        None,
        lambda: reviewer.review(full_text, enable_ai_review=False)
    )

    # 4. 兼容旧字段
    report.setdefault("local_scan", report.get("summary", ""))
    report.setdefault("risk_level", report.get("risk_level_code", "low"))
    report.setdefault("negotiation_speech", [])

    # 5. 附带 OCR 结果
    report["ocr_result"] = ocr_result

    # 6. 保存审查记录
    db = Database()
    db.add_contract(
        user_id,
        "",
        full_text[:500],
        {"score": report["score"], "risks": len(report.get("risks", []))},
        report.get("risk_level_code", "low"),
    )

    return ContractReviewResponse(**report)


@router.post("/upload")
async def upload_contract(user_id: str, file: UploadFile = File(...)):
    """
    上传合同文件审查（旧接口，保持向后兼容）

    - 支持 .txt / .pdf 文件
    """
    content = await file.read()

    # 解析文件
    if file.filename and file.filename.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {e}")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except Exception:
                raise HTTPException(status_code=400, detail="文件编码不支持，请上传 UTF-8 或 GBK 文本")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    agent = ReActAgent(user_id)
    try:
        result = agent.review_contract_text(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审查失败: {e}")

    return ContractReviewResponse(**result)


@router.get("/list")
async def list_contracts(user_id: str, limit: int = 10):
    """获取用户的合同审查记录"""
    db = Database()
    return {"contracts": db.get_contracts(user_id, limit)}


@router.get("/negotiation-speech")
async def get_negotiation_speech(
    risk_ids: str = Query(..., description="风险ID列表，逗号分隔，如 A01,C01"),
):
    """
    获取指定风险的谈判话术

    - 传入风险ID列表（逗号分隔），返回对应的谈判话术
    - 话术基于预置模板+LLM生成混合策略
    """
    from src.core.risk_engine import ContractReviewer

    ids = [rid.strip() for rid in risk_ids.split(",") if rid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="请提供至少一个风险ID")

    reviewer = ContractReviewer()
    # 构造风险列表用于话术生成
    risks = []
    # 从预置模板中查找
    for rid in ids:
        template = reviewer._SPEECH_TEMPLATES.get(rid)
        if template:
            risks.append({
                "id": rid,
                "title": rid,
                "level": "high" if template["tone"] == "firm" else "medium",
            })
        else:
            # 没有模板的风险，仍生成通用话术
            risks.append({
                "id": rid,
                "title": rid,
                "level": "medium",
            })

    speeches = reviewer.generate_negotiation_speech(risks)
    return {"negotiation_speech": speeches}


@router.post("/ai-review")
async def ai_review_contract(
    req: ContractReviewRequest,
):
    """
    按需触发 AI 深度审查

    - 对已审查的合同进行 AI 深度分析
    - 带超时保护，AI 不可用时返回 fallback
    - 适合前端在用户点击"AI深度审查"按钮时调用
    """
    reviewer = ContractReviewer(user_id=req.user_id)
    parser = reviewer.parser
    contract_info = parser.extract(req.contract_text)
    contract_info["_raw_clauses"] = req.contract_text

    # 先做规则扫描获取风险列表
    from src.core.risk_engine import _detect_city_from_address, _compare_standard, _calculate_score
    city = _detect_city_from_address(contract_info["property"]["address"])
    risks = reviewer._scan_rules(contract_info, city)

    # AI 深度审查
    loop = asyncio.get_event_loop()
    ai_result = await loop.run_in_executor(
        None,
        lambda: reviewer._do_ai_review(contract_info, risks)
    )

    # 谈判话术（AI 模式）
    speech = await loop.run_in_executor(
        None,
        lambda: reviewer.generate_negotiation_speech(risks)
    )

    return {
        "ai_review": ai_result,
        "negotiation_speech": speech,
    }
