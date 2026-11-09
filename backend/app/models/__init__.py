"""SQLAlchemy tables. Import every model module here so `Base.metadata` sees it."""

from app.models.base import Base

__all__ = ["Base"]
