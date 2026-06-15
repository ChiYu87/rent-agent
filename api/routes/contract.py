"""合同审查路由"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from api.models import ContractReviewRequest, ContractReviewResponse
from src.core.agent import ReActAgent
from src.utils.db import Database

router = APIRouter(prefix="/contract", tags=["合同审查"])


@router.post("/review", response_model=ContractReviewResponse)
async def review_contract(req: ContractReviewRequest):
    """
    合同文本审查
    
    - 上传合同文本，返回本地规则扫描 + AI 深度审查结果
    """
    agent = ReActAgent(req.user_id)
    try:
        result = agent.review_contract_text(req.contract_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审查失败: {e}")

    return ContractReviewResponse(**result)


@router.post("/upload")
async def upload_contract(user_id: str, file: UploadFile = File(...)):
    """
    上传合同文件审查
    
    - 支持 .txt / .pdf 文件
    """
    content = await file.read()

    # 解析文件
    if file.filename.endswith(".pdf"):
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
            except:
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
