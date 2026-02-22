from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
import os

from carbon_metrics import get_pool, websocket_metrics_stream

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    # Optional client filters via query params:
    # ws://localhost:5000/ws/metrics?project_name=foo&run_id=bar
    project_name = websocket.query_params.get("project_name")
    run_id = websocket.query_params.get("run_id")
    await websocket_metrics_stream(
        websocket=websocket,
        pool=db_pool,
        project_name=project_name,
        run_id=run_id,
        poll_seconds=float(os.getenv("WS_POLL_SECONDS", "2.0")),
    )

if __name__ == "__main__":
    PORT = int(os.getenv("BACKEND_PORT", 5000))
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)