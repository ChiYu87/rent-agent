"""对话路由"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from api.models import ChatRequest, ChatResponse
from src.core.agent import ReActAgent
from src.utils.db import Database

router = APIRouter(prefix="/chat", tags=["对话"])

# 线程池：LLM 调用是阻塞的，放线程池里不卡事件循环
_executor = ThreadPoolExecutor(max_workers=4)

# Agent 缓存：同一用户的同一个 session 复用 Agent
_agents: dict[str, ReActAgent] = {}


def _get_agent(user_id: str, session_id: str = None) -> ReActAgent:
    """获取或创建 Agent 实例"""
    cache_key = f"{user_id}:{session_id}" if session_id else user_id
    if cache_key not in _agents:
        agent = ReActAgent(user_id)
        if session_id:
            agent.session_id = session_id
        _agents[cache_key] = agent
    return _agents[cache_key]


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    对话接口
    
    - user_id: 用户唯一标识
    - message: 用户消息
    - session_id: 可选，指定会话ID（为空则创建新会话）
    """
    agent = _get_agent(req.user_id, req.session_id)
    session_id = agent.session_id

    # 在线程池中执行（LLM 调用是阻塞的）
    loop = asyncio.get_event_loop()
    try:
        reply = await loop.run_in_executor(
            _executor,
            agent.run,
            req.message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {e}")

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        user_id=req.user_id,
    )


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """流式对话接口（SSE）"""
    from fastapi.responses import StreamingResponse
    import json

    agent = _get_agent(req.user_id, req.session_id)
    session_id = agent.session_id

    async def generate():
        loop = asyncio.get_event_loop()
        import queue
        q = queue.Queue()

        def run_stream():
            try:
                for chunk in agent.run_stream(req.message):
                    q.put(chunk)
            except Exception as e:
                q.put(f"[ERROR] {e}")
            finally:
                q.put(None)

        import threading
        t = threading.Thread(target=run_stream, daemon=True)
        t.start()

        while True:
            chunk = await loop.run_in_executor(_executor, q.get)
            if chunk is None:
                break
            yield f"data: {json.dumps({'chunk': chunk, 'session_id': session_id}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/session/new")
async def new_session(user_id: str):
    """创建新会话"""
    cache_key = user_id
    if cache_key in _agents:
        del _agents[cache_key]
    agent = _get_agent(user_id)
    return {"session_id": agent.session_id, "user_id": user_id}


@router.get("/history")
async def get_history(user_id: str, session_id: str, limit: int = 50):
    """获取对话历史"""
    db = Database()
    messages = db.get_messages(user_id, session_id, limit)
    return {"messages": messages, "count": len(messages)}
