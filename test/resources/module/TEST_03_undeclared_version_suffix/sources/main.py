# modules.jsonに宣言されていない __<version>__ ファイルは通常モジュールとして扱うことを検証する。
from sample__1__ import value


def main():
    print(value())


if __name__ == "__main__":
    main()
