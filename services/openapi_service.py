import json
from pathlib import Path
import re
from typing import Any
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_SAFE_PLAIN_STR = re.compile(r"^[A-Za-z0-9_./{}-]+$")
_RESERVED_SCALARS = {"true", "false", "null", "yes", "no", "on", "off", "~"}


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if (
        not text
        or text.lower() in _RESERVED_SCALARS
        or not _SAFE_PLAIN_STR.match(text)
        or text[0] in "-{["
    ):
        return json.dumps(text, ensure_ascii=False)
    try:
        float(text)
        return json.dumps(text, ensure_ascii=False)
    except ValueError:
        return text


def _dump_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]
        lines: list[str] = []
        for k, v in value.items():
            key_str = _format_scalar(str(k))
            if isinstance(v, dict) and v:
                lines.append(f"{prefix}{key_str}:")
                lines.extend(_dump_yaml(v, indent + 1))
            elif isinstance(v, list) and v:
                lines.append(f"{prefix}{key_str}:")
                lines.extend(_dump_yaml(v, indent + 1))
            else:
                lines.append(f"{prefix}{key_str}: {_format_scalar(v)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, dict) and item:
                first = True
                for k, v in item.items():
                    key_str = _format_scalar(str(k))
                    item_prefix = f"{prefix}- " if first else f"{prefix}  "
                    first = False
                    if isinstance(v, (dict, list)) and v:
                        lines.append(f"{item_prefix}{key_str}:")
                        lines.extend(_dump_yaml(v, indent + 2))
                    else:
                        lines.append(f"{item_prefix}{key_str}: {_format_scalar(v)}")
            elif isinstance(item, list) and item:
                lines.append(f"{prefix}-")
                lines.extend(_dump_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_format_scalar(item)}")
        return lines

    return [f"{prefix}{_format_scalar(value)}"]


def to_yaml(data: Any) -> str:
    return "\n".join(_dump_yaml(data)) + "\n"


def build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description=(
            "API REST de Sistema-PARQUEADERO con autenticación por cookie httpOnly, "
            "permisos por rol (admin/cajero), paginación indexada, auditoría y exportación en streaming."
        ),
        routes=app.routes,
    )

    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["cookieAuth"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": "session_id",
        "description": "Sesión emitida por POST /api/auth/login (HttpOnly, SameSite=Strict, sin JWT).",
    }

    schemas_comp = components.setdefault("schemas", {})
    schemas_comp["ErrorDetail"] = {
        "type": "object",
        "required": ["codigo", "mensaje"],
        "properties": {
            "codigo": {"type": "string", "example": "NO_AUTENTICADO"},
            "mensaje": {"type": "string", "example": "No autenticado o sesión expirada"},
        },
    }
    schemas_comp["ErrorResponse"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {"$ref": "#/components/schemas/ErrorDetail"},
        },
    }

    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    public_paths = {"/api/auth/login", "/api/auth/logout", "/api/docs", "/api/openapi.yaml"}

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in list(path_item.items()):
            if not isinstance(operation, dict):
                continue
            if path not in public_paths:
                operation.setdefault("security", [{"cookieAuth": []}])
            responses = operation.setdefault("responses", {})
            for code, desc in (
                ("400", "Solicitud o parámetros inválidos"),
                ("401", "No autenticado o sesión expirada"),
                ("403", "Sin permisos suficientes para este rol"),
                ("404", "Recurso no encontrado"),
                ("422", "Error de validación de esquema"),
            ):
                if code == "422" and "422" in responses:
                    responses["422"] = {
                        "description": desc,
                        "content": {"application/json": {"schema": error_ref}},
                    }
                elif code not in responses:
                    responses[code] = {
                        "description": desc,
                        "content": {"application/json": {"schema": error_ref}},
                    }
            if path == "/api/auth/login":
                responses.setdefault(
                    "429",
                    {
                        "description": "Demasiados intentos de inicio de sesión",
                        "content": {"application/json": {"schema": error_ref}},
                    },
                )

    app.openapi_schema = schema
    return app.openapi_schema


def write_openapi_yaml(app: FastAPI, output_path: Path) -> Path:
    schema = build_openapi_schema(app)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_yaml(schema), encoding="utf-8")
    return output_path
