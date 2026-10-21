"""In-memory YouTube used by tests and `python dev.py --fake`. Never talks to Google."""


class FakeGateway:
    """Grows alongside YouTubeGateway; empty until the first gateway method exists."""
