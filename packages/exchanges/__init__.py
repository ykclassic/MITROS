"""Exchange account and execution adapters with a selectable-provider boundary."""

from .xt import XTSpotClient, XTSpotError

__all__ = ["XTSpotClient", "XTSpotError"]
