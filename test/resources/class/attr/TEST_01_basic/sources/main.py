# method 経由で更新した属性値を class 統合後も読めることを検証する。
from log import Log

def main():
    log = Log()
    log.setlog("This is a log message.")
    print(log.log)

if __name__ == "__main__":
    main()
