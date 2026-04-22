# トランスパイラ用の簡易ロガー。

# デバッグ出力を有効化するフラグ。
# コマンドライン引数で有効化できる。
DEBUG_MODE = False

def debug_log(message: str):
    """デバッグメッセージを出力する。"""
    if DEBUG_MODE:
        print(f"[LOG]     {message}")

def success_log(message: str):
    """成功メッセージを出力する。"""
    if DEBUG_MODE:
        print(f"[SUCCESS] {message}")

def error_log(message: str):
    """エラーメッセージを出力する。"""
    print(f"[ERROR]   {message}")

def warning_log(message: str):
    """警告メッセージを出力する。"""
    print(f"[WARNING] {message}")

def no_header_log(message: str):
    """ヘッダ無しでメッセージを出力する。"""
    if DEBUG_MODE:
        print(message)

def log(message: str):
    """常に表示したい一般メッセージを出力する。"""
    print(message)
