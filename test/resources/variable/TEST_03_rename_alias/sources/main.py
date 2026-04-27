# rename 前後の変数名が同じ VersionedValue 実体を参照し、片方の更新がもう片方から見えることを検証する。
from sample import Dot, Point


if __name__ == "__main__":
    print(Point.get())
    Dot.set("updated")
    print(Point.get())
