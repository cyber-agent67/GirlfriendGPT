#!/usr/bin/env python3
"""
Websocket server runner for the Intimate Companion Agent.

This script starts the websocket server that allows users to connect directly
to their AI companion without requiring Telegram or other transports.

Usage:
    python run_websocket.py --port 8000 --host 0.0.0.0
"""

import click
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api import GirlfriendGPT, GirlFriendGPTConfig
from steamship import Steamship


@click.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, type=int, help='Port to bind to')
@click.option('--name', default='Luna', help='Companion name')
@click.option('--byline', default='Your intimate AI companion', help='Companion byline')
@click.option('--identity', default='A caring and intelligent AI companion', help='Companion identity')
@click.option('--behavior', default='Be helpful, supportive, and engaging', help='Companion behavior')
@click.option('--use-gpt4', default=True, type=bool, help='Use GPT-4 (vs GPT-3.5)')
def run_server(host, port, name, byline, identity, behavior, use_gpt4):
    """Start the websocket server for the intimate companion agent."""
    
    click.echo("🤖 Intimate Companion - Websocket Server")
    click.echo("=" * 50)
    
    # Create configuration
    config = GirlFriendGPTConfig(
        name=name,
        byline=byline,
        identity=identity,
        behavior=behavior,
        use_gpt4=use_gpt4,
        bot_token="",  # Not needed for websocket
    )
    
    click.echo(f"Companion: {name}")
    click.echo(f"Byline: {byline}")
    click.echo(f"Model: {'GPT-4' if use_gpt4 else 'GPT-3.5-turbo'}")
    click.echo("=" * 50)
    
    # Initialize Steamship client
    try:
        client = Steamship()
        click.echo("✓ Steamship client initialized")
    except Exception as e:
        click.echo(f"✗ Failed to initialize Steamship client: {e}", err=True)
        click.echo("Make sure you have STEAMSHIP_API_KEY set in your environment", err=True)
        sys.exit(1)
    
    # Create agent service
    try:
        service = GirlfriendGPT(client=client, config=config)
        click.echo("✓ Agent service initialized")
    except Exception as e:
        click.echo(f"✗ Failed to initialize agent service: {e}", err=True)
        sys.exit(1)
    
    click.echo("")
    click.echo(f"Starting websocket server on {host}:{port}...")
    click.echo(f"WebSocket endpoint: ws://localhost:{port}/ws/{{session_id}}")
    click.echo("")
    click.echo("Connect using the CLI tool:")
    click.echo(f"  companion chat")
    click.echo("")
    click.echo("Or write code:")
    click.echo(f"  companion code 'Python function for fibonacci'")
    click.echo("")
    click.echo("Press Ctrl+C to stop the server")
    click.echo("")
    
    try:
        service.start_websocket_server(host=host, port=port)
    except KeyboardInterrupt:
        click.echo("\n\n👋 Server stopped")
    except Exception as e:
        click.echo(f"\n✗ Server error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    run_server()
