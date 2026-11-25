# AWS Secrets Manager Caching Client (Async)

An async Python caching client for AWS Secrets Manager, backed by `aiobotocore`.

## Installation

```bash
pip install aiobotocore
```

## Usage

```python
import asyncio
from aws_secretsmanager_caching import SecretCache


async def main():
    # Create the cache (async factory)
    cache = await SecretCache.create()

    # Get a secret string
    password = await cache.get_secret_string("my-secret")
    print(password)

    # Get a secret binary
    binary_data = await cache.get_secret_binary("my-secret")

    # Force a refresh
    await cache.refresh_secret_now("my-secret")

    # Clean up
    await cache.close()


asyncio.run(main())
```

## Configuration

```python
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

config = SecretCacheConfig(
    secret_refresh_interval=300,   # Refresh every 5 minutes
    max_cache_size=50,             # Cache up to 50 secrets
)
cache = await SecretCache.create(config=config)
```

## Development

```bash
pip install -e .
pip install -r dev-requirements.txt
```