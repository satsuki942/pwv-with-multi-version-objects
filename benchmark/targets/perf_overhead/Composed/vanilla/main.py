import time
class MVO:
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
    "[obj.composed()]"
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
