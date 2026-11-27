# How Caching Works

This document explains the internal architecture and caching strategy of the library.

## Overview

The library implements a **two-level in-memory cache** using LRU (Least Recently Used) eviction policy. Secrets are cached to reduce the number of API calls to AWS Secrets Manager, which reduces latency and cost.

```
┌──────────────────────────────────────────────────────────┐
│                    SecretCache                           │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │          LRUCache (max_size configurable)         │    │
│  │                                                   │    │
│  │  ┌─────────────────┐  ┌─────────────────┐        │    │
│  │  │ SecretCacheItem │  │ SecretCacheItem │  ...   │    │
│  │  │  (secret "foo") │  │  (secret "bar") │        │    │
│  │  └───────┬─────────┘  └────────┬────────┘        │    │
│  │          │                     │                  │    │
│  │          ▼                     ▼                  │    │
│  │  ┌──────────────────────────────────────────┐     │    │
│  │  │    Inner LRUCache (size=10, fixed)       │     │    │
│  │  │  ┌──────────┐ ┌──────────┐              │     │    │
│  │  │  │ Version  │ │ Version  │   ...        │     │    │
│  │  │  │AWSCURRENT│ │AWSPREVIOUS│             │     │    │
│  │  │  └────┬─────┘ └────┬─────┘              │     │    │
│  │  │       │            │                     │     │    │
│  │  │       ▼            ▼                     │     │    │
│  │  │  ┌──────────────────────────┐            │     │    │
│  │  │  │   SecretCacheVersion    │            │     │    │
│  │  │  │   (cached secret value) │            │     │    │
│  │  │  └──────────────────────────┘            │     │    │
│  │  └──────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │           aiobotocore Client                     │    │
│  │  DescribeSecret  │  GetSecretValue               │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## Level 1: Secret Cache (SecretCacheItem)

When you call `get_secret_string("my-secret")`:

1. The `SecretCache` looks up `"my-secret"` in the top-level `LRUCache`.
2. If not found, a new `SecretCacheItem` is created and stored.
3. `SecretCacheItem` calls `DescribeSecret` to get metadata (version IDs, stages, ARN, etc.).
4. The result is cached, and a **randomized refresh time** is set (between 50% and 100% of `secret_refresh_interval`).

## Level 2: Version Cache (SecretCacheVersion)

When a specific version stage is requested (e.g., `AWSCURRENT`):

1. `SecretCacheItem` looks up which version ID corresponds to the requested stage (from the `DescribeSecret` result).
2. It checks its inner `LRUCache` (fixed size of 10) for that version ID.
3. If not found, a new `SecretCacheVersion` is created.
4. `SecretCacheVersion` calls `GetSecretValue` for that specific version.
5. The result (containing `SecretString` or `SecretBinary`) is cached.

## Refresh Strategy

### Automatic Refresh

- Each `SecretCacheItem` tracks a `_next_refresh_time`.
- On access, if the current time is past `_next_refresh_time`, the metadata is refreshed via `DescribeSecret`.
- The next refresh time is randomized: `now + random(interval/2, interval)` to spread out refreshes across many secrets.

### Retry with Exponential Backoff

If a refresh fails:

1. The exception is stored.
2. A retry delay is calculated: `base * growth_factor^attempt_count`
3. The delay is capped at `exception_retry_delay_max`.
4. On the next access, if the retry time has passed, another attempt is made.
5. If all retries fail, the exception is propagated to the caller.

### Force Refresh

`refresh_secret_now()` forces an immediate refresh:

1. Waits for any pending retry backoff (capped at `FORCE_REFRESH_MAX_SLEEP = 10s`).
2. Adds jitter (2.5s–5s) to avoid thundering herd.
3. Sets `_refresh_needed = True` and triggers a refresh.

## LRU Eviction

### Top-Level Cache (SecretCacheItem)

- Configurable `max_cache_size` (default: 1024).
- When full, the least-recently-accessed secret is evicted.
- Eviction removes both the metadata and all cached versions of that secret.

### Inner Version Cache

- Fixed size of 10 per secret item.
- When full, the least-recently-accessed version is evicted.
- This prevents unbounded growth from secrets with many versions.

## Thread Safety

All cache operations are protected by `asyncio.Lock()`:

- **LRUCache** — a single lock protects the entire cache and linked list.
- **SecretCacheItem / SecretCacheVersion** — each has its own lock for refresh logic.

This ensures safe concurrent access from multiple coroutines.

## Cache Hook Integration

A `SecretCacheHook` can be provided to transform values before they enter or after they leave the cache:

```python
class MyHook(SecretCacheHook):
    def put(self, obj):
        return encrypt(obj)     # Transform before storing

    def get(self, cached_obj):
        return decrypt(cached_obj)  # Transform after retrieving
```

The hook is applied at the `SecretCacheObject` level, affecting both metadata (`DescribeSecret` results) and version values (`GetSecretValue` results).

## Memory Considerations

| Component | Memory per entry |
|-----------|-----------------|
| SecretCacheItem (metadata) | ~1-2 KB |
| SecretCacheVersion (value) | Size of the secret value |
| LRU linked list node | ~200 bytes |

**Example:** 100 secrets, each with 1 version of 1 KB:
- ~100 × (2 KB + 200 bytes) + 100 × (1 KB + 200 bytes) ≈ **350 KB**

For most applications, the default `max_cache_size` of 1024 is more than sufficient.