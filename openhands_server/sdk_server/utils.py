from datetime import UTC, datetime


def utc_now():
    """Return the current time in UTC format (Since datetime.utcnow is deprecated)"""
    return datetime.now(UTC)


def get_all_subclasses(cls):
    """
    Recursively finds and returns all (loaded) subclasses of a given class.
    """
    all_subclasses = set()
    for subclass in cls.__subclasses__():
        all_subclasses.add(subclass)
        all_subclasses.update(get_all_subclasses(subclass))
    return all_subclasses
