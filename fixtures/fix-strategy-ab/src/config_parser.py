"""Parse key=value config files. Bug: does not handle values containing '='."""

from pathlib import Path


def parse_config(text: str) -> dict[str, str]:
    """Parse lines of 'key=value' into a dict. Skips comments (#) and blanks."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # BUG: split("=") splits on ALL '=' chars; "db_url=postgres://host?opt=1"
        # yields key="db_url", value="postgres://host?opt" and drops "1"
        parts = line.split("=")
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


def load_config(path: Path) -> dict[str, str]:
    """Load config from a file path."""
    return parse_config(path.read_text())
