import time
TIMES = {LOOP_COUNT}
class MVO:
    def method1(self):
        return

def main():
    obj = MVO()
    start_time = time.perf_counter()
    for _ in range(TIMES):
        obj.method1()
        obj.method1()
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
