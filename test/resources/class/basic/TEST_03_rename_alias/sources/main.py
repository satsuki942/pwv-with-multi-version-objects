# rename 前後のクラス名が同じ wrapper class を参照し、どちらの名前からもインスタンス化できることを検証する。
from sample import Dot, Point


if __name__ == "__main__":
    print(Dot(1).show())
    print(Point(1, 2).show())
