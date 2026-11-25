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
Unit test suite for decorators module
"""
import json
import pytest
from unittest.mock import AsyncMock

from aws_secretsmanager_caching.decorators import InjectKeywordedSecretString, InjectSecretString
from aws_secretsmanager_caching.secret_cache import SecretCache


pytestmark = [pytest.mark.unit, pytest.mark.local]


def _make_mock_client(version_response=None):
    client = AsyncMock()
    client.describe_secret = AsyncMock(return_value={
        "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test",
        "Name": "test",
        "VersionIdsToStages": {
            '01234567890123456789012345678901': ['AWSCURRENT']
        }
    })
    client.get_secret_value = AsyncMock(return_value=version_response or {})
    return client


@pytest.mark.asyncio
class TestInjectKeywordedSecretStringDecorator:

    async def test_valid_json(self):
        secret = {
            'username': 'secret_username',
            'password': 'secret_password'
        }
        secret_string = json.dumps(secret)
        version_response = {'SecretString': secret_string}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectKeywordedSecretString(
            secret_id='test', cache=cache,
            func_username='username', func_password='password'
        )
        async def function_to_be_decorated(func_username, func_password, keyworded_argument='foo'):
            assert func_username == secret['username']
            assert func_password == secret['password']
            assert keyworded_argument == 'foo'
            return 'OK'

        result = await function_to_be_decorated()
        assert result == 'OK'

    async def test_valid_json_with_mixed_args(self):
        secret = {
            'username': 'secret_username',
            'password': 'secret_password'
        }
        secret_string = json.dumps(secret)
        version_response = {'SecretString': secret_string}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectKeywordedSecretString(
            secret_id='test', cache=cache,
            arg2='username', arg3='password'
        )
        async def function_to_be_decorated(arg1, arg2, arg3, arg4='bar'):
            assert arg1 == 'foo'
            assert arg2 == secret['username']
            assert arg3 == secret['password']
            assert arg4 == 'bar'

        await function_to_be_decorated('foo')

    async def test_valid_json_with_no_secret_kwarg(self):
        secret = {
            'username': 'secret_username',
            'password': 'secret_password'
        }
        secret_string = json.dumps(secret)
        version_response = {'SecretString': secret_string}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectKeywordedSecretString(
            'test', cache=cache,
            func_username='username', func_password='password'
        )
        async def function_to_be_decorated(func_username, func_password, keyworded_argument='foo'):
            assert func_username == secret['username']
            assert func_password == secret['password']
            assert keyworded_argument == 'foo'

        await function_to_be_decorated()

    async def test_invalid_json(self):
        secret = 'not json'
        version_response = {'SecretString': secret}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectKeywordedSecretString(
            secret_id='test', cache=cache,
            func_username='username', func_passsword='password'
        )
        async def function_to_be_decorated(func_username, func_password, keyworded_argument='foo'):
            return

        with pytest.raises(RuntimeError):
            await function_to_be_decorated()

    async def test_missing_key(self):
        secret = {'username': 'secret_username'}
        secret_string = json.dumps(secret)
        version_response = {'SecretString': secret_string}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectKeywordedSecretString(
            secret_id='test', cache=cache,
            func_username='username', func_passsword='password'
        )
        async def function_to_be_decorated(func_username, func_password, keyworded_argument='foo'):
            return

        with pytest.raises(RuntimeError):
            await function_to_be_decorated()


@pytest.mark.asyncio
class TestInjectSecretStringDecorator:

    async def test_string(self):
        secret = 'not json'
        version_response = {'SecretString': secret}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectSecretString('test', cache)
        async def function_to_be_decorated(arg1, arg2, arg3):
            assert arg1 == secret
            assert arg2 == 'foo'
            assert arg3 == 'bar'
            return 'OK'

        result = await function_to_be_decorated('foo', 'bar')
        assert result == 'OK'

    async def test_string_with_additional_kwargs(self):
        secret = 'not json'
        version_response = {'SecretString': secret}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        @InjectSecretString('test', cache)
        async def function_to_be_decorated(arg1, arg2, arg3):
            assert arg1 == secret
            assert arg2 == 'foo'
            assert arg3 == 'bar'

        await function_to_be_decorated(arg2='foo', arg3='bar')

    async def test_string_with_class_method(self):
        secret = 'not json'
        version_response = {'SecretString': secret}

        client = _make_mock_client(version_response=version_response)
        cache = await SecretCache.create(client=client)

        class TestClass:
            @InjectSecretString('test', cache)
            async def class_method(self, arg1, arg2, arg3):
                assert arg1 == secret
                assert arg2 == 'foo'
                assert arg3 == 'bar'

        t = TestClass()
        await t.class_method(arg2="foo", arg3="bar")