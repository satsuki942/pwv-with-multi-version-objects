# 統合クラスのメソッド内での self の束縛が以下のようになることを確認
# - 直接のメソッド内では wrapper のインスタンス
# - それより深くでは新たに束縛可能
from a import A

def main():
    A().method()
if __name__ == '__main__':
    main()
