"""
Lightweight HTTP/JSON REST Adapter for `gpower_chi2_forge`.

Acts strictly as a thin Hexagonal Primary Adapter translating HTTP JSON payloads
into calls on `ChiSquarePowerEngine` and `ContingencyEffectCalculator`.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Any, Optional

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.exceptions import ChiSquareDomainException
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class ChiSquareRestDispatcher:
    """Framework-agnostic REST request processor delegating to core domain services."""

    def __init__(self, engine: Optional[ChiSquarePowerEngine] = None) -> None:
        self._engine = engine or ChiSquarePowerEngine()

    def handle_post_power(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            envelope = self._engine.dispatch(
                mode=payload.get("mode", "a-priori"),
                alpha=payload.get("alpha"),
                power=payload.get("power"),
                w=payload.get("w"),
                df=payload.get("df"),
                n=payload.get("n"),
                q_ratio=payload.get("q_ratio"),
            )
            return 200, envelope.to_contract_dict()
        except ChiSquareDomainException as exc:
            status_code = 422 if exc.exit_code == 2 else 500
            return status_code, {
                "status": "error",
                "error_code": exc.error_code,
                "message": str(exc),
                "exit_code": exc.exit_code,
            }
        except ValueError as exc:
            return 400, {
                "status": "error",
                "error_code": "INVALID_REQUEST_PARAMETERS",
                "message": str(exc),
                "exit_code": 2,
            }

    def handle_post_effect_size(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            res = ContingencyEffectCalculator.compute_from_contingency_table(
                observed_cells=payload.get("observed_table", []),
                null_cells=payload.get("null_table"),
            )
            return 200, res.to_contract_dict()
        except ChiSquareDomainException as exc:
            return 422, {
                "status": "error",
                "error_code": exc.error_code,
                "message": str(exc),
                "exit_code": exc.exit_code,
            }


def create_http_handler(dispatcher: ChiSquareRestDispatcher) -> type[BaseHTTPRequestHandler]:
    """Create a standard library BaseHTTPRequestHandler bound to the REST dispatcher."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok", "service": "gpower_chi2_forge"})
            else:
                self._send_json(404, {"status": "error", "message": "Not Found"})

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                self._send_json(400, {"status": "error", "message": f"Invalid JSON: {exc}"})
                return

            if self.path == "/v1/chi2/power":
                code, resp = dispatcher.handle_post_power(body)
                self._send_json(code, resp)
            elif self.path == "/v1/chi2/effect-size":
                code, resp = dispatcher.handle_post_effect_size(body)
                self._send_json(code, resp)
            else:
                self._send_json(404, {"status": "error", "message": "Endpoint not found"})

        def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    return _Handler


def serve_rest_api(host: str = "127.0.0.1", port: int = 8089) -> HTTPServer:
    dispatcher = ChiSquareRestDispatcher()
    handler_cls = create_http_handler(dispatcher)
    return HTTPServer((host, port), handler_cls)
