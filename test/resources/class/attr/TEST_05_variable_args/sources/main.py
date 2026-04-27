# 可変長引数や keyword 引数を持つ method が version 切替後も正しく dispatch されることを検証する。
from test import Test

def main():
    t = Test()
    t.a(10)
    t.b(n=20)
    t.new_method()
    t.a(10)
    t.b(n=20)
    t.stable_method()
    t.c(30)
    t.d(n=40)
    t.new_method()
    t.c(30)
    t.d(n=40)
if __name__ == '__main__':
    main()
