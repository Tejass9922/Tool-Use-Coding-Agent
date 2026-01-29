from src.solution import sum_csv_ints

def test_basic():
    assert sum_csv_ints("1,2,3") == 6

def test_spaces():
    assert sum_csv_ints(" 1, 2, 3 ") == 6

def test_trailing_comma():
    assert sum_csv_ints("1,2,3,") == 6

def test_empty():
    assert sum_csv_ints("") == 0
