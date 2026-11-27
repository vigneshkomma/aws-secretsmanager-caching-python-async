# API Reference

## `aws_secretsmanager_caching` (Top-Level Package)

### `SecretCache`

The main caching client for AWS Secrets Manager.

#### `SecretCache.create(config=None, client=None)`

*Async class method.* Creates a `SecretCache` instance with an `aiobotocore` secrets manager client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `SecretCacheConfig` | `None` | Cache configuration (uses defaults if omitted) |
| `client` | `aiobotocore.client.BaseClient` | `None` | Pre-configured client (auto-created if omitted) |

| Returns | Type |
|---------|------|
| Initialized cache | `SecretCache` |

```python
cache = await SecretCache.create()
cache = await SecretCache.create(config=config)
cache = await SecretCache.create(client=custom_client)
```

#### `get_secret_string(secret_id, version_stage=None)`

*Async method.* Retrieves a secret string value from the cache.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `secret_id` | `str` | — | The secret name or ARN |
| `version_stage` | `str` | `None` | Version stage (uses config default if omitted) |

| Returns | Type |
|---------|------|
| Secret string value | `str` or `None` |

```python
secret = await cache.get_secret_string("my-secret")
secret = await cache.get_secret_string("my-secret", version_stage="AWSPREVIOUS")
```

#### `get_secret_binary(secret_id, version_stage=None)`

*Async method.* Retrieves a secret binary value from the cache.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `secret_id` | `str` | — | The secret name or ARN |
| `version_stage` | `str` | `None` | Version stage (uses config default if omitted) |

| Returns | Type |
|---------|------|
| Secret binary value | `bytes` or `None` |

```python
binary = await cache.get_secret_binary("my-secret")
```

#### `refresh_secret_now(secret_id)`

*Async method.* Forces an immediate refresh of the cached secret metadata.

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_id` | `str` | The secret name or ARN |

| Returns | Type |
|---------|------|
| `True` if refresh succeeded | `bool` |

```python
success = await cache.refresh_secret_now("my-secret")
```

#### `close()`

*Async method.* Closes the underlying `aiobotocore` client and releases resources.

```python
await cache.close()
```

---

### `SecretCacheConfig`

Configuration class for `SecretCache`. Accepts any subset of options as keyword arguments.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_cache_size` | `int` | `1024` | Maximum secrets to cache |
| `secret_refresh_interval` | `int` | `3600` | Seconds between refreshes |
| `exception_retry_delay_base` | `int` | `1` | Initial retry delay (seconds) |
| `exception_retry_growth_factor` | `int` | `2` | Backoff growth factor |
| `exception_retry_delay_max` | `int` | `3600` | Max retry delay (seconds) |
| `default_version_stage` | `str` | `"AWSCURRENT"` | Default version stage |
| `secret_cache_hook` | `SecretCacheHook` | `None` | Custom cache hook |

```python
config = SecretCacheConfig(max_cache_size=100, secret_refresh_interval=600)
```

Raises `TypeError` if an unknown keyword argument is provided.

---

### `InjectSecretString`

Decorator that injects a secret string as the first positional argument.

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_id` | `str` | The secret name or ARN |
| `cache` | `SecretCache` | An initialized cache instance |

```python
@InjectSecretString("my-secret", cache)
async def my_func(secret: str, ...):
    ...
```

---

### `InjectKeywordedSecretString`

Decorator that injects JSON secret fields as keyword arguments.

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_id` | `str` | The secret name or ARN |
| `cache` | `SecretCache` | An initialized cache instance |
| `**kwargs` | `dict` | Maps parameter names → JSON keys |

```python
@InjectKeywordedSecretString("my-secret", cache, username="username", password="password")
async def my_func(username: str, password: str, ...):
    ...
```

---

## `aws_secretsmanager_caching.cache` (Internal)

> **Warning:** This module is considered internal. No guarantee is provided on the stability of these APIs. Directly reference at your own risk.

### `LRUCache`

A thread-safe LRU cache using `asyncio.Lock` and a doubly-linked list.

#### `__init__(max_size=1024)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_size` | `int` | `1024` | Maximum number of items |

#### `get(key)`

*Async.* Retrieves an item. Returns `None` if not found.

#### `put_if_absent(key, data)`

*Async.* Stores an item only if the key doesn't already exist. Returns `True` if stored.

### `SecretCacheItem`

Represents a single cached secret. Manages version lookups and refresh timing.

### `SecretCacheVersion`

Represents a specific version of a cached secret. Stores the result of `GetSecretValue`.

### `SecretCacheHook`

Abstract base class for cache hooks.

| Method | Description |
|--------|-------------|
| `put(obj)` | Transform before storing in cache |
| `get(cached_obj)` | Transform after retrieving from cache |