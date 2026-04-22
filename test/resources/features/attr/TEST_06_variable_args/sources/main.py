from test import Test

def main():
    t = Test()
    t.a(10)
    t.b(n=20)
    t.new_method()
    t.a(10)
    t.b(n=20)
    t.legacy_method()
    t.c(30)
    t.d(n=40)
    t.new_method()
    t.c(30)
    t.d(n=40)
if __name__ == '__main__':
    main()
