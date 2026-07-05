"""Merge two sorted lists. Bug: does not drain remainder of the longer list."""


def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    """Merge two sorted lists into one sorted list."""
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    # BUG: remaining elements of whichever list is not exhausted are dropped
    return result
