import time
class MVO:
    def __init__(self):
        self.value1 = 0
        
def main():
    obj = MVO()
    start_time = time.perf_counter()
    "[obj.value1 = 1]"
    end_time = time.perf_counter()
    print(end_time - start_time)

main()
