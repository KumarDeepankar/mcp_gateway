#!/usr/bin/env python3
"""
Wrapper script to run server.py with Python 3.11 compatibility patches
"""
import sys
import os

# Add compatibility patch for Python 3.11 type subscripting
if sys.version_info < (3, 12):
    # Monkey-patch anyio to work around type subscripting issues
    import anyio

    # Store the original function
    _original_create_memory_object_stream = anyio.create_memory_object_stream

    # Create a wrapper that ignores type subscripting
    class _MemoryObjectStreamWrapper:
        def __init__(self, func):
            self._func = func

        def __call__(self, *args, **kwargs):
            return self._func(*args, **kwargs)

        def __getitem__(self, item):
            # Return self to allow subscripting but ignore the type parameter
            return self

    # Apply the patch
    anyio.create_memory_object_stream = _MemoryObjectStreamWrapper(_original_create_memory_object_stream)

    print("Applied Python 3.11 compatibility patches for anyio")

# Now run the actual server
if __name__ == "__main__":
    # Import and run the server module
    import server
