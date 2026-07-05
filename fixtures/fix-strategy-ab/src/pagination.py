"""Paginate a list of items. Bug: off-by-one in page count calculation."""


def paginate(items: list, page_size: int) -> int:
    """Return total number of pages needed for items at given page_size."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    # BUG: integer division truncates; 10 items / 3 per page = 3, but need 4
    return len(items) // page_size


def get_page(items: list, page: int, page_size: int) -> list:
    """Return items for the given 1-based page number."""
    if page < 1:
        raise ValueError("page must be >= 1")
    start = (page - 1) * page_size
    return items[start : start + page_size]
