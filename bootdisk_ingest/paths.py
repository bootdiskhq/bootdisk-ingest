from pathlib import Path


def normalize_windows_path(value):
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value.replace("\\", "/")


def normalize_string(value):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def relative_disc_path(folder, filename):
    if not filename:
        return None

    if folder:
        return (Path(folder) / filename).as_posix()

    return Path(filename).as_posix()
