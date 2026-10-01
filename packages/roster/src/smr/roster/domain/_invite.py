"""Invite codes: the payload of a group's join link."""

from __future__ import annotations

import secrets

# 16 random bytes give 22 URL-safe characters: unguessable, and well inside the
# 64-character `[A-Za-z0-9_-]` limit of a Telegram deep link.
_INVITE_BYTES = 16


def new_invite_code() -> str:
    """Make a fresh invite code.

    Returns:
        str - 22 characters of `[A-Za-z0-9_-]`.

    """
    return secrets.token_urlsafe(_INVITE_BYTES)
