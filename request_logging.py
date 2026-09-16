"""Request logging middleware for tracking API usage"""
import asyncio
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional

from platform_repository import log_request
from tenant_auth import TenantContext

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        def _get_tenant():
            ctx = getattr(request.state, 'tenant_context', None)
            return (ctx.api_key_id if ctx else None, ctx.client_id if ctx else None)

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            api_key_id, client_id = _get_tenant()
            asyncio.create_task(asyncio.to_thread(
                log_request,
                api_key_id=api_key_id, client_id=client_id,
                method=request.method, path=request.url.path,
                status_code=500, duration_ms=duration_ms,
                error_message=str(e)[:256]
            ))
            raise

        duration_ms = int((time.time() - start_time) * 1000)
        api_key_id, client_id = _get_tenant()
        asyncio.create_task(asyncio.to_thread(
            log_request,
            api_key_id=api_key_id, client_id=client_id,
            method=request.method, path=request.url.path,
            status_code=response.status_code, duration_ms=duration_ms,
        ))

        return response
