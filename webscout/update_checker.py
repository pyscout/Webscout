try:
    from importlib.metadata import version, PackageNotFoundError
    def get_package_version(package_name: str) -> str:
        return version(package_name)
except ImportError:
    # Fallback for Python < 3.8
    from pkg_resources import get_distribution, DistributionNotFound as PackageNotFoundError
    def get_package_version(package_name: str) -> str:
        return get_distribution(package_name).version
"""
Webscout Update Checker
>>> from webscout import check_for_updates
>>> result = check_for_updates()
>>> print(result)
'New Webscout version available: 2.0.0 - Update with: pip install --upgrade webscout'
"""

from typing import Optional, Dict, Any, Literal

import requests
from packaging import version

# Constants
PYPI_URL = "https://pypi.org/pypi/webscout/json"

# Create a session for HTTP requests
session = requests.Session()

# Version comparison result type
VersionCompareResult = Literal[-1, 0, 1]

def get_installed_version() -> Optional[str]:
    """Get the currently installed version of webscout.

    Returns:
        Optional[str]: The installed version string or None if not found

    Examples:
        >>> version = get_installed_version()
        >>> print(version)
        '1.2.3'
    """
    try:
        return get_package_version('webscout')
    except PackageNotFoundError:
        return None

def get_pypi_version() -> Optional[str]:
    """Get the latest version available on PyPI.

    Returns:
        Optional[str]: The latest version string or None if retrieval failed

    Examples:
        >>> latest = get_pypi_version()
        >>> print(latest)
        '2.0.0'
    """
    try:
        response = session.get(PYPI_URL, timeout=10)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        return data['info']['version']
    except (requests.RequestException, KeyError, ValueError):
        return None

def version_compare(v1: str, v2: str) -> VersionCompareResult:
    """Compare two version strings.

    Args:
        v1: First version string
        v2: Second version string to compare with

    Returns:
        VersionCompareResult: -1 if v1 < v2, 1 if v1 > v2, 0 if equal

    Examples:
        >>> version_compare('1.0.0', '2.0.0')
        -1
    """
    try:
        version1 = version.parse(v1)
        version2 = version.parse(v2)
        if version1 < version2:
            return -1
        if version1 > version2:
            return 1
        return 0
    except version.InvalidVersion:
        return 0

def get_update_message(installed: str, latest: str) -> Optional[str]:
    """Generate appropriate update message based on version comparison.

    Args:
        installed: Currently installed version
        latest: Latest available version

    Returns:
        Optional[str]: Update message if needed, None if already on latest version

    Examples:
        >>> get_update_message('1.0.0', '2.0.0')
        'New Webscout version available: 2.0.0 - Update with: pip install --upgrade webscout'
    """
    comparison_result = version_compare(installed, latest)
    if comparison_result < 0:
        return f"New Webscout version available: {latest} - Update with: pip install --upgrade webscout"
    elif comparison_result > 0:
        return f"You're running a development version ({installed}) ahead of latest release ({latest})"
    return None  # Already on the latest version

def check_for_updates() -> Optional[str]:
    """Check if a newer version of Webscout is available.

    Returns:
        Optional[str]: Update message if newer version exists, None otherwise

    Examples:
        >>> result = check_for_updates()
        >>> print(result)
        'New Webscout version available: 2.0.0 - Update with: pip install --upgrade webscout'
    """
    installed_version = get_installed_version()
    if not installed_version:
        return None

    latest_version = get_pypi_version()
    if not latest_version:
        return None

    return get_update_message(installed_version, latest_version)

if __name__ == "__main__":
    try:
        update_message = check_for_updates()
        if update_message:
            print(update_message)
    except KeyboardInterrupt:
        print("Update check canceled")
    except Exception as e:
        print(f"Update check failed: {str(e)}")