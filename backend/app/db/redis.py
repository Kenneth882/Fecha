from redis.asyncio import Redis

from app.core.config import Settings


def create_redis(settings: Settings) -> Redis:
    """The app's Redis client, backed by a connection pool that connects lazily."""
    return Redis.from_url(settings.redis_url.get_secret_value(), socket_connect_timeout=2)
