"""Hexagonal Primary Adapters (CLI, MCP Server, REST API) for `gpower_chi2_forge`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gpower_chi2_forge.adapters.cli_adapter import ChiSquareCliAdapter
    from gpower_chi2_forge.adapters.mcp_server import ChiSquareMcpServer
    from gpower_chi2_forge.adapters.rest_adapter import ChiSquareRestDispatcher, serve_rest_api

__all__ = [
    "ChiSquareCliAdapter",
    "ChiSquareMcpServer",
    "ChiSquareRestDispatcher",
    "serve_rest_api",
]


def __getattr__(name: str) -> Any:
    if name == "ChiSquareCliAdapter":
        from gpower_chi2_forge.adapters.cli_adapter import ChiSquareCliAdapter
        return ChiSquareCliAdapter
    if name == "ChiSquareMcpServer":
        from gpower_chi2_forge.adapters.mcp_server import ChiSquareMcpServer
        return ChiSquareMcpServer
    if name in ("ChiSquareRestDispatcher", "serve_rest_api"):
        from gpower_chi2_forge.adapters import rest_adapter
        return getattr(rest_adapter, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
