"""CSV export utility. Bug: header row is written on every call, not just the first."""

from pathlib import Path


class CSVWriter:
    """Append rows to a CSV file."""

    def __init__(self, path: Path, columns: list[str]):
        self.path = path
        self.columns = columns
        # BUG: _header_written is never set to True, so header re-emits every write_row
        self._header_written = False

    def write_row(self, row: dict[str, str]) -> None:
        """Append a single row. Writes header if file is new."""
        with open(self.path, "a") as f:
            if not self._header_written:
                f.write(",".join(self.columns) + "\n")
                # BUG: missing self._header_written = True
            values = [row.get(col, "") for col in self.columns]
            f.write(",".join(values) + "\n")

    def read_all(self) -> list[dict[str, str]]:
        """Read all rows back as dicts."""
        lines = self.path.read_text().splitlines()
        if not lines:
            return []
        headers = lines[0].split(",")
        return [dict(zip(headers, line.split(","))) for line in lines[1:]]
