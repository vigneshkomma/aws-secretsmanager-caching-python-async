# AWS Secrets Manager Caching Client (Async)

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

An **async-native** Python caching client for [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/), built on top of `aiobotocore`. This is the asynchronous counterpart to the official [aws-secretsmanager-caching-python](https://github.com/aws/aws-secretsmanager-caching-python) library, designed for use with `asyncio`-based applications.

> **Why this library?** Fetching secrets on every request is slow and expensive. This client caches secrets in memory, refreshes them automatically in the background, and handles retries with exponential backoff — so your application always has fast, reliable access to secrets.

---

## Features

- **Async-first** — built for `asyncio` with `aiobotocore`
- **In-memory LRU cache** — configurable max size, evicts least-recently used secrets
- **Automatic refresh** — secrets are refreshed in the background at a configurable interval
- **Exponential backoff** — retries failed requests with jitter to avoid thundering herd
- **Thread-safe** — uses `asyncio.Lock` for safe concurrent access
- **Decorators** — inject secrets directly into your async functions
- **Customizable hooks** — encrypt/decrypt or transform cached secrets via `SecretCacheHook`
- **Version-aware** — caches multiple versions of a secret per stage (e.g. `AWSCURRENT`, `AWSPREVIOUS`)

---

## Installation

```bash
pip install aiobotocore
```

> **Note:** This library is not yet published on PyPI. To install locally, see [Development](#development).

---

## Quick Start

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig


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

---

## Advanced Usage

### Custom Configuration

```python
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

config = SecretCacheConfig(
    secret_refresh_interval=300,    # Refresh every 5 minutes (default: 3600)
    max_cache_size=50,              # Cache up to 50 secrets (default: 1024)
    exception_retry_delay_base=2,   # Start retry at 2 seconds (default: 1)
    exception_retry_growth_factor=3,# Exponential growth factor (default: 2)
    exception_retry_delay_max=600,  # Max retry delay of 10 minutes (default: 3600)
    default_version_stage="AWSCURRENT",  # Version stage (default: AWSCURRENT)
)

cache = await SecretCache.create(config=config)
```

### Using a Pre-configured Client

If you already have an `aiobotocore` client (e.g. configured with custom credentials, region, or endpoint), pass it directly:

```python
import aiobotocore.session
import aiobotocore.config
from aws_secretsmanager_caching import SecretCache

session = aiobotocore.session.AioSession()
client = await session.create_client(
    "secretsmanager",
    region_name="us-west-2",
).__aenter__()

cache = await SecretCache.create(client=client)
```

### Injecting Secrets into Functions (Decorators)

#### `InjectSecretString`

Injects the raw secret string as the **first positional argument** to your async function:

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, InjectSecretString

async def main():
    cache = await SecretCache.create()

    @InjectSecretString("my-secret", cache)
    async def process_with_secret(password: str):
        print(f"Using password: {password}")

    await process_with_secret()
    await cache.close()

asyncio.run(main())
```

#### `InjectKeywordedSecretString`

Injects specific fields from a **JSON secret** as named keyword arguments:

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, InjectKeywordedSecretString

async def main():
    cache = await SecretCache.create()

    # Secret is JSON: {"username": "admin", "password": "hunter2"}
    @InjectKeywordedSecretString("my-secret", cache, username="username", password="password")
    async def connect(username: str, password: str):
        print(f"Connecting as {username} with password {password}")

    await connect()
    await cache.close()

asyncio.run(main())
```

> **Note:** Decorators only work with `async` functions when using the async `SecretCache`. Sync functions will raise a `RuntimeError`.

### Error Handling

```python
from aws_secretsmanager_caching import SecretCache

cache = await SecretCache.create()

try:
    secret = await cache.get_secret_string("non-existent-secret")
except Exception as e:
    print(f"Failed to retrieve secret: {e}")
```

The cache handles transient errors internally with exponential backoff. If all retries are exhausted, the exception is propagated to your code.

### Using a `SecretCacheHook`

Transform secrets before they are stored in or retrieved from the cache (e.g. for encryption):

```python
from aws_secretsmanager_caching.cache import SecretCacheHook
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

class MyEncryptionHook(SecretCacheHook):
    def put(self, obj):
        # Encrypt before storing
        return encrypt(obj)

    def get(self, cached_obj):
        # Decrypt after retrieving
        return decrypt(cached_obj)

config = SecretCacheConfig(secret_cache_hook=MyEncryptionHook())
cache = await SecretCache.create(config=config)
```

---

## Documentation

Full documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/installation.md) | Detailed installation and setup |
| [Usage Guide](docs/usage.md) | Comprehensive usage examples |
| [Configuration Reference](docs/configuration.md) | All configuration options |
| [Decorators](docs/decorators.md) | How to use injector decorators |
| [How Caching Works](docs/caching.md) | Internal caching architecture |
| [API Reference](docs/api-reference.md) | Full API documentation |
| [Examples](docs/examples.md) | Real-world usage patterns |

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/your-org/aws-secretsmanager-caching-python-async.git
cd aws-secretsmanager-caching-python-async
pip install -e .

# Install dev dependencies
pip install -r dev-requirements.txt

# Run unit tests
pytest -m unit

# Run integration tests (requires AWS credentials)
pytest -m local

# Run all tests
pytest
```
---
## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

---

## Related

- [Official AWS Secrets Manager Caching Client (sync)](https://github.com/aws/aws-secretsmanager-caching-python)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [aiobotocore](https://github.com/aio-libs/aiobotocore)