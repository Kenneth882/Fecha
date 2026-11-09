from typing import cast

from fastapi import Request

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    """The Settings this app was built with, as stored by `create_app`."""
    return cast(Settings, request.app.state.settings)
