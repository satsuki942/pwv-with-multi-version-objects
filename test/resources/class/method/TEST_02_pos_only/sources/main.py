# 複数 version の method が positional-only signature を持つ場合も制約を保ってコンパイルされることを検証する。
from sample import Runner


if __name__ == "__main__":
    runner = Runner()
    print(runner.call(1))
    try:
        runner.call(x=1)
    except TypeError as e:
        print(type(e).__name__)
