"""FastAPI + FastMCP combined application."""
from fastapi import FastAPI, Request
from fastmcp import FastMCP

from .tools import load_tools
from .utils import header_store

mcp_server = FastMCP(name="shared-mcp-server")
load_tools(mcp_server)

mcp_app = mcp_server.http_app()

app = FastAPI(title="Shared MCP Server", version="0.1.0", lifespan=mcp_app.lifespan)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


combined_app = FastAPI(
    title="Combined MCP App",
    routes=[*mcp_app.routes, *app.routes],
    lifespan=mcp_app.lifespan,
)


@combined_app.middleware("http")
async def capture_headers(request: Request, call_next):
    header_store.set(dict(request.headers))
    return await call_next(request)
