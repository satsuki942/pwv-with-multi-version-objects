# PWV with Multi-Version Objects

本リポジトリは、複数バージョンのプログラムが混在するコードを整合的に実行するための言語と、その Python 向けコンパイラ実装を扱う研究用リポジトリです。

言語仕様は [docs/README.md](docs/README.md) から参照してください。

## 要件

- Python 3.12 以上
- uv

## セットアップ

```bash
uv python pin 3.12
uv sync
```

仮想環境を有効化する場合:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\activate
```

## 基本コマンド

```bash
# サンプル入力をコンパイルして実行
python main.py test/resources/module/TEST_01_basic/sources

# デバッグログを有効化
python main.py test/resources/module/TEST_01_basic/sources --debug

# テスト
pytest
```

ベンチマーク用依存関係が必要な場合:

```bash
uv sync --group bench --active
```

## ドキュメント

- [docs/README.md](docs/README.md): ドキュメント入口
- [docs/spec/README.md](docs/spec/README.md): 言語仕様
- [docs/spec/compatibility-features/README.md](docs/spec/compatibility-features/README.md): 互換仕様で使う判定材料と実現機能
- [benchmark/README.md](benchmark/README.md): ベンチマーク実行方法
- [test/resources/README.md](test/resources/README.md): テストリソースの管理方法
