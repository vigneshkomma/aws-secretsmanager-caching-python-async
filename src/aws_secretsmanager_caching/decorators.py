"""Decorators for use with caching library"""

import inspect
import json
from functools import wraps


class InjectSecretString:
    """Decorator implementing high-level Secrets Manager caching client"""

    def __init__(self, secret_id, cache):
        """
        Constructs a decorator to inject a single non-keyworded argument from a
        cached secret for a given function.

        :type secret_id: str
        :param secret_id: The secret identifier

        :type cache: aws_secretsmanager_caching.SecretCache
        :param cache: Secret cache
        """

        self.cache = cache
        self.secret_id = secret_id

    def __call__(self, func):
        """
        Return a function with cached secret injected as first argument.
        Works with both sync and async functions.

        :type func: object
        :param func: The function for injecting a single non-keyworded argument.

        :return: The function with the injected argument.
        """
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def _async_wrapped(*args, **kwargs):
                secret = await self.cache.get_secret_string(secret_id=self.secret_id)

                # Prevent clobbering self arg in class methods
                if args and hasattr(args[0].__class__, func.__name__):
                    new_args = (args[0], secret) + args[1:]
                else:
                    new_args = (secret,) + args

                return await func(*new_args, **kwargs)

            return _async_wrapped
        else:
            @wraps(func)
            def _wrapped_func(*args, **kwargs):
                raise RuntimeError(
                    "InjectSecretString only supports async functions "
                    "when using the async SecretCache."
                )

            return _wrapped_func


class InjectKeywordedSecretString:
    """Decorator implementing high-level Secrets Manager caching client using JSON-based secrets"""

    def __init__(self, secret_id, cache, **kwargs):
        """
        Construct a decorator to inject a variable list of keyword arguments to a given
        function with resolved values from a cached secret.

        :type kwargs: dict
        :param kwargs: dictionary mapping original keyword argument of wrapped function
            to JSON-encoded secret key

        :type secret_id: str
        :param secret_id: The secret identifier

        :type cache: aws_secretsmanager_caching.SecretCache
        :param cache: Secret cache
        """

        self.cache = cache
        self.kwarg_map = kwargs
        self.secret_id = secret_id

    def __call__(self, func):
        """
        Return a function with injected keyword arguments from a cached secret.
        Works with both sync and async functions.

        :type func: object
        :param func: function for injecting keyword arguments.

        :return: The original function with injected keyword arguments
        """
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def _async_wrapped(*args, **kwargs):
                try:
                    secret_str = await self.cache.get_secret_string(secret_id=self.secret_id)
                    secret = json.loads(secret_str)
                except json.decoder.JSONDecodeError:
                    raise RuntimeError("Cached secret is not valid JSON") from None

                resolved_kwargs = {}
                for orig_kwarg, secret_key in self.kwarg_map.items():
                    try:
                        resolved_kwargs[orig_kwarg] = secret[secret_key]
                    except KeyError:
                        raise RuntimeError(
                            f"Cached secret does not contain key {secret_key}"
                        ) from None

                return await func(*args, **resolved_kwargs, **kwargs)

            return _async_wrapped
        else:

            @wraps(func)
            def _wrapped_func(*args, **kwargs):
                raise RuntimeError(
                    "InjectKeywordedSecretString only supports async functions "
                    "when using the async SecretCache."
                )

            return _wrapped_func