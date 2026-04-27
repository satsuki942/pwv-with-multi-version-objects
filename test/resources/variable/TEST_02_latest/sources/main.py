# latest strategy では versioned_value が latest 版の値で初期化されることを検証する。
from sample import VALUE


if __name__ == "__main__":
    print(VALUE.get())
