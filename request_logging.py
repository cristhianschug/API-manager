"""Request logging middleware for tracking API usage"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional

from platform_repository import log_request
from tenant_auth import TenantContext

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests to platform.db for metrics/debugging"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # Extract tenant context if present (not all endpoints require auth)
        tenant_context: Optional[TenantContext] = None
        if hasattr(request.state, 'tenant_context'):
            tenant_context = request.state.tenant_context

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            # Log the error
            log_request(
                api_key_id=tenant_context.api_key_id if tenant_context else None,
                client_id=tenant_context.client_id if tenant_context else None,
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                error_message=str(e)[:256]
            )
            raise

        duration_ms = int((time.time() - start_time) * 1000)

        # Log successful response
        log_request(
            api_key_id=tenant_context.api_key_id if tenant_context else None,
            client_id=tenant_context.client_id if tenant_context else None,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
