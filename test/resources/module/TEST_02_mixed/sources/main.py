# class、function、versioned_value が同一 module 内で同時に統合されることを検証する。
from sample import Point, VALUE, choose


if __name__ == "__main__":
    print(Point().label())
    print(choose(1, 2))
    print(VALUE.get())
