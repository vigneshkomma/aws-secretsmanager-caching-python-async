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
Unit test suite for config module
"""
import pytest
from aws_secretsmanager_caching.config import SecretCacheConfig


class TestSecretCacheConfig:

    def test_simple_config(self):
        with pytest.raises(TypeError):
            SecretCacheConfig(no='one')

    def test_config_default_version_stage(self):
        stage = 'nothing'
        config = SecretCacheConfig(default_version_stage=stage)
        assert config.default_version_stage == stage

    def test_default_secret_refresh_interval_typing(self):
        config = SecretCacheConfig()
        assert isinstance(config.secret_refresh_interval, int)

    def test_default_values(self):
        config = SecretCacheConfig()
        assert config.max_cache_size == 1024
        assert config.exception_retry_delay_base == 1
        assert config.exception_retry_growth_factor == 2
        assert config.exception_retry_delay_max == 3600
        assert config.default_version_stage == "AWSCURRENT"
        assert config.secret_refresh_interval == 3600
        assert config.secret_cache_hook is None

    def test_custom_values(self):
        config = SecretCacheConfig(
            max_cache_size=50,
            secret_refresh_interval=300,
            default_version_stage="AWSPREVIOUS",
        )
        assert config.max_cache_size == 50
        assert config.secret_refresh_interval == 300
        assert config.default_version_stage == "AWSPREVIOUS"
        # Non-overridden values stay at defaults
        assert config.exception_retry_delay_base == 1