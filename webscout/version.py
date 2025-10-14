import datetime

def _get_version():
    """Generate version based on current date (YYYY.MM.DD format)."""
    now = datetime.datetime.now()
    return f"{now.year}.{now.month}.{now.day}"

__version__ = _get_version()
__prog__ = "webscout"
