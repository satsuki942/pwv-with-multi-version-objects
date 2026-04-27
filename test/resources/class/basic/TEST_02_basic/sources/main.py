# 複数 version の class 属性を統合後に読み書きできることを検証する。
from test import Test

class Main:
    def main(self):
        t = Test()
        print(t.v2)
        t.v1 = "Updated Version 1"
        t.log()

    
if __name__ == "__main__":
    main_instance = Main()
    main_instance.main()
