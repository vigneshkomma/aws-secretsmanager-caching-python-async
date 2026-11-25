import asyncio
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from random import randint

from .lru import LRUCache


class SecretCacheObject:
    """Secret cache object that handles the common refresh logic."""
    # Jitter max for refresh now
    FORCE_REFRESH_JITTER_SLEEP = 5000
    # Ceiling on the retry backoff a forced refresh will wait out
    FORCE_REFRESH_MAX_SLEEP = 10000
    __metaclass__ = ABCMeta

    def __init__(self, config, client, secret_id):
        """Construct the secret cache object.

        :type config: aws_secretsmanager_caching.SecretCacheConfig
        :param config: Configuration for the cache.

        :type client: botocore.client.BaseClient
        :param client: The 'secretsmanager' boto client.

        :type secret_id: str
        :param secret_id: The secret identifier to cache.
        """
        self._lock = asyncio.Lock()
        self._config = config
        self._client = client
        self._secret_id = secret_id
        self._result = None
        self._exception = None
        self._exception_count = 0
        self._refresh_needed = True
        self._next_retry_time = None

    def _is_refresh_needed(self):
        """Determine if the cached object should be refreshed.

        :rtype: bool
        :return: True if the object should be refreshed.
        """
        if self._refresh_needed:
            return True
        if self._exception is None:
            return False
        if self._next_retry_time is None:
            return False
        return self._next_retry_time <= datetime.now(timezone.utc)

    @abstractmethod
    async def _execute_refresh(self):
        """Perform the refresh of the cached object.

        :rtype: object
        :return: The cached result of the refresh.
        """

    @abstractmethod
    async def _get_version(self, version_stage):
        """Get a cached secret version based on the given stage.

        :type version_stage: str
        :param version_stage: The version stage being requested.

        :rtype: object
        :return: The associated cached secret version.
        """

    async def __refresh(self):
        """Refresh the cached object when needed.

        The caller must hold self._lock.

        :rtype: bool
        :return: True if the refresh attempt succeeded.
        """
        if not self._is_refresh_needed():
            return self._exception is None
        self._refresh_needed = False
        try:
            result = await self._execute_refresh()
            self._set_result(result)
            self._exception = None
            self._exception_count = 0
            self._next_retry_time = None
            return True
        except Exception as e:
            self._exception = e
            delay = self._config.exception_retry_delay_base * (
                self._config.exception_retry_growth_factor ** self._exception_count
            )
            self._exception_count += 1
            delay = min(delay, self._config.exception_retry_delay_max)
            self._next_retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
            return False

    async def get_secret_value(self, version_stage=None):
        """Get the cached secret value for the given version stage.

        :type version_stage: str
        :param version_stage: The requested secret version stage.

        :rtype: object
        :return: The cached secret value.
        """
        if not version_stage:
            version_stage = self._config.default_version_stage
        async with self._lock:
            await self.__refresh()
            value = await self._get_version(version_stage)
            if not value and self._exception:
                raise self._exception
            return deepcopy(value)

    async def refresh_secret_now(self):
        """Force a refresh of the cached secret.

        :rtype: bool
        :return: True if the refresh succeeded.
        """
        async with self._lock:
            retry_at = self._next_retry_time if self._exception is not None else None

        # Generate a random number to have a sleep jitter to not get stuck in a retry loop
        sleep = randint(int(self.FORCE_REFRESH_JITTER_SLEEP / 2), self.FORCE_REFRESH_JITTER_SLEEP + 1)

        # Waits at most FORCE_REFRESH_MAX_SLEEP for a pending retry backoff,
        # then refreshes regardless of how much backoff remains.
        if retry_at is not None:
            exception_sleep = (retry_at - datetime.now(timezone.utc)).total_seconds() * 1000
            sleep = max(min(exception_sleep, self.FORCE_REFRESH_MAX_SLEEP), sleep)

        # divide sleep(millis) by 1000 to get seconds
        await asyncio.sleep(sleep / 1000)

        async with self._lock:
            self._refresh_needed = True
            return await self.__refresh()

    def _get_result(self):
        """Get the stored result using a hook if present"""
        if self._config.secret_cache_hook is None:
            return self._result

        return self._config.secret_cache_hook.get(self._result)

    def _set_result(self, result):
        """Store the given result using a hook if present"""
        if self._config.secret_cache_hook is None:
            self._result = result
            return

        self._result = self._config.secret_cache_hook.put(result)


class SecretCacheItem(SecretCacheObject):
    """The secret cache item that maintains a cache of secret versions."""

    def __init__(self, config, client, secret_id):
        """Construct a secret cache item.


        :type config: aws_secretsmanager_caching.SecretCacheConfig
        :param config: Configuration for the cache.

        :type client: botocore.client.BaseClient
        :param client: The 'secretsmanager' boto client.

        :type secret_id: str
        :param secret_id: The secret identifier to cache.
        """
        super(SecretCacheItem, self).__init__(config, client, secret_id)
        self._versions = LRUCache(10)
        self._next_refresh_time = datetime.now(timezone.utc)

    def _is_refresh_needed(self):
        """Determine if the cached item should be refreshed.

        :rtype: bool
        :return: True if a refresh is needed.
        """
        if super(SecretCacheItem, self)._is_refresh_needed():
            return True
        if self._exception:
            return False
        return self._next_refresh_time <= datetime.now(timezone.utc)

    @staticmethod
    def _get_version_id(result, version_stage):
        """Get the version id for the given version stage.

        :type: dict
        :param result: The result of the DescribeSecret request.

        :type version_stage: str
        :param version_stage: The version stage being requested.

        :rtype: str
        :return: The associated version id.
        """
        if not result:
            return None
        if "VersionIdsToStages" not in result:
            return None
        ids = [key for (key, value) in result["VersionIdsToStages"].items() if version_stage in value]
        if not ids:
            return None
        return ids[0]

    async def _execute_refresh(self):
        """Perform the actual refresh of the cached secret information.

        :rtype: dict
        :return: The result of the DescribeSecret request.
        """
        result = await self._client.describe_secret(SecretId=self._secret_id)
        ttl = self._config.secret_refresh_interval
        self._next_refresh_time = datetime.now(timezone.utc) + timedelta(seconds=randint(round(ttl / 2), ttl))
        return result

    async def _get_version(self, version_stage):
        """Get the version associated with the given stage.

        :type version_stage: str
        :param version_stage: The version stage being requested.

        :rtype: dict
        :return: The cached secret for the given version stage.
        """
        version_id = self._get_version_id(self._get_result(), version_stage)
        if not version_id:
            return None
        version = await self._versions.get(version_id)
        if version:
            return await version.get_secret_value()
        await self._versions.put_if_absent(version_id, SecretCacheVersion(self._config, self._client, self._secret_id,
                                                                          version_id))
        version = await self._versions.get(version_id)
        return await version.get_secret_value()


class SecretCacheVersion(SecretCacheObject):
    """Secret cache object for a secret version."""

    def __init__(self, config, client, secret_id, version_id):
        """Construct the cache object for a secret version.

        :type config: aws_secretsmanager_caching.SecretCacheConfig
        :param config: Configuration for the cache.

        :type client: botocore.client.BaseClient
        :param client: The 'secretsmanager' boto client.

        :type secret_id: str
        :param secret_id: The secret identifier to cache.

        :type version_id: str
        :param version_id: The version identifier.
        """
        super(SecretCacheVersion, self).__init__(config, client, secret_id)
        self._version_id = version_id

    async def _execute_refresh(self):
        """Perform the actual refresh of the cached secret version.

        :rtype: dict
        :return: The result of GetSecretValue for the version.
        """
        return await self._client.get_secret_value(SecretId=self._secret_id, VersionId=self._version_id)

    async def _get_version(self, version_stage):
        """Get the cached version information for the given stage.

        :type version_stage: str
        :param version_stage: The version stage being requested.

        :rtype: dict
        :return: The cached GetSecretValue result.
        """
        return self._get_result()