"""The single boundary between the app and YouTube.

RealGateway talks to the YouTube Data API; FakeGateway is in-memory and used by tests and --fake mode.
"""
from typing import Protocol


class YouTubeGateway(Protocol):
    """Methods are added as features need them (connect, sync, then writes)."""
