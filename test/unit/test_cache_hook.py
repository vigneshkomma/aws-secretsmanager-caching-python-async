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
Unit test suite for SecretCacheHook
"""
import pytest
from unittest.mock import AsyncMock

from aws_secretsmanager_caching.cache.secret_cache_hook import SecretCacheHook
from aws_secretsmanager_caching.config import SecretCacheConfig
from aws_secretsmanager_caching.secret_cache import SecretCache


class DummySecretCacheHook(SecretCacheHook):
    """A dummy implementation of the SecretCacheHook abstract class for testing"""

    dict = {}

    def put(self, obj):
        if 'SecretString' in obj:
            obj['SecretString'] = obj['SecretString'] + "+hook_put"

        if 'SecretBinary' in obj:
            obj['SecretBinary'] = obj['SecretBinary'] + b'11111111'

        key = len(self.dict)
        self.dict[key] = obj
        return key

    def get(self, cached_obj):
        obj = self.dict[cached_obj]

        if 'SecretString' in obj:
            obj['SecretString'] = obj['SecretString'] + "+hook_get"

        if 'SecretBinary' in obj:
            obj['SecretBinary'] = obj['SecretBinary'] + b'00000000'

        return obj


@pytest.mark.asyncio
class TestSecretCacheHook:

    def _make_mock_client(self, versions=None, version_response=None):
        client = AsyncMock()

        if versions is None:
            versions = {
                '01234567890123456789012345678901': ['AWSCURRENT']
            }

        client.describe_secret = AsyncMock(return_value={
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "Name": "test",
            "VersionIdsToStages": versions,
        })

        if version_response is not None:
            client.get_secret_value = AsyncMock(return_value=version_response)
        else:
            client.get_secret_value = AsyncMock(return_value={})

        return client

    async def test_calls_hook_string(self):
        secret = 'mysecret'
        hooked_secret = secret + "+hook_put+hook_get"
        version_response = {'SecretString': secret}

        hook = DummySecretCacheHook()
        config = SecretCacheConfig(secret_cache_hook=hook)

        client = self._make_mock_client(version_response=version_response)
        cache = await SecretCache.create(config=config, client=client)

        for _ in range(10):
            fetched_secret = await cache.get_secret_string('test')
            assert fetched_secret.startswith(hooked_secret)

    async def test_calls_hook_binary(self):
        secret = b'01010101'
        hooked_secret = secret + b'1111111100000000'
        version_response = {'SecretBinary': secret}

        hook = DummySecretCacheHook()
        config = SecretCacheConfig(secret_cache_hook=hook)

        client = self._make_mock_client(version_response=version_response)
        cache = await SecretCache.create(config=config, client=client)

        for _ in range(10):
            result = await cache.get_secret_binary('test')
            assert result[:24] == hooked_secret