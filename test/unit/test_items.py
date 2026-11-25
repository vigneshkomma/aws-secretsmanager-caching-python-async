# Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""
Unit test suite for items module
"""
import pytest
from datetime import timezone, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from aws_secretsmanager_caching.cache.items import SecretCacheObject, SecretCacheItem, SecretCacheVersion
from aws_secretsmanager_caching.config import SecretCacheConfig


pytestmark = [pytest.mark.unit, pytest.mark.local]


class TestSecretCacheObject:

    class TestObject(SecretCacheObject):

        def __init__(self, config, client, secret_id):
            super().__init__(config, client, secret_id)

        async def _execute_refresh(self):
            pass

        async def _get_version(self, version_stage):
            return self._get_result()

    @pytest.mark.asyncio
    async def test_simple(self):
        sco = TestSecretCacheObject.TestObject(SecretCacheConfig(), None, None)
        result = await sco.get_secret_value()
        assert result is None

    @pytest.mark.asyncio
    async def test_simple_2(self):
        sco = TestSecretCacheObject.TestObject(SecretCacheConfig(), None, None)
        result = await sco.get_secret_value()
        assert result is None
        sco._exception = Exception("test")
        with pytest.raises(Exception, match="test"):
            await sco.get_secret_value()

    @pytest.mark.asyncio
    async def test_refresh_now(self):
        config = SecretCacheConfig()

        client_mock = AsyncMock()
        client_mock.describe_secret = AsyncMock(return_value="test")
        secret_cache_item = SecretCacheItem(config, client_mock, None)
        secret_cache_item._next_refresh_time = datetime.now(timezone.utc) + timedelta(days=30)
        secret_cache_item._refresh_needed = False
        assert not secret_cache_item._is_refresh_needed()

        old_refresh_time = secret_cache_item._next_refresh_time
        assert old_refresh_time > datetime.now(timezone.utc) + timedelta(days=29)

        await secret_cache_item.refresh_secret_now()
        new_refresh_time = secret_cache_item._next_refresh_time

        ttl = config.secret_refresh_interval
        assert new_refresh_time < old_refresh_time
        assert new_refresh_time < datetime.now(timezone.utc) + timedelta(seconds=ttl)

    @pytest.mark.asyncio
    async def test_datetime_fix_is_refresh_needed(self):
        secret_cached_object = TestSecretCacheObject.TestObject(SecretCacheConfig(), None, None)

        secret_cached_object._next_retry_time = datetime.now(tz=timezone.utc)
        secret_cached_object._refresh_needed = False
        secret_cached_object._exception = Exception("err")

        assert secret_cached_object._is_refresh_needed()

    @pytest.mark.asyncio
    async def test_datetime_fix_refresh(self):
        exp_factor = 11

        secret_cached_object = SecretCacheObject(
            SecretCacheConfig(exception_retry_delay_base=1, exception_retry_growth_factor=2),
            None, None
        )
        secret_cached_object._set_result = Mock(side_effect=Exception("exception used for test"))
        secret_cached_object._refresh_needed = True
        secret_cached_object._exception_count = exp_factor

        t_before = datetime.now(tz=timezone.utc)
        await secret_cached_object._SecretCacheObject__refresh()
        t_after = datetime.now(tz=timezone.utc)

        t_before_delay = t_before + timedelta(
            seconds=secret_cached_object._config.exception_retry_delay_base * (
                secret_cached_object._config.exception_retry_growth_factor ** exp_factor
            )
        )
        assert t_before_delay <= secret_cached_object._next_retry_time

        t_after_delay = t_after + timedelta(
            seconds=secret_cached_object._config.exception_retry_delay_base * (
                secret_cached_object._config.exception_retry_growth_factor ** exp_factor
            )
        )
        assert t_after_delay >= secret_cached_object._next_retry_time

    @pytest.mark.asyncio
    async def test_force_refresh_with_retry_pending(self):
        sco = SecretCacheObject(SecretCacheConfig(), None, None)
        sco._execute_refresh = AsyncMock(side_effect=Exception("exception used for test"))
        sco._refresh_needed = True

        await sco._SecretCacheObject__refresh()
        assert sco._exception is not None
        assert sco._next_retry_time is not None

        # Patch refresh_secret_now to avoid the actual sleep
        import aws_secretsmanager_caching.cache.items as items_module
        with patch.object(items_module.asyncio, 'sleep', AsyncMock()):
            sco._execute_refresh = AsyncMock(return_value="refreshed")
            refreshed = await sco.refresh_secret_now()

        assert refreshed
        sco._execute_refresh.assert_awaited_once()
        assert sco._get_result() == "refreshed"
        assert sco._exception is None
        assert sco._exception_count == 0
        assert sco._next_retry_time is None

    @pytest.mark.asyncio
    async def test_force_refresh_reports_failure(self):
        sco = SecretCacheObject(SecretCacheConfig(), None, None)
        sco._execute_refresh = AsyncMock(side_effect=Exception("exception used for test"))

        import aws_secretsmanager_caching.cache.items as items_module
        with patch.object(items_module.asyncio, 'sleep', AsyncMock()):
            result = await sco.refresh_secret_now()
            assert not result
            assert sco._execute_refresh.call_count == 1

            result = await sco.refresh_secret_now()
            assert not result
            assert sco._execute_refresh.call_count == 2

            assert sco._exception is not None
            with pytest.raises(Exception):
                await sco.get_secret_value()

    @pytest.mark.asyncio
    async def test_refresh_secret_now_success(self):
        sco = SecretCacheObject(SecretCacheConfig(), None, None)
        sco._execute_refresh = AsyncMock(return_value="refreshed")

        import aws_secretsmanager_caching.cache.items as items_module
        with patch.object(items_module.asyncio, 'sleep', AsyncMock()):
            result = await sco.refresh_secret_now()
            assert result


class TestSecretCacheItem:

    def test_datetime_fix_SCI_init(self):
        config = SecretCacheConfig()
        t_before = datetime.now(tz=timezone.utc)
        secret_cache_item = SecretCacheItem(config, None, None)
        t_after = datetime.now(tz=timezone.utc)

        assert secret_cache_item._next_refresh_time >= t_before
        assert secret_cache_item._next_refresh_time <= t_after

    def test_datetime_fix_refresh_needed(self):
        config = SecretCacheConfig()
        secret_cache_item = SecretCacheItem(config, None, None)

        secret_cache_item._refresh_needed = False
        secret_cache_item._exception = False
        secret_cache_item._next_retry_time = None

        assert secret_cache_item._is_refresh_needed()

    @pytest.mark.asyncio
    async def test_datetime_fix_execute_refresh(self):
        client_mock = AsyncMock()
        client_mock.describe_secret = AsyncMock(return_value="test")

        config = SecretCacheConfig()
        secret_cache_item = SecretCacheItem(config, client_mock, None)

        t_before = datetime.now(tz=timezone.utc)
        await secret_cache_item._execute_refresh()
        t_after = datetime.now(tz=timezone.utc)

        assert secret_cache_item._next_refresh_time.tzinfo == timezone.utc
        assert secret_cache_item._next_refresh_time >= t_before
        t_max_after = t_after + timedelta(seconds=config.secret_refresh_interval)
        assert secret_cache_item._next_refresh_time <= t_max_after

    @pytest.mark.asyncio
    async def test_get_version_cached(self):
        """Test that _get_version uses cached version when available"""
        client_mock = AsyncMock()
        client_mock.describe_secret = AsyncMock(return_value={
            "VersionIdsToStages": {
                "v1-uuid": ["AWSCURRENT"]
            }
        })
        client_mock.get_secret_value = AsyncMock(return_value={
            "SecretString": "test-value",
            "SecretBinary": b"test-binary",
        })

        config = SecretCacheConfig()
        item = SecretCacheItem(config, client_mock, "test-secret")

        # First call - should trigger refresh and get_secret_value
        result = await item.get_secret_value("AWSCURRENT")
        assert result is not None
        assert result.get("SecretString") == "test-value"

        # Second call - should use cached version
        result2 = await item.get_secret_value("AWSCURRENT")
        assert result2 is not None
        assert result2.get("SecretString") == "test-value"

    @pytest.mark.asyncio
    async def test_get_version_id_static(self):
        result = {
            "VersionIdsToStages": {
                "v1-uuid": ["AWSCURRENT"],
                "v0-uuid": ["AWSPREVIOUS"]
            }
        }
        assert SecretCacheItem._get_version_id(result, "AWSCURRENT") == "v1-uuid"
        assert SecretCacheItem._get_version_id(result, "AWSPREVIOUS") == "v0-uuid"
        assert SecretCacheItem._get_version_id(result, "NONEXISTENT") is None
        assert SecretCacheItem._get_version_id(None, "AWSCURRENT") is None
        assert SecretCacheItem._get_version_id({}, "AWSCURRENT") is None


class TestSecretCacheVersion:

    @pytest.mark.asyncio
    async def test_execute_refresh(self):
        client_mock = AsyncMock()
        client_mock.get_secret_value = AsyncMock(return_value={
            "SecretString": "version-value"
        })

        config = SecretCacheConfig()
        version = SecretCacheVersion(config, client_mock, "test-secret", "v1-uuid")

        result = await version._execute_refresh()
        assert result == {"SecretString": "version-value"}
        client_mock.get_secret_value.assert_called_once_with(
            SecretId="test-secret",
            VersionId="v1-uuid"
        )

    @pytest.mark.asyncio
    async def test_get_version(self):
        config = SecretCacheConfig()
        version = SecretCacheVersion(config, None, "test-secret", "v1-uuid")
        version._result = {"SecretString": "cached-value"}

        result = await version._get_version("AWSCURRENT")
        assert result == {"SecretString": "cached-value"}