#!/usr/bin/env python3
"""
Test script to verify formatter handles None values correctly
"""
import sys
sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway/mcp_opensearch')

from tools.formatters import ResultFormatter


def test_attendance_stats_with_none():
    """Test that formatter handles None values in attendance stats."""
    print("=" * 60)
    print("Testing Attendance Stats with None Values")
    print("=" * 60)

    formatter = ResultFormatter()

    # Simulate OpenSearch response with None values (no matching documents)
    result_with_none = {
        "aggregations": {
            "attendance_stats": {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "sum": None
            }
        }
    }

    try:
        output = formatter.format_attendance_stats(result_with_none, year=2025, country="Denmark")
        print("✓ Successfully handled None values")
        print(f"\nOutput:\n{output}")
        return True
    except Exception as e:
        print(f"✗ Failed to handle None values: {e}")
        return False


def test_attendance_stats_with_valid_data():
    """Test that formatter still works with valid data."""
    print("\n" + "=" * 60)
    print("Testing Attendance Stats with Valid Data")
    print("=" * 60)

    formatter = ResultFormatter()

    # Simulate OpenSearch response with valid values
    result_with_data = {
        "aggregations": {
            "attendance_stats": {
                "count": 10,
                "min": 50.0,
                "max": 500.0,
                "avg": 250.5,
                "sum": 2505.0
            }
        }
    }

    try:
        output = formatter.format_attendance_stats(result_with_data, year=2023, country=None)
        print("✓ Successfully formatted valid data")
        print(f"\nOutput:\n{output}")

        # Verify the output contains expected values
        if "250.5" in output and "50" in output and "500" in output:
            print("✓ Output contains expected values")
            return True
        else:
            print("✗ Output missing expected values")
            return False
    except Exception as e:
        print(f"✗ Failed to format valid data: {e}")
        return False


def test_year_stats_with_none():
    """Test year stats formatter with None values."""
    print("\n" + "=" * 60)
    print("Testing Year Stats with None Values")
    print("=" * 60)

    formatter = ResultFormatter()

    result_with_none = {
        "aggregations": {
            "by_year": {
                "buckets": [
                    {
                        "key": 2023,
                        "doc_count": 0,
                        "avg_attendance": {"value": None},
                        "total_attendance": {"value": None},
                        "min_attendance": {"value": None},
                        "max_attendance": {"value": None}
                    }
                ]
            }
        }
    }

    try:
        output = formatter.format_year_stats(result_with_none, country=None)
        print("✓ Successfully handled None values in year stats")
        print(f"\nOutput:\n{output}")
        return True
    except Exception as e:
        print(f"✗ Failed to handle None values: {e}")
        return False


def main():
    """Run all formatter tests."""
    print("\n" + "#" * 60)
    print("# Formatter None Value Handling Tests")
    print("#" * 60 + "\n")

    test1 = test_attendance_stats_with_none()
    test2 = test_attendance_stats_with_valid_data()
    test3 = test_year_stats_with_none()

    print("\n" + "#" * 60)
    if test1 and test2 and test3:
        print("# RESULT: ALL TESTS PASSED ✓")
        print("# None value handling fixed successfully!")
        print("#" * 60)
        return 0
    else:
        print("# RESULT: SOME TESTS FAILED ✗")
        print("#" * 60)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
