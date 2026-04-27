# version 切替を伴う method 呼び出し後も属性値と既存 method 呼び出しが維持されることを検証する。
from log import Log
def main():
    log = Log()
    print(log.log)
    log.legacy_method()
    print(log.log)
    log.new_method()
    print(log.log)

if __name__ == "__main__":
    main()
