# rename 前後の関数名が同じ wrapper 関数を参照し、どちらの名前からも dispatch できることを検証する。
from sample import new_name, old_name


if __name__ == "__main__":
    print(old_name(1))
    print(new_name(1, 2))
