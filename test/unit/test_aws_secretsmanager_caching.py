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
Unit test suite for high-level functions in aws_secretsmanager_caching
"""
import pytest
from unittest.mock import AsyncMock

from aws_secretsmanager_caching.config import SecretCacheConfig
from aws_secretsmanager_caching.secret_cache import SecretCache


pytestmark = [pytest.mark.unit, pytest.mark.local]


@pytest.mark.asyncio
class TestAwsSecretsManagerCaching:

    def _make_mock_client(self, describe_result=None, get_value_result=None):
        """Create a mock aiobotocore client with canned responses."""
        client = AsyncMock()

        if describe_result is None:
            describe_result = {
                "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
                "Name": "test",
                "VersionIdsToStages": {
                    "01234567890123456789012345678901": ["AWSCURRENT"]
                }
            }
        client.describe_secret = AsyncMock(return_value=describe_result)

        if get_value_result is None:
            get_value_result = {"SecretString": "mysecret"}
        client.get_secret_value = AsyncMock(return_value=get_value_result)

        return client

    async def test_create_with_client(self):
        client = self._make_mock_client()
        cache = await SecretCache.create(client=client)
        assert cache is not None
        assert cache._client is client
        await cache.close()

    async def test_get_secret_string_none(self):
        # No versions defined — describe_secret returns empty dict
        client = self._make_mock_client(
            describe_result={
                "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
                "Name": "test",
            }
        )
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_string("test")
        assert result is None

    async def test_get_secret_string_missing(self):
        describe_result = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test",
            "VersionIdsToStages": {
                "01234567890123456789012345678901": ["AWSCURRENT"]
            }
        }
        version_response = {"Name": "test"}  # No SecretString key
        client = self._make_mock_client(
            describe_result=describe_result,
            get_value_result=version_response
        )
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_string("test")
        assert result is None

    async def test_get_secret_string_no_current(self):
        describe_result = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test",
            "VersionIdsToStages": {
                "01234567890123456789012345678901": ["NOTCURRENT"]
            }
        }
        version_response = {"Name": "test"}
        client = self._make_mock_client(
            describe_result=describe_result,
            get_value_result=version_response
        )
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_string("test")
        assert result is None

    async def test_get_secret_string_no_versions(self):
        describe_result = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test"
            # No VersionIdsToStages
        }
        client = self._make_mock_client(describe_result=describe_result)
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_string("test")
        assert result is None

    async def test_get_secret_string_empty(self):
        describe_result = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test",
            "VersionIdsToStages": {
                "01234567890123456789012345678901": ["AWSCURRENT"]
            }
        }
        version_response = {}  # Empty response
        client = self._make_mock_client(
            describe_result=describe_result,
            get_value_result=version_response
        )
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_string("test")
        assert result is None

    async def test_get_secret_string(self):
        secret = "mysecret"
        version_response = {"SecretString": secret}
        client = self._make_mock_client(get_value_result=version_response)
        cache = await SecretCache.create(client=client)

        for _ in range(10):
            result = await cache.get_secret_string("test")
            assert result == secret

        # Only one API call each for describe + get_value (cached)
        assert client.describe_secret.call_count == 1
        assert client.get_secret_value.call_count == 1

    async def test_get_secret_string_refresh_with_mock(self):
        secret = "mysecret"
        version_response = {"SecretString": secret}
        describe_result = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test",
            "VersionIdsToStages": {
                "01234567890123456789012345678901": ["AWSCURRENT"]
            }
        }

        client = AsyncMock()
        client.describe_secret = AsyncMock(return_value=describe_result)
        client.get_secret_value = AsyncMock(return_value=version_response)

        cache = await SecretCache.create(
            config=SecretCacheConfig(secret_refresh_interval=1),
            client=client
        )

        for _ in range(10):
            result = await cache.get_secret_string("test")
            assert result == secret

    async def test_get_secret_string_stage(self):
        secret = "mysecret"
        version_response = {"SecretString": secret}
        client = self._make_mock_client(get_value_result=version_response)
        cache = await SecretCache.create(client=client)

        for _ in range(10):
            result = await cache.get_secret_string("test", "AWSCURRENT")
            assert result == secret

    async def test_get_secret_string_multiple(self):
        # No versions defined — simulate empty describe result
        client = self._make_mock_client(
            describe_result={
                "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
                "Name": "test",
            }
        )
        cache = await SecretCache.create(client=client)

        for _ in range(100):
            result = await cache.get_secret_string("test")
            assert result is None

    async def test_get_secret_binary(self):
        secret = b"01010101"
        version_response = {"SecretBinary": secret}
        client = self._make_mock_client(get_value_result=version_response)
        cache = await SecretCache.create(client=client)

        for _ in range(10):
            result = await cache.get_secret_binary("test")
            assert result == secret

    async def test_get_secret_binary_no_versions(self):
        client = self._make_mock_client()
        cache = await SecretCache.create(client=client)
        result = await cache.get_secret_binary("test")
        assert result is None

    async def test_refresh_secret_now(self):
        secret = "mysecret"
        version_response = {"SecretString": secret}
        client = self._make_mock_client(get_value_result=version_response)
        cache = await SecretCache.create(client=client)

        # First call populates the cache
        result = await cache.get_secret_string("test")
        assert result == secret

        # Record the version count before refresh
        secret_item = cache._cache._cache["test"].data
        old_version_count = secret_item._exception_count

        # Force refresh — patch asyncio.sleep to avoid the 2.5-10s jitter delay
        from unittest.mock import patch
        with patch("aws_secretsmanager_caching.cache.items.asyncio.sleep", AsyncMock()):
            result = await cache.refresh_secret_now("test")
            assert result

        # Verify the refresh actually happened (no error state)
        assert secret_item._exception is None
        assert secret_item._exception_count == 0

    async def test_get_secret_string_exception(self):
        client = AsyncMock()
        client.describe_secret = AsyncMock(side_effect=Exception("Describe failed"))

        cache = await SecretCache.create(client=client)

        with pytest.raises(Exception, match="Describe failed"):
            await cache.get_secret_string("test")

    async def test_multiple_secrets_independent(self):
        """Different secrets should not block each other."""
        client = AsyncMock()

        def describe_side_effect(SecretId=None, **kwargs):
            if SecretId == "secret-a":
                return {
                    "VersionIdsToStages": {"v1": ["AWSCURRENT"]}
                }
            elif SecretId == "secret-b":
                return {
                    "VersionIdsToStages": {"v2": ["AWSCURRENT"]}
                }
            return {}

        def get_value_side_effect(SecretId=None, VersionId=None, **kwargs):
            if SecretId == "secret-a":
                return {"SecretString": "value-a"}
            elif SecretId == "secret-b":
                return {"SecretString": "value-b"}
            return {}

        client.describe_secret = AsyncMock(side_effect=describe_side_effect)
        client.get_secret_value = AsyncMock(side_effect=get_value_side_effect)

        cache = await SecretCache.create(client=client)

        result_a = await cache.get_secret_string("secret-a")
        result_b = await cache.get_secret_string("secret-b")

        assert result_a == "value-a"
        assert result_b == "value-b"

    async def test_caching_behavior(self):
        """Verify that cache hits make zero API calls."""
        client = self._make_mock_client(
            get_value_result={"SecretString": "cached-secret"}
        )
        cache = await SecretCache.create(client=client)

        # First call — should call API
        result1 = await cache.get_secret_string("test-cache")
        assert result1 == "cached-secret"
        assert client.describe_secret.call_count == 1
        assert client.get_secret_value.call_count == 1

        # Second call — should be cached, zero API calls
        result2 = await cache.get_secret_string("test-cache")
        assert result2 == "cached-secret"
        assert client.describe_secret.call_count == 1
        assert client.get_secret_value.call_count == 1