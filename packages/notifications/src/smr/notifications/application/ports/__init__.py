"""Where notices and preferences are kept, and who delivers them."""

from __future__ import annotations

from ._ports import (
    DeliveryError,
    DeliveryGaveUpError,
    DeliveryRetryError,
    Outbox,
    Preferences,
    Sender,
)

__all__ = (
    "DeliveryError",
    "DeliveryGaveUpError",
    "DeliveryRetryError",
    "Outbox",
    "Preferences",
    "Sender",
)
