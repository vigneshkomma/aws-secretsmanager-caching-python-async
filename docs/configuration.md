# Configuration Reference

## `SecretCacheConfig`

All configuration is done via the `SecretCacheConfig` class, which accepts keyword arguments for any option you want to override. Options not specified use their defaults.

### Quick Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_cache_size` | `int` | `1024` | Maximum number of secrets to cache |
| `secret_refresh_interval` | `int` | `3600` | Seconds between automatic refreshes |
| `exception_retry_delay_base` | `int` | `1` | Initial retry delay in seconds |
| `exception_retry_growth_factor` | `int` | `2` | Exponential growth factor for retry delays |
| `exception_retry_delay_max` | `int` | `3600` | Maximum retry delay in seconds |
| `default_version_stage` | `str` | `"AWSCURRENT"` | Default version stage to request |
| `secret_cache_hook` | `SecretCacheHook` | `None` | Custom hook for transforming cached secrets |

### Detailed Descriptions

#### `max_cache_size`
- **Type:** `int`
- **Default:** `1024`
- **Description:** The maximum number of secrets to hold in the in-memory LRU cache. When the cache is full and a new secret is requested, the least-recently-used secret is evicted.
- **When to adjust:** Increase if your application uses more than 1024 distinct secrets. Decrease to reduce memory footprint.

#### `secret_refresh_interval`
- **Type:** `int`
- **Default:** `3600` (1 hour)
- **Description:** The number of seconds between automatic refreshes of cached secret metadata. The actual refresh time is randomized between 50% and 100% of this value to spread out refresh requests.
- **When to adjust:** Decrease if your secrets rotate frequently. Increase to reduce API calls and cost.

#### `exception_retry_delay_base`
- **Type:** `int`
- **Default:** `1`
- **Description:** The base number of seconds to wait before retrying a failed request. This is the starting delay before exponential backoff is applied.

#### `exception_retry_growth_factor`
- **Type:** `int`
- **Default:** `2`
- **Description:** The multiplier applied to the retry delay on each successive failure. With the default value, delays progress as: 1s, 2s, 4s, 8s, 16s, etc.

#### `exception_retry_delay_max`
- **Type:** `int`
- **Default:** `3600` (1 hour)
- **Description:** The maximum number of seconds to wait between retry attempts. This caps the exponential backoff.

#### `default_version_stage`
- **Type:** `str`
- **Default:** `"AWSCURRENT"`
- **Description:** The default version stage used when no `version_stage` is specified in `get_secret_string()` or `get_secret_binary()`.
- **Common values:** `"AWSCURRENT"`, `"AWSPREVIOUS"`, or any custom stage label.

#### `secret_cache_hook`
- **Type:** `SecretCacheHook` or `None`
- **Default:** `None`
- **Description:** An implementation of the `SecretCacheHook` abstract class. When set, every secret value passes through the hook's `put()` method before being stored in the cache, and through `get()` when retrieved. This can be used for encryption/decryption or data transformation.

---

## Configuration Examples

### Minimal (all defaults)

```python
config = SecretCacheConfig()
cache = await SecretCache.create(config=config)
```

### High-traffic, frequently rotating secrets

```python
config = SecretCacheConfig(
    max_cache_size=500,
    secret_refresh_interval=120,       # Refresh every 2 minutes
    exception_retry_delay_base=1,
    exception_retry_growth_factor=2,
    exception_retry_delay_max=120,     # Max 2 minute retry
)
```

### Low-traffic, cost-conscious

```python
config = SecretCacheConfig(
    max_cache_size=50,
    secret_refresh_interval=86400,     # Refresh once per day
    exception_retry_delay_base=5,
    exception_retry_growth_factor=2,
    exception_retry_delay_max=600,     # Max 10 minute retry
)
```

### With encryption hook

```python
from aws_secretsmanager_caching.cache import SecretCacheHook

class EncryptionHook(SecretCacheHook):
    def put(self, obj):
        return encrypt(obj)   # your encryption logic

    def get(self, cached_obj):
        return decrypt(cached_obj)  # your decryption logic

config = SecretCacheConfig(
    secret_cache_hook=EncryptionHook(),
)
```