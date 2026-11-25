"""High level AWS Secrets Manager caching client."""
from copy import deepcopy

from importlib.metadata import version, PackageNotFoundError
import aiobotocore.config
import aiobotocore.session

from .cache import LRUCache, SecretCacheItem
from .config import SecretCacheConfig


class SecretCache:
    """Secret Cache client for AWS Secrets Manager secrets"""

    try:
        __version__ = version('aws_secretsmanager_caching')
    except PackageNotFoundError:
        __version__ = '0.0.0'

    def __init__(self, config, client):
        """Construct a secret cache. Not intended for direct use.
        Use ``await SecretCache.create()`` instead.

        :type config: aws_secretsmanager_caching.SecretCacheConfig
        :param config: Secret cache configuration (deep-copied)

        :type client: aiobotocore.client.BaseClient
        :param client: aiobotocore 'secretsmanager' client
        """
        self._client = client
        self._config = deepcopy(config)
        self._cache = LRUCache(max_size=self._config.max_cache_size)

    @classmethod
    async def create(cls, config=None, client=None):
        """Async factory. Creates the cache with an aiobotocore client.

        :type config: aws_secretsmanager_caching.SecretCacheConfig or None
        :param config: Secret cache configuration (uses defaults if omitted)

        :type client: aiobotocore.client.BaseClient or None
        :param client: Pre-configured aiobotocore 'secretsmanager' client.
            If omitted, one is created automatically.

        :rtype: aws_secretsmanager_caching.SecretCache
        :return: A fully initialized SecretCache instance.
        """
        if client is None:
            session = aiobotocore.session.AioSession()
            boto_config = aiobotocore.config.AioConfig(**{
                "user_agent_extra": f"AwsSecretCache/{cls.__version__}",
            })
            client = await session.create_client("secretsmanager", config=boto_config).__aenter__()
        return cls(config or SecretCacheConfig(), client)

    async def close(self):
        """Close the underlying aiobotocore client and release resources."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)

    async def _get_cached_secret(self, secret_id):
        """Get a cached secret for the given secret identifier.

        :type secret_id: str
        :param secret_id: The secret identifier

        :rtype: aws_secretsmanager_caching.cache.SecretCacheItem
        :return: The associated cached secret item
        """
        secret = await self._cache.get(secret_id)
        if secret is not None:
            return secret
        await self._cache.put_if_absent(
            secret_id, SecretCacheItem(config=self._config, client=self._client, secret_id=secret_id)
        )
        return await self._cache.get(secret_id)

    async def get_secret_string(self, secret_id, version_stage=None):
        """Get the secret string value from the cache.

        :type secret_id: str
        :param secret_id: The secret identifier

        :type version_stage: str
        :param version_stage: The stage for the requested version.

        :rtype: str
        :return: The associated secret string value
        """
        item = await self._get_cached_secret(secret_id)
        secret = await item.get_secret_value(version_stage)
        if secret is None:
            return secret
        return secret.get("SecretString")

    async def get_secret_binary(self, secret_id, version_stage=None):
        """Get the secret binary value from the cache.

        :type secret_id: str
        :param secret_id: The secret identifier

        :type version_stage: str
        :param version_stage: The stage for the requested version.

        :rtype: bytes
        :return: The associated secret binary value
        """
        item = await self._get_cached_secret(secret_id)
        secret = await item.get_secret_value(version_stage)
        if secret is None:
            return secret
        return secret.get("SecretBinary")

    async def refresh_secret_now(self, secret_id):
        """Immediately refresh the secret in the cache.

        :type secret_id: str
        :param secret_id: The secret identifier

        :rtype: bool
        :return: True if the secret metadata was refreshed.
        """
        item = await self._get_cached_secret(secret_id)
        return await item.refresh_secret_now()