def fib(n: int) -> int:
    """Return nth Fibonacci number with fib(0)=0, fib(1)=1."""
    # BUG: off-by-one in loop
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
