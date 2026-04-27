# 統合後の class インスタンスで属性への直接代入と読み取りができることを検証する。
from log import Log

def main():
    log = Log()
    log.log = "This is a log message."
    print(log.log)

if __name__ == "__main__":
    main()
