"""Gateway websocket server for AI Influencer Agent."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import Agent, Config
from config import ConfigManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages websocket connections."""

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.connections:
            self.connections[session_id] = set()
        self.connections[session_id].add(websocket)
        logger.info(f"Client connected: {session_id}")

    async def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.connections:
            self.connections[session_id].discard(websocket)
            if not self.connections[session_id]:
                del self.connections[session_id]
        logger.info(f"Client disconnected: {session_id}")

    async def send(self, session_id: str, message: dict):
        """Send message to all connections in a session."""
        if session_id in self.connections:
            for connection in self.connections[session_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message: {e}")


def create_app(agent: Agent, config: dict) -> FastAPI:
    """Create FastAPI app with websocket endpoint."""
    app = FastAPI(title="AI Influencer Gateway")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = ConnectionManager()

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "name": config.get("name", "Unknown"),
            "active_sessions": len(manager.connections)
        }

    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        await manager.connect(session_id, websocket)

        try:
            # Send greeting
            await manager.send(session_id, {
                "role": "assistant",
                "content": f"Hello! I'm {config.get('name')}. How can I help you create content today?"
            })

            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                    message = json.loads(data)

                    logger.info(f"Message from {session_id}: {message.get('content', '')[:100]}")

                    # Get response from agent
                    response_text = agent.respond(message.get("content", ""))

                    # Send response
                    await manager.send(session_id, {
                        "role": "assistant",
                        "content": response_text,
                        "type": "text"
                    })

                except asyncio.TimeoutError:
                    # Keepalive ping
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except:
                        break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    await manager.send(session_id, {"role": "system", "content": "Invalid message format"})

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")
            await manager.disconnect(session_id, websocket)
        except Exception as e:
            logger.error(f"Websocket error: {e}")
            await manager.disconnect(session_id, websocket)

    return app


def run_gateway(port: int = 18789, host: str = "127.0.0.1"):
    """Run the gateway server."""
    config = ConfigManager.load_config()
    ConfigManager.save_config(config)

    # Get OpenAI config
    openai_config = config.get("model_provider", {}).get("openai", {})
    api_key = openai_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    model = openai_config.get("model", "gpt-4")

    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")

    print(f"🚀 Starting AI Influencer Gateway")
    print(f"   Agent: {config.get('name')}")
    print(f"   Server: {host}:{port}")
    print(f"   Model: {model}")
    print()

    # Create agent
    agent_config = Config(
        name=config.get("name", "Luna"),
        byline=config.get("byline", "AI Media Influencer"),
        identity=config.get("identity", "A creative AI influencer"),
        behavior=config.get("behavior", "Be engaging and creative"),
        use_gpt4=(model == "gpt-4"),
    )

    agent = Agent(agent_config)
    print(f"✅ Agent initialized")

    # Create and run app
    app = create_app(agent, config)

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Gateway shutting down...")
