import time
class MVO__1__:
    def __init__(self):
        return

    def method(self):
        return

    def composed(self):
        self.value += 1

class MVO__2__:
    def __init__(self):
        return

    def method(self):
        return

    def composed(self):
        self.value += 1

def main():
    obj = MVO()
    obj.value = 0
    start_time = time.perf_counter()
    "[obj.value = 1]"
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
