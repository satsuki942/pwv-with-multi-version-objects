# 複数の versioned_value が互いに独立した値として解決・更新されることを検証する。
from sample import LEFT, RIGHT


if __name__ == "__main__":
    print(LEFT.get(), RIGHT.get())
    LEFT.set(15)
    print(LEFT.get(), RIGHT.get())
