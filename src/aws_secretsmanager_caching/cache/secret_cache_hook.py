from abc import ABCMeta, abstractmethod

class SecretCacheHook:
    """Interface to hook the local in-memory cache.  This interface will allow
    for clients to perform actions on the items being stored in the in-memory
    cache.  One example would be encrypting/decrypting items stored in the
    in-memory cache."""

    __metaclass__ = ABCMeta

    def __init__(self):
        """Construct the secret cache hook."""

    @abstractmethod
    def put(self, obj):
        """Prepare the object for storing in the cache"""

    @abstractmethod
    def get(self, cached_obj):
        """Derive the object from the cached object."""