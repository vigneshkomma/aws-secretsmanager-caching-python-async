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
Integration tests for aws_secretsmanager_caching.
These tests require actual AWS credentials and a running Secrets Manager endpoint.
"""
import inspect
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FIXTURE_PREFIX = 'python_caching_integ_test_'
UUID_SUFFIX = uuid4().hex


skip_if_no_aws = pytest.mark.skipif(
    True,  # Replaced below after detecting AWS availability
    reason="AWS credentials not available"
)

# Override the skip condition dynamically
import os
_has_aws = bool(
    os.environ.get('AWS_ACCESS_KEY_ID')
    or os.environ.get('AWS_PROFILE')
    or os.environ.get('AWS_DEFAULT_REGION')
    or os.environ.get('AWS_REGION')
    or os.path.exists(os.path.expanduser('~/.aws/credentials'))
    or os.path.exists(os.path.expanduser('~/.aws/config'))
)
skip_if_no_aws = pytest.mark.skipif(
    not _has_aws,
    reason="AWS credentials not available — integration tests require real AWS infrastructure"
)


@skip_if_no_aws
@pytest.mark.asyncio
class TestAwsSecretsManagerCachingInteg:

    @pytest.fixture(scope='class')
    async def client(self):
        """Create an aiobotocore secretsmanager client."""
        import aiobotocore.session
        session = aiobotocore.session.AioSession()
        async with session.create_client('secretsmanager') as cli:
            yield cli

    @pytest.fixture(scope='class', autouse=True)
    async def pre_test_cleanup(self, client):
        """Clean up stale test secrets before running integration tests."""
        from botocore.exceptions import ClientError
        logger.info('Starting cleanup operation of previous test secrets...')
        old_secrets = []
        two_days_ago = datetime.now() - timedelta(days=2)

        paginator = client.get_paginator('list_secrets')
        paginator_config = {'PageSize': 10, 'StartingToken': None}

        try:
            async for page in paginator.paginate(PaginationConfig=paginator_config):
                for secret in page['SecretList']:
                    if (
                        secret['Name'].startswith(FIXTURE_PREFIX)
                        and secret['LastChangedDate'] > two_days_ago
                        and secret['LastAccessedDate'] > two_days_ago
                    ):
                        old_secrets.append(secret)
                if 'NextToken' in page:
                    paginator_config['StartingToken'] = page['NextToken']
                else:
                    break
        except ClientError as e:
            logger.error(f"ClientError while listing secrets: {e.response['Error']['Code']}")

        if not old_secrets:
            logger.info("No previously configured test secrets found")
        else:
            for secret in old_secrets:
                logger.info(f"Deleting stale secret: {secret['Name']}")
                try:
                    await client.delete_secret(SecretId=secret['Name'])
                except ClientError as e:
                    logger.error(
                        f"Error deleting secret {secret['Name']}: {e.response['Error']['Code']}"
                    )
        yield

    @pytest.fixture
    async def secret_string(self, request, client):
        """Create a test secret with a string value."""
        from botocore.exceptions import ClientError
        name = f"{FIXTURE_PREFIX}{request.function.__name__}{UUID_SUFFIX}"
        secret = await client.create_secret(Name=name, SecretString='test')
        yield secret
        try:
            await client.delete_secret(SecretId=secret['ARN'], ForceDeleteWithoutRecovery=True)
        except ClientError:
            pass

    @pytest.fixture
    async def secret_string_stage(self, request, client):
        """Create a test secret with multiple versions for stage testing."""
        from botocore.exceptions import ClientError
        name = f"{FIXTURE_PREFIX}{request.function.__name__}{UUID_SUFFIX}"
        secret = await client.create_secret(Name=name, SecretString='test')
        await client.put_secret_value(
            SecretId=secret['ARN'], SecretString='test2', VersionStages=['AWSCURRENT']
        )
        describe_result = await client.describe_secret(SecretId=secret['ARN'])
        yield describe_result
        try:
            await client.delete_secret(SecretId=secret['ARN'], ForceDeleteWithoutRecovery=True)
        except ClientError:
            pass

    @pytest.fixture
    async def secret_binary(self, request, client):
        """Create a test secret with a binary value."""
        from botocore.exceptions import ClientError
        name = f"{FIXTURE_PREFIX}{request.function.__name__}{UUID_SUFFIX}"
        secret = await client.create_secret(Name=name, SecretBinary=b'01010101')
        yield secret
        try:
            await client.delete_secret(SecretId=secret['ARN'], ForceDeleteWithoutRecovery=True)
        except ClientError:
            pass

    async def test_get_secret_string(self, client, secret_string):
        cache = await SecretCache.create(client=client)
        secret_value = await client.get_secret_value(SecretId=secret_string['ARN'])
        secret = secret_value['SecretString']
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        for _ in range(10):
            result = await cache.get_secret_string(name)
            assert result == secret
        await cache.close()

    async def test_get_secret_string_refresh(self, client, secret_string):
        cache = await SecretCache.create(
            config=SecretCacheConfig(secret_refresh_interval=1), client=client
        )
        secret_value = await client.get_secret_value(SecretId=secret_string['ARN'])
        secret = secret_value['SecretString']
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        for _ in range(10):
            result = await cache.get_secret_string(name)
            assert result == secret

        await client.put_secret_value(
            SecretId=secret_string['ARN'], SecretString='test2', VersionStages=['AWSCURRENT']
        )
        import asyncio
        await asyncio.sleep(2)

        secret_value = await client.get_secret_value(SecretId=secret_string['ARN'])
        secret = secret_value['SecretString']
        for _ in range(10):
            result = await cache.get_secret_string(name)
            assert result == secret
        await cache.close()

    async def test_get_secret_binary_empty(self, client, secret_string):
        cache = await SecretCache.create(client=client)
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        result = await cache.get_secret_binary(name)
        assert result is None
        await cache.close()

    async def test_get_secret_string_stage(self, client, secret_string_stage):
        cache = await SecretCache.create(client=client)
        secret_value = await client.get_secret_value(
            SecretId=secret_string_stage['ARN'], VersionStage='AWSPREVIOUS'
        )
        secret = secret_value['SecretString']
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        for _ in range(10):
            result = await cache.get_secret_string(name, 'AWSPREVIOUS')
            assert result == secret
        await cache.close()

    async def test_get_secret_binary(self, client, secret_binary):
        cache = await SecretCache.create(client=client)
        secret_value = await client.get_secret_value(SecretId=secret_binary['ARN'])
        secret = secret_value['SecretBinary']
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        for _ in range(10):
            result = await cache.get_secret_binary(name)
            assert result == secret
        await cache.close()

    async def test_get_secret_string_empty(self, client, secret_binary):
        cache = await SecretCache.create(client=client)
        name = f"{FIXTURE_PREFIX}{inspect.stack()[0][3]}{UUID_SUFFIX}"
        result = await cache.get_secret_string(name)
        assert result is None
        await cache.close()