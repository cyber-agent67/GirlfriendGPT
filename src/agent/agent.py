"""SmolAgent - Lightweight AI Agent for Media Influencer.

This is the core agent implementation that powers the AI influencer.
It uses OpenAI's API directly (no Steamship dependency) and supports
tool integration for media creation and social media management.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

# Keep OpenAI import inside module to avoid issues if not installed
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


@dataclass
class AgentConfig:
    """Configuration for the AI influencer agent."""
    name: str = "Luna"
    byline: str = "AI Media Influencer"
    identity: str = "A creative AI influencer and content creator"
    behavior: str = "Be engaging, creative, and social media savvy"
    use_gpt4: bool = True
    model: str = field(init=False)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    tools: Optional[List[str]] = None  # List of tool names to enable

    def __post_init__(self):
        self.model = "gpt-4" if self.use_gpt4 else "gpt-3.5-turbo"


class SmolAgent:
    """Lightweight AI agent using OpenAI API with tool support."""

    def __init__(self, config: AgentConfig):
        self.config = config
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.tools = self._load_tools()
        self.system_prompt = self._build_system_prompt()
        self.conversation_history = []

    def _load_tools(self) -> List[Any]:
        """Load enabled tools."""
        from agent.tools import (
            ImageGenerationTool,
            VideoGenerationTool,
            AudioGenerationTool,
            InstagramPostTool,
            TwitterPostTool,
            TikTokPostTool,
            YouTubePostTool,
            CaptionWriterTool,
            ScriptWriterTool,
            HashtagGeneratorTool,
            ContentCalendarTool,
        )

        # Load all tools by default (can be filtered by config later)
        return [
            ImageGenerationTool(),
            VideoGenerationTool(),
            AudioGenerationTool(),
            InstagramPostTool(),
            TwitterPostTool(),
            TikTokPostTool(),
            YouTubePostTool(),
            CaptionWriterTool(),
            ScriptWriterTool(),
            HashtagGeneratorTool(),
            ContentCalendarTool(),
        ]

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.human_description}"
            for tool in self.tools
        ])

        return (
            f"You are {self.config.name}, {self.config.byline}.\n"
            f"{self.config.identity}\n\n"
            f"Behavior: {self.config.behavior}\n\n"
            f"Available Tools:\n{tool_descriptions}\n\n"
            f"INSTRUCTIONS:\n"
            f"- For normal conversation, respond naturally and engage with the user.\n"
            f"- When the user asks to create media (images, videos, audio), use the appropriate tool.\n"
            f"- When the user asks to post to social media, use the platform-specific tool.\n"
            f"- When the user asks for content planning or captions, use the content writing tools.\n"
            f"- After using a tool, explain what you did and offer to help further.\n"
            f"- Be creative, engaging, and think like a social media influencer!\n"
        )

    def respond(self, user_message: str) -> str:
        """Generate a response from the LLM."""
        if not self.client:
            return "Error: OpenAI API key not configured"

        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            resp = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation_history[-10:],  # Keep last 10 messages for context
                ],
            )
            response = resp.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            return f"Error: {str(e)}"

    def reset(self):
        """Clear conversation history."""
        self.conversation_history = []

    def get_tools_info(self) -> List[Dict[str, str]]:
        """Get information about available tools."""
        return [
            {
                "name": tool.name,
                "description": tool.human_description,
            }
            for tool in self.tools
        ]


# Export names for other modules
Agent = SmolAgent
Config = AgentConfig
