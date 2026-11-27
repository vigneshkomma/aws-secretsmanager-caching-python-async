# Decorators

The library provides two decorators that inject cached secrets directly into your async functions. Both are available from the top-level package:

```python
from aws_secretsmanager_caching import InjectSecretString, InjectKeywordedSecretString
```

> **Important:** These decorators only work with `async` functions. Wrapping a sync function raises a `RuntimeError`, since the underlying `SecretCache` is async-only.

---

## `InjectSecretString`

Injects the **entire secret string** as the first positional argument of the decorated function.

### Signature

```python
InjectSecretString(secret_id: str, cache: SecretCache)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_id` | `str` | The name or ARN of the secret to inject |
| `cache` | `SecretCache` | An initialized `SecretCache` instance |

### Behavior

- The secret string is fetched from the cache and prepended to the function's positional arguments.
- For **class methods**, the `self` (or `cls`) argument is preserved — the secret is injected as the second argument (after `self`).

### Examples

#### Basic Usage

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, InjectSecretString

async def main():
    cache = await SecretCache.create()

    @InjectSecretString("my-api-key", cache)
    async def call_api(api_key: str):
        print(f"Calling API with key: {api_key}")

    await call_api()
    await cache.close()

asyncio.run(main())
```

#### With Additional Arguments

```python
@InjectSecretString("my-secret", cache)
async def process(secret: str, user_id: str, action: str):
    print(f"Processing {action} for user {user_id} with secret: {secret[:8]}...")

await process(user_id="user-123", action="read")
```

#### In a Class Method

```python
class DatabaseClient:
    def __init__(self, cache):
        self.cache = cache

    @InjectSecretString("db-password", cache)
    async def connect(self, password: str, host: str, port: int):
        print(f"Connecting to {host}:{port} with password {password}")
```

> **Note:** When used in a class, pass the `cache` as an external reference — the decorator captures it at decoration time, not from `self`.

---

## `InjectKeywordedSecretString`

Injects specific fields from a **JSON-formatted secret** as keyword arguments.

### Signature

```python
InjectKeywordedSecretString(secret_id: str, cache: SecretCache, **kwarg_map)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_id` | `str` | The name or ARN of the secret |
| `cache` | `SecretCache` | An initialized `SecretCache` instance |
| `**kwarg_map` | `dict` | Maps function parameter names to JSON secret keys |

### Behavior

1. Fetches the secret string from the cache.
2. Parses it as JSON.
3. For each entry in `kwarg_map`, looks up the JSON key and assigns its value to the corresponding function parameter.
4. Calls the decorated function with those keyword arguments.

### Example

Given a secret `"db-credentials"` with JSON content:

```json
{
    "username": "admin",
    "password": "hunter2",
    "host": "db.example.com",
    "port": 5432
}
```

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, InjectKeywordedSecretString

async def main():
    cache = await SecretCache.create()

    @InjectKeywordedSecretString(
        "db-credentials", cache,
        username="username",
        password="password",
        host="host",
        port="port",
    )
    async def connect(username: str, password: str, host: str, port: int):
        print(f"Connecting to {host}:{port} as {username}")

    await connect()
    await cache.close()

asyncio.run(main())
```

#### Partial Injection

You can inject only some fields and pass others directly:

```python
@InjectKeywordedSecretString(
    "db-credentials", cache,
    username="username",
    password="password",
)
async def connect(username: str, password: str, host: str):
    print(f"Connecting to {host} as {username}")

await connect(host="db.example.com")  # host is passed directly
```

### Error Handling

- If the secret is not valid JSON, a `RuntimeError("Cached secret is not valid JSON")` is raised.
- If a JSON key specified in `kwarg_map` does not exist in the secret, a `RuntimeError("Cached secret does not contain key <key>")` is raised.

---

## Best Practices

1. **Create the cache once** — Instantiate a single `SecretCache` and reuse it across your application. The decorators capture the cache reference at decoration time.

2. **Avoid hot reloading** — Decorators are evaluated at function definition time, so changing the cache or secret ID requires a restart.

3. **Use `InjectKeywordedSecretString` for structured secrets** — It makes the dependency on specific secret fields explicit in the function signature.

4. **Don't use decorators for secrets that change per-invocation** — If you need to look up different secrets per call, use the cache methods directly instead.