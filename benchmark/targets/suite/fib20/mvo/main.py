import time
class Num__1__:
    def __init__(self, value):
        self.value = value
    def plus(self, other):
        return Num(self.value + other.value)
    def less_than_equal(self, other):
        return self.value <= other.value
    def equal(self, other):
        return self.value == other.value
    def minus(self, other):
        return Num(self.value - other.value)

class Num__2__:
    def __init__(self, value):
        self.value = value
    def plus(self, other):
        return Num(self.value + other.value)
    def less_than_equal(self, other):
        return self.value <= other.value
    def equal(self, other):
        return self.value == other.value
    def minus(self, other):
        return Num(self.value - other.value)

def fib(n):
    if n.less_than_equal(Num(0)):
        return Num(0)
    elif n.equal(Num(1)):
        return Num(1)
    else:
        return fib(n.minus(Num(1))).plus(fib(n.minus(Num(2))))

def main():
    start_time = time.perf_counter()
    fib(Num(20))
    end_time = time.perf_counter()
    avg_time = end_time - start_time
    print(avg_time)

main()
