"""Rotas de controle do processo do monitor (iniciar, parar, status)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from web.db_models import UserModel
from web.dependencies import get_current_user, get_monitor_manager
from web.monitor_process import (
    MonitorAlreadyRunningError,
    MonitorNotRunningError,
    MonitorProcessManager,
)
from web.schemas import MonitorStatusResponse

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/status", response_model=MonitorStatusResponse)
def read_monitor_status(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    """Informa se o monitor está em execução e o PID do processo."""
    return MonitorStatusResponse(running=monitor.is_running(), pid=monitor.pid())


@router.post("/start", response_model=MonitorStatusResponse)
def start_monitor(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    """Inicia o processo do monitor (``run.py``)."""
    try:
        pid = monitor.start()
    except MonitorAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MonitorStatusResponse(running=True, pid=pid)


@router.post("/stop", response_model=MonitorStatusResponse)
def stop_monitor(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    """Encerra o processo do monitor em execução."""
    try:
        monitor.stop()
    except MonitorNotRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MonitorStatusResponse(running=False, pid=None)
