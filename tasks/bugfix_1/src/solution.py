def is_palindrome(s: str) -> bool:
    # BUG: does not normalize whitespace / punctuation / casing
    return s == s[::-1]
