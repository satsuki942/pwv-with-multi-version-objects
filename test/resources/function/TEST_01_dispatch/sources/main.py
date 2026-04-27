# top-level function が引数に応じて呼び出し可能な version へ dispatch されることを検証する。
from sample import choose


if __name__ == "__main__":
    print(choose(1))
    print(choose(1, 2))
    print(choose(1, 2, 3))
    print(choose(4, 5))
