"""JSON API routes; all Agent behavior remains in AgentApplication."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app import __version__
from app.api.schemas import CreateSessionRequest, HealthResponse, RunRequest
from app.application import AgentApplication
from app.bootstrap import ApplicationResources
from app.errors import SessionNotFoundError
from app.models import Message, RunResult, Session, TraceEvent

router = APIRouter(prefix="/api")


def get_resources(request: Request) -> ApplicationResources:
    resources = getattr(request.app.state, "resources", None)
    if resources is None:
        raise HTTPException(status_code=503, detail="Application is still starting")
    return cast(ApplicationResources, resources)


def get_application(
    resources: ApplicationResources = Depends(get_resources),
) -> AgentApplication:
    return resources.application


@router.get("/health", response_model=HealthResponse)
async def health(resources: ApplicationResources = Depends(get_resources)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_configured=resources.application.llm_configured,
        storage="sqlite:ready",
        version=__version__,
    )


@router.post("/sessions", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    application: AgentApplication = Depends(get_application),
) -> Session:
    return await application.create_session(body.title)


@router.get("/sessions", response_model=list[Session])
async def list_sessions(
    application: AgentApplication = Depends(get_application),
) -> list[Session]:
    return await application.list_sessions()


@router.get("/sessions/{session_id}/messages", response_model=list[Message])
async def list_messages(
    session_id: str,
    application: AgentApplication = Depends(get_application),
) -> list[Message]:
    try:
        return await application.get_history(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/sessions/{session_id}/runs", response_model=RunResult)
async def run_agent(
    session_id: str,
    body: RunRequest,
    application: AgentApplication = Depends(get_application),
) -> RunResult:
    try:
        return await application.run_agent(session_id, body.text)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runs/{run_id}/trace", response_model=list[TraceEvent])
async def get_trace(
    run_id: str,
    application: AgentApplication = Depends(get_application),
) -> list[TraceEvent]:
    if await application.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return await application.get_trace(run_id)


@router.get("/tools", response_model=list[dict[str, Any]])
async def list_tools(
    application: AgentApplication = Depends(get_application),
) -> list[dict[str, Any]]:
    return application.list_tools()

