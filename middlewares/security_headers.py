import os
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'"
)


def _is_https_or_prod(scope: Scope, req_headers: Headers) -> bool:
    explicit = os.getenv("COOKIE_SECURE", "").strip().lower()
    if explicit in {"1", "true", "yes"}:
        return True
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).strip().lower()
    if env in {"prod", "production"}:
        return True
    proto = req_headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return scope.get("scheme") == "https" or proto == "https"


class SecurityHeadersMiddleware:
    """Middleware ASGI ligero equivalente a Helmet sin dependencias externas."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_headers = Headers(scope=scope)
        path = scope.get("path", "")
        enable_hsts = _is_https_or_prod(scope, req_headers)

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "SAMEORIGIN"
                headers["X-XSS-Protection"] = "0"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["X-DNS-Prefetch-Control"] = "off"
                headers["X-Download-Options"] = "noopen"
                headers["X-Permitted-Cross-Domain-Policies"] = "none"
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                headers["Origin-Agent-Cluster"] = "?1"
                headers["Content-Security-Policy"] = _CSP_POLICY
                if "x-powered-by" in headers:
                    del headers["x-powered-by"]
                if enable_hsts:
                    headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
                if path.startswith("/api/auth"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
