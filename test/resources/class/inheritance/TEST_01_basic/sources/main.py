# 通常 class を継承する versioned class が統合後も継承 method を利用できることを検証する。
from car import Car
def main():
    car = Car()
    car.start_engine()
    car.honk()
    
if __name__ == "__main__":
    main()
