"""SQLAlchemy tables. Import every model module here so `Base.metadata` sees it."""

from app.models.base import Base
from app.models.user import Role, User

__all__ = ["Base", "Role", "User"]
