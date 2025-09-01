#!/usr/bin/env python3
"""
Test Environment Verification Script for Paperless-NGX Telegram Concierge

This script helps diagnose and fix async test configuration issues.
Run this if pytest fails with "async def functions are not natively supported".
"""

import os
import subprocess
import sys

# ruff: noqa: T201

# Constants
PYTEST_MIN_MAJOR_VERSION = 6
PYTEST_MIN_MINOR_VERSION = 1


def check_pytest_asyncio():
    """Check if pytest-asyncio is properly installed."""
    print("🔍 Checking pytest-asyncio installation...")

    try:
        import pytest_asyncio

        print(f"✅ pytest-asyncio {pytest_asyncio.__version__} is installed")
        return True
    except ImportError:
        print("❌ pytest-asyncio is not installed")
        print("🔧 Fix: pip install pytest-asyncio")
        return False


def check_pytest_version():
    """Check pytest version compatibility."""
    print("\n🔍 Checking pytest version...")

    try:
        import pytest

        print(f"✅ pytest {pytest.__version__} is installed")

        # Check if version supports asyncio_mode
        version_parts = pytest.__version__.split(".")
        major, minor = int(version_parts[0]), int(version_parts[1])

        if major >= PYTEST_MIN_MAJOR_VERSION or (
            major == PYTEST_MIN_MAJOR_VERSION and minor >= PYTEST_MIN_MINOR_VERSION
        ):
            print("✅ pytest version supports asyncio_mode = 'auto'")
            return True
        else:
            print("⚠️  pytest version may not support asyncio_mode = 'auto'")
            print("🔧 Consider upgrading: pip install --upgrade pytest")
            return False

    except ImportError:
        print("❌ pytest is not installed")
        print("🔧 Fix: pip install pytest")
        return False


def check_configuration_files():
    """Check pytest configuration files."""
    print("\n🔍 Checking pytest configuration...")

    issues_found = []

    # Check if pytest.ini exists (potential conflict)
    if os.path.exists("pytest.ini"):
        print("⚠️  Found pytest.ini - this may conflict with pyproject.toml")
        issues_found.append("Remove pytest.ini to avoid conflicts")

    # Check pyproject.toml configuration
    if os.path.exists("pyproject.toml"):
        try:
            with open("pyproject.toml") as f:
                content = f.read()

            if "asyncio_mode" in content:
                if 'asyncio_mode = "auto"' in content:
                    print("✅ pyproject.toml has asyncio_mode = 'auto'")
                else:
                    print("⚠️  asyncio_mode found but not set to 'auto'")
                    issues_found.append("Set asyncio_mode = 'auto' in pyproject.toml")
            else:
                print("❌ asyncio_mode not found in pyproject.toml")
                issues_found.append(
                    "Add asyncio_mode = 'auto' to [tool.pytest.ini_options]"
                )

        except (OSError, ValueError) as e:
            print(f"❌ Error reading pyproject.toml: {e}")
            issues_found.append("Fix pyproject.toml syntax errors")
    else:
        print("❌ pyproject.toml not found")
        issues_found.append("Create pyproject.toml with pytest configuration")

    return len(issues_found) == 0, issues_found


def test_simple_async_function():
    """Test if async functions work in pytest."""
    print("\n🔍 Testing async function support...")

    # Create a simple test file
    test_content = '''
import pytest

@pytest.mark.asyncio
async def test_simple_async():
    """Simple async test."""
    import asyncio
    await asyncio.sleep(0.01)
    assert True

async def test_auto_async():
    """Test without explicit @pytest.mark.asyncio (requires asyncio_mode=auto)."""
    import asyncio
    await asyncio.sleep(0.01)
    assert True
'''

    try:
        # Write test file
        with open("temp_async_test.py", "w") as f:
            f.write(test_content)

        # Run the test
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "temp_async_test.py", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Clean up
        os.remove("temp_async_test.py")

        if result.returncode == 0:
            print("✅ Async tests are working correctly")
            return True
        else:
            print("❌ Async tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False

    except (OSError, subprocess.SubprocessError) as e:
        # Clean up on error
        if os.path.exists("temp_async_test.py"):
            os.remove("temp_async_test.py")
        print(f"❌ Error testing async functions: {e}")
        return False


def print_diagnosis_summary(issues):
    """Print summary and fixes for identified issues."""
    print("\n" + "=" * 60)
    if not issues:
        print("🎉 ASYNC TEST ENVIRONMENT IS PROPERLY CONFIGURED!")
        print("You can run tests with: pytest tests/ -v")
    else:
        print("🔧 FIXES NEEDED FOR ASYNC TESTS:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")

        print("\n📋 Quick Fix Commands:")
        print("pip install pytest-asyncio")
        print("# Ensure pyproject.toml has:")
        print("#   [tool.pytest.ini_options]")
        print('#   asyncio_mode = "auto"')

    print("=" * 60)


def main():
    """Run all verification checks."""
    print("🧪 Pytest Async Environment Verification")
    print("=" * 50)

    issues = []

    # Run all checks
    if not check_pytest_asyncio():
        issues.append("Install pytest-asyncio: pip install pytest-asyncio")

    if not check_pytest_version():
        issues.append("Upgrade pytest: pip install --upgrade pytest")

    config_ok, config_issues = check_configuration_files()
    if not config_ok:
        issues.extend(config_issues)

    if not issues:  # Only test async if basic setup is correct
        if not test_simple_async_function():
            issues.append("Fix async test execution issues")

    print_diagnosis_summary(issues)

    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
