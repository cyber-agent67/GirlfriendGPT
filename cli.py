#!/usr/bin/env python3
"""CLI for AI Influencer Agent with gateway management."""

import asyncio
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import click
import websockets
from httpx import get

from src.config import ConfigManager

STATE_DIR = Path.home() / ".gfgpt"
STATE_FILE = STATE_DIR / "state.json"


def ensure_state_dir():
    """Ensure state directory exists."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load application state."""
    ensure_state_dir()
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """Save application state."""
    ensure_state_dir()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def is_process_running(pid: int) -> bool:
    """Check if a process is running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


@click.group()
def cli():
    """AI Influencer Agent - Your personal media creator and social media manager."""
    pass


@cli.group()
def gateway():
    """Manage the gateway server."""
    pass


@gateway.command()
@click.option('--port', type=int, help='Gateway port')
@click.option('--host', help='Gateway host')
@click.option('--daemon', is_flag=True, help='Run in background')
def start(port: Optional[int], host: Optional[str], daemon: bool):
    """Start the gateway server."""
    config = ConfigManager.load_config()
    
    port = port or config.get("gateway_port", 18789)
    host = host or config.get("gateway_host", "127.0.0.1")
    
    # Check if already running
    state = load_state()
    if state.get("gateway_pid"):
        if is_process_running(state["gateway_pid"]):
            click.echo(f"Gateway already running on {host}:{port} (PID: {state['gateway_pid']})")
            return
        else:
            click.echo("Cleaning up stale state file...")
            state.pop("gateway_pid", None)
            save_state(state)
    
    click.echo("🚀 Starting AI Influencer Gateway")
    click.echo(f"   Agent: {config.get('name')}")
    click.echo(f"   Server: {host}:{port}")
    click.echo(f"   Model: {config.get('model_provider', {}).get('openai', {}).get('model', 'gpt-4')}")
    click.echo()
    
    if daemon:
        # Run in background
        import subprocess
        log_file = STATE_DIR / "gateway.log"
        
        cmd = [sys.executable, "-m", "src.gateway.server", "--port", str(port), "--host", host]
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=f, start_new_session=True)
        
        time.sleep(1)  # Give it time to start
        
        if is_process_running(process.pid):
            click.echo(f"✅ Gateway started in background (PID: {process.pid})")
            click.echo(f"   Logs: {log_file}")
            save_state({"gateway_pid": process.pid, "port": port, "host": host})
        else:
            click.echo("❌ Failed to start gateway", err=True)
            click.echo(f"   Check logs: {log_file}", err=True)
    else:
        # Run in foreground
        from src.gateway.server import run_gateway
        try:
            run_gateway(port=port, host=host)
        except KeyboardInterrupt:
            click.echo("\n👋 Gateway stopped")


@gateway.command()
def stop():
    """Stop the gateway server."""
    state = load_state()
    pid = state.get("gateway_pid")
    
    if not pid:
        click.echo("Gateway is not running")
        return
    
    if not is_process_running(pid):
        click.echo("Gateway process not found (stale state file)")
        state.pop("gateway_pid", None)
        save_state(state)
        return
    
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"✅ Gateway stopped (PID: {pid})")
        state.pop("gateway_pid", None)
        save_state(state)
    except Exception as e:
        click.echo(f"❌ Failed to stop gateway: {e}", err=True)


@gateway.command()
def restart():
    """Restart the gateway server."""
    click.echo("Restarting gateway...")
    cli.invoke(stop.get_command(click.Context(cli)))
    time.sleep(1)
    cli.invoke(start.get_command(click.Context(cli)))


@gateway.command()
def status():
    """Check gateway status."""
    state = load_state()
    config = ConfigManager.load_config()
    
    pid = state.get("gateway_pid")
    port = state.get("port", config.get("gateway_port", 18789))
    host = state.get("host", config.get("gateway_host", "127.0.0.1"))
    
    if pid and is_process_running(pid):
        click.echo(f"✅ Gateway is running")
        click.echo(f"   PID: {pid}")
        click.echo(f"   Host: {host}")
        click.echo(f"   Port: {port}")
        
        # Try to get health
        try:
            response = get(f"http://{host}:{port}/health", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                click.echo(f"   Status: {data.get('status')}")
                click.echo(f"   Agent: {data.get('name')}")
                click.echo(f"   Sessions: {data.get('active_sessions')}")
        except:
            pass
    else:
        click.echo("❌ Gateway is not running")
        if pid:
            click.echo("   (stale state file detected)")


@cli.command()
@click.argument('message', required=False)
def chat(message: Optional[str]):
    """Chat with the AI influencer agent."""
    config = ConfigManager.load_config()
    host = config.get("gateway_host", "127.0.0.1")
    port = config.get("gateway_port", 18789)
    session_id = str(uuid.uuid4())
    
    async def send_message(msg: str):
        uri = f"ws://{host}:{port}/ws/{session_id}"
        try:
            async with websockets.connect(uri) as websocket:
                greeting = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                greeting_data = json.loads(greeting)
                click.echo(f"\n{greeting_data['role']}: {greeting_data['content']}\n")
                
                user_msg = {
                    "role": "user",
                    "content": msg,
                    "type": "text",
                    "metadata": None
                }
                await websocket.send(json.dumps(user_msg))
                
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                        response_data = json.loads(response)
                        if response_data.get("type") != "ping":
                            click.echo(f"{response_data['role']}: {response_data['content']}\n")
                    except asyncio.TimeoutError:
                        break
        except Exception as e:
            click.echo(f"Error: Could not connect to gateway", err=True)
            click.echo(f"Details: {str(e)}", err=True)
            click.echo(f"Start the gateway: gfgpt gateway start", err=True)
            sys.exit(1)
    
    async def interactive_chat():
        uri = f"ws://{host}:{port}/ws/{session_id}"
        try:
            async with websockets.connect(uri) as websocket:
                greeting = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                greeting_data = json.loads(greeting)
                click.echo(f"\n{greeting_data['role']}: {greeting_data['content']}\n")
                
                while True:
                    try:
                        user_input = input("You: ").strip()
                        if not user_input:
                            continue
                        if user_input.lower() in ['exit', 'quit', 'bye']:
                            click.echo("Goodbye!")
                            break
                        
                        msg = {
                            "role": "user",
                            "content": user_input,
                            "type": "text",
                            "metadata": None
                        }
                        await websocket.send(json.dumps(msg))
                        
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                            response_data = json.loads(response)
                            if response_data.get("type") != "ping":
                                click.echo(f"{response_data['role']}: {response_data['content']}\n")
                        except asyncio.TimeoutError:
                            click.echo("Response timeout\n")
                    except KeyboardInterrupt:
                        click.echo("\nGoodbye!")
                        break
        except Exception as e:
            click.echo(f"Error: Could not connect to gateway", err=True)
            click.echo(f"Details: {str(e)}", err=True)
            sys.exit(1)
    
    if message:
        asyncio.run(send_message(message))
    else:
        click.echo("\n💁 AI Influencer Agent")
        click.echo("Type 'exit' or 'quit' to end\n")
        asyncio.run(interactive_chat())


@cli.command()
def health():
    """Check gateway health."""
    config = ConfigManager.load_config()
    host = config.get("gateway_host", "127.0.0.1")
    port = config.get("gateway_port", 18789)
    
    try:
        response = get(f"http://{host}:{port}/health", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("✅ Gateway is running")
            click.echo(f"   Agent: {data.get('name')}")
            click.echo(f"   Status: {data.get('status')}")
            click.echo(f"   Active sessions: {data.get('active_sessions')}")
        else:
            click.echo(f"❌ Gateway error: {response.status_code}", err=True)
    except Exception as e:
        click.echo(f"❌ Gateway is not running", err=True)
        click.echo(f"Start it: gfgpt gateway start", err=True)


@cli.command()
def setup():
    """Run initial setup."""
    click.echo("\n🤖 AI Influencer Agent Setup\n")
    
    config = ConfigManager.load_config()
    
    name = click.prompt("Agent name", default=config.get("name", "Luna"))
    
    identity = click.prompt(
        "Personality identity",
        default=config.get("identity", "A creative AI influencer")
    )
    
    behavior = click.prompt(
        "Behavior description",
        default=config.get("behavior", "Be engaging, creative, and social media savvy")
    )
    
    api_key = click.prompt(
        "OpenAI API Key",
        default=config.get("model_provider", {}).get("openai", {}).get("api_key", ""),
        hide_input=True
    )
    
    config.update({
        "name": name,
        "identity": identity,
        "behavior": behavior,
        "model_provider": {
            "openai": {
                "api_key": api_key,
                "model": "gpt-4"
            }
        }
    })
    
    ConfigManager.save_config(config)
    
    click.echo("\n✅ Configuration saved")
    click.echo("\nNext steps:")
    click.echo("  gfgpt gateway start    # Start the gateway")
    click.echo("  gfgpt chat             # Start chatting")


if __name__ == '__main__':
    cli()
