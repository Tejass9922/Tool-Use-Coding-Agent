def sum_csv_ints(line: str) -> int:
    """Given a comma-separated string of integers, return the sum.

    Example: "1,2,3" -> 6
    """
    # BUG: fails on whitespace and empty segments
    parts = line.split(",")
    return sum(int(p) for p in parts)
