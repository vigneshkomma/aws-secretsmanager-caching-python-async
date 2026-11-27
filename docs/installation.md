# Installation Guide

## Prerequisites

- **Python 3.8+** — The library requires Python 3.8 or later.
- **AWS Credentials** — Configured via environment variables, AWS CLI, IAM role, or another standard method. The `aiobotocore` client uses the same credential chain as `boto3`.

## Installing from Source

Since this library is not yet published on PyPI, install it directly from the source directory:

```bash
# Clone the repository
git clone https://github.com/your-org/aws-secretsmanager-caching-python-async.git
cd aws-secretsmanager-caching-python-async

# Install in editable mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

## Dependencies

The only runtime dependency is `aiobotocore>=2.5.0`, which is installed automatically when you install this package.

### Development Dependencies

```bash
pip install -r dev-requirements.txt
```

This installs:

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.0 | Test runner |
| `pytest-asyncio` | >=0.21.0 | Async test support |

## Verifying the Installation

```python
import asyncio
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

async def test():
    cache = await SecretCache.create()
    print(f"SecretCache v{cache.__version__} installed successfully!")
    await cache.close()

asyncio.run(test())
```

## AWS Credentials Setup

The `aiobotocore` client uses the standard AWS credential chain:

### Environment Variables

```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

### AWS CLI Configuration

```bash
aws configure
```

### IAM Role (EC2, ECS, Lambda)

Ensure the IAM role has the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:DescribeSecret",
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:*"
        }
    ]
}
```

For a production environment, scope the `Resource` to the specific secrets your application needs.