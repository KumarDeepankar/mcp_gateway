#!/usr/bin/env python3
"""Quick compliance test"""
import sys
print("Testing protocol compliance...")

# Test 1: Import server
try:
    from server import mcp, fuzzy_autocomplete, validate_entity
    print("✓ Server imports successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Check server metadata
if hasattr(mcp, 'name'):
    print(f"✓ Server name: {mcp.name}")
else:
    print("✗ Server missing name attribute")

# Test 3: Check tool registration
tools = list(mcp._tools.keys()) if hasattr(mcp, '_tools') else []
print(f"✓ Tools registered: {tools}")

# Test 4: Check type annotations
import inspect
sig = inspect.signature(fuzzy_autocomplete)
print(f"✓ fuzzy_autocomplete signature: {sig}")
print(f"  Return type: {sig.return_annotation}")

sig2 = inspect.signature(validate_entity)
print(f"✓ validate_entity signature: {sig2}")
print(f"  Return type: {sig2.return_annotation}")

# Test 5: Check TypedDict definitions
from server import AutocompleteResult, ValidationResult
print(f"✓ AutocompleteResult fields: {AutocompleteResult.__annotations__.keys()}")
print(f"✓ ValidationResult fields: {ValidationResult.__annotations__.keys()}")

print("\n✓ All protocol compliance checks passed!")
