from src.solution import fib

def test_base():
    assert fib(0) == 0
    assert fib(1) == 1

def test_small():
    assert fib(2) == 1
    assert fib(3) == 2
    assert fib(4) == 3
    assert fib(5) == 5

def test_medium():
    assert fib(10) == 55
