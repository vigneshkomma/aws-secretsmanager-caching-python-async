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
Unit test suite for LRU cache
"""
import pytest
from aws_secretsmanager_caching.cache.lru import LRUCache


pytestmark = [pytest.mark.unit, pytest.mark.local]


@pytest.mark.asyncio
class TestLRUCache:

    async def test_lru_cache_max(self):
        cache = LRUCache(max_size=10)
        for n in range(100):
            await cache.put_if_absent(n, n)
        for n in range(90):
            result = await cache.get(n)
            assert result is None
        for n in range(91, 100):
            result = await cache.get(n)
            assert result is not None

    async def test_lru_cache_none(self):
        cache = LRUCache(max_size=10)
        result = await cache.get(1)
        assert result is None

    async def test_lru_cache_recent(self):
        cache = LRUCache(max_size=10)
        for n in range(100):
            await cache.put_if_absent(n, n)
            await cache.get(0)
        for n in range(1, 91):
            result = await cache.get(n)
            assert result is None
        for n in range(92, 100):
            result = await cache.get(n)
            assert result is not None
        result = await cache.get(0)
        assert result is not None

    async def test_lru_cache_zero(self):
        cache = LRUCache(max_size=0)
        for n in range(100):
            await cache.put_if_absent(n, n)
            result = await cache.get(n)
            assert result is None
        for n in range(100):
            result = await cache.get(n)
            assert result is None

    async def test_lru_cache_one(self):
        cache = LRUCache(max_size=1)
        for n in range(100):
            await cache.put_if_absent(n, n)
            result = await cache.get(n)
            assert result == n
        for n in range(99):
            result = await cache.get(n)
            assert result is None
        result = await cache.get(99)
        assert result == 99

    async def test_lru_cache_if_absent(self):
        cache = LRUCache(max_size=1)
        for n in range(100):
            await cache.put_if_absent(1000, 1000)
            result = await cache.get(n)
            assert result is None
        result = await cache.get(1000)
        assert result == 1000

    async def test_lru_cache_put_if_absent_existing(self):
        cache = LRUCache(max_size=10)
        result1 = await cache.put_if_absent("key", "value1")
        assert result1 is True
        result2 = await cache.put_if_absent("key", "value2")
        assert result2 is False
        result = await cache.get("key")
        assert result == "value1"