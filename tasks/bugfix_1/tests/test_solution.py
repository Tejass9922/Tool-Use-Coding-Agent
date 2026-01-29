from src.solution import is_palindrome

def test_simple():
    assert is_palindrome("racecar") is True
    assert is_palindrome("hello") is False

def test_case_insensitive():
    assert is_palindrome("RaceCar") is True

def test_spaces():
    assert is_palindrome("a man a plan a canal panama") is True
