# Usage Guide

## Basic Usage

### Creating a Cache

The `SecretCache` is created via the async factory method `SecretCache.create()`. This sets up an `aiobotocore` secrets manager client and initializes the in-memory cache.

```python
import asyncio
from aws_secretsmanager_caching import SecretCache

async def main():
    cache = await SecretCache.create()
    # ... use the cache ...
    await cache.close()

asyncio.run(main())
```

### Retrieving a Secret String

```python
secret = await cache.get_secret_string("my-secret")
print(secret)  # The secret value as a string
```

### Retrieving a Secret Binary

```python
binary_data = await cache.get_secret_binary("my-secret")
print(binary_data)  # The secret value as bytes
```

### Specifying a Version Stage

By default, the cache retrieves the `AWSCURRENT` version. You can request a different stage:

```python
# Get the previous version
previous = await cache.get_secret_string("my-secret", version_stage="AWSPREVIOUS")
```

### Forcing a Refresh

If you know a secret has been rotated and want to bypass the cache immediately:

```python
success = await cache.refresh_secret_now("my-secret")
if success:
    print("Secret refreshed")
else:
    print("Refresh failed, check the exception")
```

### Cleaning Up

Always close the cache when you're done to release the underlying `aiobotocore` client resources:

```python
await cache.close()
```

## Using a Pre-configured Client

If you need to customize the `aiobotocore` client (e.g., custom endpoint, region, credentials), create one yourself and pass it in:

```python
import aiobotocore.session
import aiobotocore.config
from aws_secretsmanager_caching import SecretCache

async def main():
    session = aiobotocore.session.AioSession()
    boto_config = aiobotocore.config.AioConfig(
        connect_timeout=5,
        read_timeout=5,
        retries={"max_attempts": 3},
    )

    client = await session.create_client(
        "secretsmanager",
        region_name="eu-west-1",
        config=boto_config,
    ).__aenter__()

    cache = await SecretCache.create(client=client)
    secret = await cache.get_secret_string("my-secret")
    await cache.close()

asyncio.run(main())
```

## Working with JSON Secrets

Many applications store JSON in secrets. Here's a pattern for working with them:

```python
import asyncio
import json
from aws_secretsmanager_caching import SecretCache

async def main():
    cache = await SecretCache.create()
    secret_str = await cache.get_secret_string("db-credentials")
    creds = json.loads(secret_str)

    print(f"Host: {creds['host']}")
    print(f"Port: {creds['port']}")
    print(f"Username: {creds['username']}")

    await cache.close()

asyncio.run(main())
```

## Multiple Secrets

The cache handles many secrets efficiently via its LRU eviction policy:

```python
secrets = [
    "db-credentials",
    "api-key",
    "oauth-token",
    "encryption-key",
]

for secret_id in secrets:
    value = await cache.get_secret_string(secret_id)
    print(f"{secret_id}: {value[:20]}...")
```

## Error Handling

### Transient Errors

The cache automatically retries failed requests with exponential backoff and jitter. You don't need to handle transient errors yourself.

### Fatal Errors

When all retries are exhausted, or the error is non-retryable (e.g., `ResourceNotFoundException`), the exception propagates to your code:

```python
try:
    secret = await cache.get_secret_string("secret-that-does-not-exist")
except cache._client.exceptions.ResourceNotFoundException:
    print("Secret not found!")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Context Manager Usage

The cache can be used as an async context manager for automatic cleanup:

```python
import asyncio
from aws_secretsmanager_caching import SecretCache

async def main():
    cache = await SecretCache.create()
    async with cache:
        secret = await cache.get_secret_string("my-secret")
        print(secret)
    # cache is automatically closed
```

> **Note:** This requires implementing `__aenter__` and `__aexit__` on `SecretCache`. If not yet available, use `try/finally`:

```python
cache = await SecretCache.create()
try:
    secret = await cache.get_secret_string("my-secret")
finally:
    await cache.close()
```

## Application Startup Pattern

A common pattern is to warm the cache on application startup:

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

async def startup():
    config = SecretCacheConfig(
        secret_refresh_interval=3600,  # Refresh every hour
    )
    cache = await SecretCache.create(config=config)

    # Warm up critical secrets
    for secret_id in ["db-credentials", "api-key"]:
        await cache.get_secret_string(secret_id)

    return cache
```