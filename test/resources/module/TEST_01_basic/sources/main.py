# class、function、variable を含む versioned module の基本的な統合結果を検証する。
from sample import PLAIN, THRESHOLD, Point, label


def main():
    print(PLAIN)
    print(label())
    print(THRESHOLD + 5)
    p = Point(3)
    print(p.show())


if __name__ == "__main__":
    main()
