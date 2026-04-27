# method dispatch が positional-only、可変長引数、keyword-only、kwargs を Python の signature binding で判定することを検証する。
from sample import Runner


if __name__ == "__main__":
    runner = Runner()
    print(runner.call(1))
    print(runner.call(x=2, mode="m"))
    print(runner.call())
    print(runner.call(1, 2, 3))
    print(runner.call(extra=5))
    try:
        runner.call(1, x=2)
    except TypeError as e:
        print(type(e).__name__, str(e))
