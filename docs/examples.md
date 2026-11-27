# Examples

## 1. Web Application (FastAPI)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

cache: SecretCache | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache
    config = SecretCacheConfig(secret_refresh_interval=300)  # 5 min refresh
    cache = await SecretCache.create(config=config)
    yield
    await cache.close()


app = FastAPI(lifespan=lifespan)


@app.get("/config")
async def get_config():
    try:
        api_key = await cache.get_secret_string("api-key")
        db_url = await cache.get_secret_string("database-url")
        return {"api_key_configured": bool(api_key), "db_url": db_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 2. Database Connection Pool

```python
import asyncpg
import asyncio
import json
from aws_secretsmanager_caching import SecretCache


class DatabasePool:
    def __init__(self, cache: SecretCache, secret_id: str):
        self._cache = cache
        self._secret_id = secret_id
        self._pool = None

    async def connect(self):
        secret_str = await self._cache.get_secret_string(self._secret_id)
        creds = json.loads(secret_str)

        self._pool = await asyncpg.create_pool(
            host=creds["host"],
            port=creds["port"],
            user=creds["username"],
            password=creds["password"],
            database=creds["database"],
            min_size=5,
            max_size=20,
        )

    async def fetch(self, query, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def close(self):
        if self._pool:
            await self._pool.close()


async def main():
    cache = await SecretCache.create()
    pool = DatabasePool(cache, "db-credentials")
    await pool.connect()

    rows = await pool.fetch("SELECT * FROM users LIMIT 10")
    print(rows)

    await pool.close()
    await cache.close()

asyncio.run(main())
```

## 3. AWS Lambda Handler

```python
import asyncio
import json
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

# Global cache — reused across Lambda invocations for maximum benefit
cache: SecretCache | None = None


async def get_cache():
    global cache
    if cache is None:
        config = SecretCacheConfig(secret_refresh_interval=3600)
        cache = await SecretCache.create(config=config)
    return cache


async def async_handler(event, context):
    cache = await get_cache()

    secret_id = event.get("secret_id", "my-secret")
    secret = await cache.get_secret_string(secret_id)

    return {
        "statusCode": 200,
        "body": json.dumps({"secret_preview": secret[:20] + "..."}),
    }


def lambda_handler(event, context):
    return asyncio.run(async_handler(event, context))
```

## 4. Celery Async Task

```python
from celery import Celery
import asyncio
from aws_secretsmanager_caching import SecretCache

app = Celery("tasks", broker="redis://localhost")


@app.task(bind=True)
def process_order(self, order_id):
    async def _run():
        cache = await SecretCache.create()
        try:
            api_key = await cache.get_secret_string("payment-api-key")
            # ... process payment with api_key ...
            return {"order_id": order_id, "status": "processed"}
        finally:
            await cache.close()

    return asyncio.run(_run())
```

## 5. Multiple Secrets with Error Handling

```python
import asyncio
from aws_secretsmanager_caching import SecretCache


async def load_all_secrets(secret_ids: list[str]) -> dict[str, str]:
    """Load multiple secrets, returning only the ones that succeed."""
    cache = await SecretCache.create()
    results = {}

    try:
        for secret_id in secret_ids:
            try:
                value = await cache.get_secret_string(secret_id)
                if value is not None:
                    results[secret_id] = value
            except Exception as e:
                print(f"Warning: Could not load '{secret_id}': {e}")
    finally:
        await cache.close()

    return results


async def main():
    required_secrets = ["db-credentials", "api-key", "oauth-token"]
    secrets = await load_all_secrets(required_secrets)
    print(f"Loaded {len(secrets)}/{len(required_secrets)} secrets")

asyncio.run(main())
```

## 6. Custom Cache Hook for Compression

```python
import zlib
import json
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
from aws_secretsmanager_caching.cache import SecretCacheHook


class CompressionHook(SecretCacheHook):
    """Compresses large JSON secrets in memory to reduce RAM usage."""

    def put(self, obj):
        # Compress before caching
        return zlib.compress(json.dumps(obj).encode())

    def get(self, cached_obj):
        # Decompress when retrieving
        return json.loads(zlib.decompress(cached_obj).decode())


async def main():
    config = SecretCacheConfig(secret_cache_hook=CompressionHook())
    cache = await SecretCache.create(config=config)

    # Works transparently
    secret = await cache.get_secret_string("large-json-secret")
    print(secret)

    await cache.close()
```

## 7. Health Check Endpoint

```python
import asyncio
from datetime import datetime
from aws_secretsmanager_caching import SecretCache


async def health_check(cache: SecretCache, test_secret_id: str) -> dict:
    """Check that the cache and AWS Secrets Manager are functioning."""
    status = {"healthy": False, "timestamp": datetime.utcnow().isoformat()}

    try:
        # Try to describe a secret (uses DescribeSecret API)
        start = asyncio.get_event_loop().time()
        success = await cache.refresh_secret_now(test_secret_id)
        elapsed = asyncio.get_event_loop().time() - start

        status["healthy"] = success
        status["latency_ms"] = round(elapsed * 1000, 2)
        status["cache_available"] = True
    except Exception as e:
        status["error"] = str(e)
        status["cache_available"] = False

    return status
```