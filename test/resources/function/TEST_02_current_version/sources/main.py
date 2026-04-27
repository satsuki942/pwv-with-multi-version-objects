# top-level function の current version が export ごとに独立して保持されることを検証する。
from sample import left, right


if __name__ == "__main__":
    print(left._mvo_current_version, right._mvo_current_version)
    print(left(1, 2))
    print(left._mvo_current_version, right._mvo_current_version)
    print(right(3))
    print(left._mvo_current_version, right._mvo_current_version)
