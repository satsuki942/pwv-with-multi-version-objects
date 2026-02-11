import time
class MVO__1__:
    def __init__(self):
        self.value1 = 0

    def method1(self):
        self.value1 += 1

class MVO__2__:
    def __init__(self):
        self.value1 = 0

    def method1(self):
        self.value1 += 1
    
def main():
    obj = MVO()
    start_time = time.perf_counter()
    "[obj.method1()]"
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
