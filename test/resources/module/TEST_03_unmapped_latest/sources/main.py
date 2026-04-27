# mapping がない versioned module では latest 版の定義が公開されることを検証する。
from sample import Point, helper


if __name__ == "__main__":
    print(Point().label())
    print(helper())
