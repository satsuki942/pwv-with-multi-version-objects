# PWV with Multi-Version Objects

## 概要

本プロジェクトは、論文で提案する「PWV with Multi-Version Objects (MVO)」の PoC トランスパイラです。Python の AST を解析し、複数版モジュール内の class / function / top-level variable を単一の実行可能モジュールへ統合します。

## 要件

- Python 3.12 以上
- uv: 高速なパッケージインストーラ/リゾルバ

## セットアップ

```bash
# Python バージョン固定 (.python-version を作成)
uv python pin 3.12

# 依存関係インストール (.venv と uv.lock が無ければ作成)
uv sync
```

uv sync の内容
- .venv を作成
- 依存関係をインストール
- プロジェクトを editable でインストール（src/mv_compiler を import 可能にする）

### 仮想環境の有効化

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\activate

# deactivate
deactivate
```

### ベンチマーク用の別環境（推奨）

ベンチマークは本体とは別の仮想環境で実行できます。`bench` 依存グループを用意しているので、専用の venv を作って同期してください。

```bash
# ベンチマーク用の仮想環境を作成
uv venv .venv-bench

# アクティベート
.venv-bench\Scripts\activate

# ベンチマーク依存のみ同期
uv sync --group bench --active
```

通常の環境に追加したい場合は、既存の venv で `uv sync --group bench --active` を実行してください。

## 実行方法

### 手動実行

```bash
# 例: test/resources/basic_cases/TEST_basic_01/sources を実行
python main.py test/resources/basic_cases/TEST_basic_01/sources

# デバッグログを有効化
python main.py test/resources/basic_cases/TEST_basic_01/sources --debug

# バージョン選択戦略を指定
python main.py test/resources/basic_cases/TEST_basic_01/sources --strategy latest
```

- target_dir は main.py 内の `INPUT_BASE_PATH` からの相対パスです。
  - 現状の `INPUT_BASE_PATH` はリポジトリルート（`.`）です。
- strategy は continuity | latest を選択します。

## 入力形式

### 1. 入力ディレクトリ

compile() に渡すディレクトリ配下を再帰的にスキャンします。
- **/*.py はソースファイル
- `_mv_mapping/` はコンパイル用メタデータの専用ディレクトリ
- `_mv_mapping/evolution.json` は複数版モジュール内の進化仕様
- `_mv_mapping/**/*_sync.py` は同期モジュール

### 2. 複数版モジュール

- `foo__1__.py` と `foo__2__.py` は、同じ論理モジュール `foo.py` の別バージョンとして統合されます。
- version は整数です。1版だけの `foo__1__.py` も、現在のコンパイル単位として扱えます。
- 通常ファイルはそのままコピーされます。通常ファイル内のクラス名は、versioned module の判定には使いません。
- 通常ファイルから複数版モジュールを参照するときは、`foo__1__` / `foo__2__` ではなく、統合後の論理モジュール名 `foo` を import します。
- `evolution.json` に書かれた意味的 entity を複数版対応としてコンパイルします。
- `evolution.json` がない場合は、PoC 用フォールバックとして同名 entity をソースから推論します。

**例**
```python
# point__1__.py
class Point:
    def __init__(self, x: int):
        self.x = x

# point__2__.py
class Point:
    def __init__(self, r: float):
        self.r = r
```

### 3. バージョン付きクラス

- クラスは複数版モジュール内では通常のクラス名で定義します。
- クラス定義はトップレベルメソッドのみを対象にします。
- クラス属性（AnnAssign/Assign）は無視されます。
- 内部クラスは未対応です。

### 4. 継承

- バージョン付きクラスは通常クラス/バージョン付きクラスを継承できます。
- 複数版モジュール内のクラスは、コンパイル時に内部用の版付きクラスへ展開され、そこで継承関係も記録されます。

### 5. 同期モジュール (sync_modules)

- ファイル名は `<BaseName>_sync.py` です（例: Point_sync.py）。
- 位置は `_mv_mapping/` 配下です。
- 同期関数名は `_?sync_from_v<from>_to_v<to>` 形式です。先頭の `_` は任意です。
- 同期関数の引数は 1 つ（wrapper オブジェクト）です。
- 同期モジュール内の import 文は統合クラスの先頭へ移されます。

**例**
```python
def _sync_from_v1_to_v2(wrapper_obj):
    wrapper_obj._v2 = "Version 2"
    del wrapper_obj._v1
```

### 6. evolution JSON

`_mv_mapping/evolution.json` に module ごとの version、import、意味的 entity の対応を書きます。

```json
{
  "modules": {
    "point": {
      "versions": [1, 2],
      "imports": {
        "1": [],
        "2": []
      },
      "entities": {
        "point": {
          "state": {"sync": "none"},
          "versions": {
            "1": {"kind": "class", "name": "Point"},
            "2": {"kind": "class", "name": "PolarPoint"}
          }
        }
      }
    }
  }
}
```

top-level kind は `import`, `function`, `variable`, `class` の4種類です。`import` は `imports` に分け、`function` / `variable` / `class` は `entities` に意味的対応として書きます。

`state.sync = required` は、後続の状態同期対象であることを示します。状態同期は runtime が生成する proxy / wrapper の内側に閉じ込められる状態だけを対象にし、Python の通常の top-level name rebinding は追跡しません。

### 7. エントリポイント

main.py 経由で実行する場合、入力ディレクトリ直下に main.py が存在することを想定します。

詳細な入力規約と evolution 例は `docs/versioned_modules.md`、未対応範囲の実装ロードマップは `docs/roadmap.md` を参照してください。

## テスト

- テストケース: test/resources/**/TEST_*/ 以下
- 入力サンプル: test/resources/**/TEST_*/sources/
- 期待出力: test/resources/**/TEST_*/outputs/output.txt

### テストの実行

```bash
# 全テスト
pytest

# 特定のテストのみ
pytest --target_dir=basic_cases/TEST_basic_01
```

## ディレクトリ構成

```
.
├── main.py
├── pyproject.toml
├── src/
│   └── mv_compiler/
│       ├── api.py
│       ├── compiler/
│       │   ├── project.py
│       │   ├── scanner.py
│       │   ├── module/
│       │   │   └── compiler.py
│       │   ├── elements/
│       │   │   ├── class_/
│       │   │   ├── function/
│       │   │   └── variable/
│       │   └── common/
│       │       └── util/
│       └── runtime/
│           └── executor.py
└── test/
    ├── conftest.py
    ├── test_create.py
    ├── test_transformer.py
    └── resources/
        ├── basic_cases/
        │   └── TEST_basic_01/
        │       ├── sources/
        │       └── outputs/
        └── features/
            └── ...
```
