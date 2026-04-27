# function dispatch が positional-only、可変長引数、keyword-only、kwargs を Python の signature binding で判定することを検証する。
from sample import choose


if __name__ == "__main__":
    print(choose(1))
    print(choose(x=2, mode="m"))
    print(choose())
    print(choose(1, 2, 3))
    print(choose(extra=5))
    try:
        choose(1, x=2)
    except TypeError as e:
        print(type(e).__name__, str(e))
