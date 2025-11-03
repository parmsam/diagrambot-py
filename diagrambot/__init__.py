"""
diagrambot - Use OpenAI Realtime API to create diagrams.
"""

__version__ = "0.1.0"

from .chat import diagrambot_chat
from .voice import diagrambot_voice, diagrambot

__all__ = [
    "diagrambot",
    "diagrambot_chat", 
    "diagrambot_voice",
]