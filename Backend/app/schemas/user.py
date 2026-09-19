"""The user profile. One kind of user -- no roles, no permissions field."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    sign_in_count: int = 0


class UserUpdate(BaseModel):
    display_name: str
