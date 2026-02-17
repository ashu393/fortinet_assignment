"""MCP JSON-RPC 2.0 server skeleton (placeholder)."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MCP Tool Server (PoC)")

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict = {}

@app.post("/rpc")
def rpc(req: JsonRpcRequest):
    # TODO: dispatch to tools, return JSON-RPC compliant responses
    raise HTTPException(status_code=501, detail="Not implemented: JSON-RPC dispatch + tools")
