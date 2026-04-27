# import 文ではない import spec を modules.json に書くとコンパイルエラーになることを検証する。
from sample import Point


if __name__ == "__main__":
    print(Point)
