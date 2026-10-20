"""
AegisFlow AI - Four-Direction Manual Scan API
"""
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from models import Lane
from ..manual_scan import ManualScanManager, ScanError


class ScanStartRequest(BaseModel):
    source: Optional[Any] = None  # camera index or stream URL; default from config


def _lane(approach: str) -> Lane:
    try:
        return Lane(approach.lower().strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approach '{approach}'. Must be one of: north, east, south, west",
        )


def create_scan_router(scan_manager: ManualScanManager, get_default_source) -> APIRouter:
    router = APIRouter(prefix="/api/v1/scan")

    def _bad_request(exc: ScanError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @router.get("")
    def get_scan_status():
        """Scan state: camera, the four observations, validity, proposal and signal permission."""
        return scan_manager.status()

    @router.post("/start")
    async def start_scan(req: ScanStartRequest):
        source = req.source if req.source is not None else get_default_source()
        try:
            scan_id = await scan_manager.start(source)
        except ScanError as exc:
            raise _bad_request(exc)
        return {"status": "started", "scan_id": scan_id}

    @router.post("/stop")
    async def stop_scan():
        await scan_manager.stop()
        return {"status": "stopped"}

    @router.post("/new")
    def new_scan():
        if not scan_manager.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start scan mode first")
        return {"status": "ok", "scan_id": scan_manager.new_scan()}

    @router.post("/apply")
    async def apply_scan():
        try:
            return await scan_manager.apply()
        except ScanError as exc:
            raise _bad_request(exc)

    @router.post("/{approach}/capture")
    async def capture(approach: str):
        lane = _lane(approach)
        try:
            return await asyncio.to_thread(scan_manager.capture, lane)
        except ScanError as exc:
            raise _bad_request(exc)

    @router.post("/{approach}/confirm")
    def confirm(approach: str):
        try:
            return scan_manager.confirm(_lane(approach))
        except ScanError as exc:
            raise _bad_request(exc)

    @router.post("/{approach}/retake")
    def retake(approach: str):
        try:
            scan_manager.retake(_lane(approach))
        except ScanError as exc:
            raise _bad_request(exc)
        return {"status": "ok"}

    @router.get("/{approach}/image")
    def image(approach: str, annotated: bool = True):
        data = scan_manager.get_image(_lane(approach), annotated=annotated)
        if data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No capture for this approach")
        return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    return router
