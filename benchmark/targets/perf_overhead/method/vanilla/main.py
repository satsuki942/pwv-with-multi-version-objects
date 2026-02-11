import time
class MVO:
    def method1(self):
        return

def main():
    obj = MVO()
    start_time = time.perf_counter()
    "[obj.method1()]"
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
