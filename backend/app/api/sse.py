from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL = 15  # seconds


async def _event_generator(
    request: Request,
    job_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Subscribe to the Redis pub/sub channel for a job and yield SSE events.

    Events have ``data`` containing a JSON string.  The generator ends when:
    - A ``complete`` or ``error`` event is received from the worker.
    - The client disconnects (``await request.is_disconnected()``).
    - The job key no longer exists in Redis (already finished or expired).
    """
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"job:{job_id}:progress"

    try:
        await pubsub.subscribe(channel)

        # If the job is already done/failed, send the current state immediately
        # so clients that connect after completion still get a terminal event.
        raw = await r.get(f"job:{job_id}")
        if raw is None:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Job '{job_id}' not found."}),
            }
            return

        state = json.loads(raw)
        if state.get("status") in ("done", "failed"):
            terminal_event = "complete" if state["status"] == "done" else "error"
            yield {"event": terminal_event, "data": json.dumps(state)}
            return

        # Send the current progress snapshot so the client can restore state.
        yield {"event": "progress", "data": json.dumps(state)}

        while True:
            # Check for client disconnection.
            if await request.is_disconnected():
                logger.debug("SSE client disconnected for job %s", job_id)
                break

            # Wait for the next message with a timeout for keepalive pings.
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1),
                    timeout=_KEEPALIVE_INTERVAL,
                )
            except asyncio.TimeoutError:
                # Send keepalive comment (SSE comment lines start with ":").
                yield {"comment": "keepalive"}
                continue

            if message is None:
                # No message yet — yield control and try again.
                await asyncio.sleep(0.05)
                continue

            if message["type"] != "message":
                continue

            payload_str: str = message["data"]
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.warning("Non-JSON SSE payload for job %s: %s", job_id, payload_str)
                continue

            event_type = payload.get("event", "progress")
            yield {"event": event_type, "data": payload_str}

            if event_type in ("complete", "error"):
                break

    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await r.aclose()
        except Exception:
            pass


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request) -> EventSourceResponse:
    """
    SSE endpoint that streams real-time progress events for a job.

    Clients receive JSON-encoded event data on every progress update.
    The stream closes after a ``complete`` or ``error`` terminal event.
    """
    # Quick existence check so we can return 404 before opening a stream.
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        exists = await r.exists(f"job:{job_id}")
    finally:
        await r.aclose()

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return EventSourceResponse(
        _event_generator(request, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx: disable proxy buffering
        },
    )
