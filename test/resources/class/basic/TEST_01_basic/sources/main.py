# 複数 version の class method が統合され、呼び出しに応じて利用できることを検証する。
from test import Test

class Main:
    def main(self):
        t = Test()
        t.display()
        t.log()
        t.just_for_test()
        t.super_log("Hello, World!", "Alice")
        t.just_for_test()

    
if __name__ == "__main__":
    main_instance = Main()
    main_instance.main()
