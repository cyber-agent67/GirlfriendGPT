#!/usr/bin/env python3
"""CLI tool for intimate companion agent - Cursor for Engineering.

This CLI allows engineers to interact with their intimate AI companion
for code generation, refactoring, and technical guidance.
"""

import click
import json
import asyncio
import websockets
from pathlib import Path
from typing import Optional
import sys


class CompanionCLI:
    """CLI client for the companion websocket server."""
    
    def __init__(self, server_url: str = "ws://localhost:8000"):
        self.server_url = server_url
        self.session_id = self._load_or_create_session()
    
    def _load_or_create_session(self) -> str:
        """Load existing session or create new one."""
        session_file = Path.home() / ".companion" / "session.json"
        
        if session_file.exists():
            with open(session_file, 'r') as f:
                data = json.load(f)
                return data.get("session_id", self._new_session_id())
        else:
            session_id = self._new_session_id()
            session_file.parent.mkdir(parents=True, exist_ok=True)
            with open(session_file, 'w') as f:
                json.dump({"session_id": session_id}, f)
            return session_id
    
    @staticmethod
    def _new_session_id() -> str:
        """Generate new session ID."""
        import uuid
        return str(uuid.uuid4())
    
    async def send_message(self, message: str, message_type: str = "text") -> str:
        """Send message to companion and get response.
        
        Args:
            message: The message to send
            message_type: Type of message (text, code_request, etc.)
        
        Returns:
            Response from the companion
        """
        uri = f"{self.server_url}/ws/{self.session_id}"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Receive initial greeting
                greeting = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Companion: {json.loads(greeting)['content']}\n")
                
                # Send user message
                msg_data = {
                    "role": "user",
                    "content": message,
                    "type": message_type,
                    "metadata": None
                }
                await websocket.send(json.dumps(msg_data))
                
                # Receive and print response
                response = ""
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        msg = json.loads(data)
                        if msg["role"] == "assistant":
                            print(f"Companion: {msg['content']}\n")
                            response += msg['content']
                    except asyncio.TimeoutError:
                        break
                    except Exception:
                        break
                
                return response
        
        except Exception as e:
            click.echo(f"Error: Could not connect to companion at {self.server_url}", err=True)
            click.echo(f"Details: {str(e)}", err=True)
            sys.exit(1)


@click.group()
@click.option('--server', default='ws://localhost:18789', help='Websocket server URL')
@click.pass_context
def cli(ctx, server):
    """Intimate Companion CLI - Your AI engineering assistant."""
    ctx.ensure_object(dict)
    ctx.obj['cli'] = CompanionCLI(server)


@cli.command()
@click.argument('request')
@click.pass_context
def code(ctx, request):
    """Generate code based on a request.
    
    Example:
        companion code "Python function to calculate fibonacci"
    """
    cli_obj = ctx.obj['cli']
    
    prompt = f"Write code for: {request}"
    click.echo(f"\nYou: {prompt}\n")
    
    asyncio.run(cli_obj.send_message(prompt, message_type="code_request"))


@cli.command()
@click.argument('filepath', type=click.Path(exists=True))
@click.argument('request')
@click.pass_context
def refactor(ctx, filepath, request):
    """Refactor existing code.
    
    Example:
        companion refactor myfile.py "optimize for performance"
    """
    cli_obj = ctx.obj['cli']
    
    # Read the code file
    with open(filepath, 'r') as f:
        code_content = f.read()
    
    prompt = f"Please refactor this code with request: {request}\n\n```\n{code_content}\n```"
    click.echo(f"\nYou: Refactor {filepath} - {request}\n")
    
    asyncio.run(cli_obj.send_message(prompt, message_type="code_refactor"))


@cli.command()
@click.pass_context
def chat(ctx):
    """Start an interactive chat session with your companion.
    
    Type 'exit' or 'quit' to end the session.
    """
    cli_obj = ctx.obj['cli']
    
    click.echo("\n🤖 Intimate Companion - Interactive Chat")
    click.echo("Type 'exit' or 'quit' to end the session\n")
    
    while True:
        try:
            user_input = click.prompt("You")
            
            if user_input.lower() in ['exit', 'quit']:
                click.echo("Goodbye!")
                break
            
            asyncio.run(cli_obj.send_message(user_input))
        
        except KeyboardInterrupt:
            click.echo("\nGoodbye!")
            break
        except Exception as e:
            click.echo(f"Error: {str(e)}", err=True)


@cli.command()
@click.option('--message', default='how can you help me?', help='Message to send')
@click.pass_context
def ask(ctx, message):
    """Ask the companion a question.
    
    Example:
        companion ask --message "what's the best way to structure a Python project?"
    """
    cli_obj = ctx.obj['cli']
    
    click.echo(f"\nYou: {message}\n")
    asyncio.run(cli_obj.send_message(message))


@cli.command()
@click.option('--server', default='ws://localhost:18789', help='Server URL to check')
def health(server):
    """Check if the companion server is running.
    
    Example:
        companion health --server ws://localhost:8000
    """
    import httpx
    
    http_server = server.replace('ws://', 'http://').replace('wss://', 'https://')
    
    try:
        response = httpx.get(f"{http_server}/health", timeout=5.0)
        if response.status_code == 200:
            click.echo(f"✓ Companion server is running at {server}")
            click.echo(f"  Status: {response.json()}")
        else:
            click.echo(f"✗ Server returned status {response.status_code}", err=True)
    except Exception as e:
        click.echo(f"✗ Could not reach server at {server}", err=True)
        click.echo(f"  Error: {str(e)}", err=True)


@cli.command()
def version():
    """Show version information."""
    click.echo("Intimate Companion CLI v1.0.0")
    click.echo("Your personal AI engineering assistant")


if __name__ == '__main__':
    cli(obj={})
