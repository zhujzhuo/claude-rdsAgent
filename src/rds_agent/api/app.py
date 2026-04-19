"""FastAPI Web API应用。"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rds_agent import __version__, settings
from rds_agent.core import get_agent, RDSAgent
from rds_agent.scheduler import router as scheduler_router
from rds_agent.scheduler.api import init_scheduler
from rds_agent.utils.logger import get_logger

logger = get_logger("api")


# 请求模型
class ChatRequest(BaseModel):
    """聊天请求"""

    message: str
    thread_id: Optional[str] = None
    instance: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应"""

    response: str
    thread_id: str
    intent: str
    instance: Optional[str] = None


# Agent实例
agent: Optional[RDSAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化Agent
    global agent
    logger.info("初始化RDS Agent...")
    try:
        agent = get_agent()
        logger.info("RDS Agent初始化成功")
    except Exception as e:
        logger.error(f"Agent初始化失败: {e}")
        agent = None

    # 初始化调度器组件
    try:
        init_scheduler()
        logger.info("调度器组件初始化成功")
    except Exception as e:
        logger.error(f"调度器初始化失败: {e}")

    yield

    # 关闭时清理
    logger.info("关闭RDS Agent")


# 创建FastAPI应用
app = FastAPI(
    title="RDS Agent API",
    description="MySQL数据库智能问答助手API",
    version=__version__,
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册调度器路由
app.include_router(scheduler_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "RDS Agent",
        "version": __version__,
        "status": "running",
        "model": settings.ollama.model,
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "ollama_host": settings.ollama.host,
    }


@app.get("/config")
async def get_config():
    """获取配置信息"""
    return {
        "ollama": {
            "host": settings.ollama.host,
            "model": settings.ollama.model,
            "embed_model": settings.ollama.embed_model,
        },
        "instance_platform": {
            "url": settings.instance_platform.url,
            "configured": bool(settings.instance_platform.url),
        },
        "agent": {
            "max_iterations": settings.agent.max_iterations,
            "timeout_seconds": settings.agent.timeout_seconds,
        },
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 生成或使用现有thread_id
    thread_id = request.thread_id or str(uuid.uuid4())

    try:
        # 调用Agent
        result = agent.invoke(request.message, thread_id)

        return ChatResponse(
            response=result.get("response", "无法生成响应"),
            thread_id=thread_id,
            intent=result.get("intent", "unknown"),
            instance=result.get("target_instance"),
        )
    except Exception as e:
        logger.error(f"聊天处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    thread_id = request.thread_id or str(uuid.uuid4())

    async def generate():
        try:
            for event in agent.stream(request.message, thread_id):
                # 获取事件中的响应内容
                for node_name, state in event.items():
                    if node_name == "respond":
                        response = state.get("response", "")
                        yield f"data: {response}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/reset")
async def reset_session(thread_id: str):
    """重置会话"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    try:
        agent.reset(thread_id)
        return {"status": "reset", "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/instances")
async def list_instances():
    """获取实例列表"""
    from rds_agent.tools.instance import get_instance_list

    try:
        result = get_instance_list.invoke({})
        import json
        return json.loads(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/instances/{instance_name}")
async def get_instance_info(instance_name: str):
    """获取实例信息"""
    from rds_agent.tools.instance import get_instance_info

    try:
        result = get_instance_info.invoke({"instance_name": instance_name})
        import json
        return json.loads(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))