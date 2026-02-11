import time
TIMES = {LOOP_COUNT}
class MVO__1__:
    def __init__(self):
        self.value1 = 0

class MVO__2__:
    def __init__(self):
        self.value2 = 0

def main():
    obj = MVO()
    start_time = time.perf_counter()
    for _ in range(TIMES):
        obj.value1 = 1
        obj.value1 = 0
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
