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
# 例: 現行の複数版モジュールケースを実行
python main.py test/resources/module/TEST_01_basic/sources

# デバッグログを有効化
python main.py test/resources/module/TEST_01_basic/sources --debug

# バージョン選択戦略を指定
python main.py test/resources/module/TEST_01_basic/sources --strategy latest
```

- target_dir は main.py 内の `INPUT_BASE_PATH` からの相対パスです。
  - 現状の `INPUT_BASE_PATH` はリポジトリルート（`.`）です。
- strategy は continuity | latest を選択します。

## 入力形式

### 1. 入力ディレクトリ

compile() に渡すディレクトリ配下を再帰的にスキャンします。
- **/*.py はソースファイル
- `_mv_mapping/` はコンパイル用メタデータの専用ディレクトリ
- `_mv_mapping/modules.json` は複数版モジュール内の公開要素 mapping
- `_mv_mapping/**/*_sync.py` は同期モジュール
- `_mv_mapping/**/*.json` は `modules.json` を除き互換性(属性)定義

### 2. 複数版モジュール

- `foo__1__.py` と `foo__2__.py` は、同じ論理モジュール `foo.py` の別バージョンとして統合されます。
- version は整数です。1版だけの `foo__1__.py` も、現在のコンパイル単位として扱えます。
- 通常ファイルはそのままコピーされます。通常ファイル内のクラス名は、versioned module の判定には使いません。
- 通常ファイルから複数版モジュールを参照するときは、`foo__1__` / `foo__2__` ではなく、統合後の論理モジュール名 `foo` を import します。
- mapping に書かれた公開要素だけを複数版対応としてコンパイルします。
- mapping に書かれていない要素は latest version 側の定義をそのまま出力します。

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

### 6. 互換性(属性)定義 JSON

`_mv_mapping/` 配下の `modules.json` 以外の .json を読み込みます。

スキーマ
```json
{
  "<BaseName>": {
    "<version>": ["attr1", "attr2"]
  }
}
```

- `<version>` は整数の文字列です。

### 7. module mapping JSON

`_mv_mapping/modules.json` に `modules` キーを置くと、複数版モジュール内の公開要素の対応関係として扱います。

```json
{
  "modules": {
    "point": {
      "exports": {
        "Point": {
          "kind": "class"
        }
      }
    }
  }
}
```

現時点では同名・同種要素だけを mapping できます。mapping がない要素は latest 側の定義をそのまま公開します。
版間で意味が異なる変数だけ、mapping JSONで `versioned_value` または `versioned_reference` として明示してください。

### 8. エントリポイント

main.py 経由で実行する場合、入力ディレクトリ直下に main.py が存在することを想定します。

詳細な入力規約と mapping 例は `docs/versioned_modules.md`、未対応範囲の実装ロードマップは `docs/roadmap.md` を参照してください。

## テスト

- モジュール全体の統合ケース: `test/resources/module/**/TEST_*/`
- top-level class の統合ケース: `test/resources/class/**/TEST_*/`
- top-level function の統合ケース: `test/resources/function/**/TEST_*/`
- top-level variable の統合ケース: `test/resources/variable/**/TEST_*/`
- 入力サンプル: `test/resources/**/TEST_*/sources/`
- 期待出力: `test/resources/**/TEST_*/outputs/output.txt`

最下流のテストケースディレクトリは `TEST_xx_yyy` の形式にします。`xx` はその親ディレクトリ内の2桁 index、`yyy` は短い説明です。説明が不要なら `basic` を使います。
各 `sources/main.py` の先頭には、そのプログラムで検証したいことを日本語コメントで書きます。
pytest 実行時は、各ケース配下の `compiled/` に最新のコンパイル結果と `metadata.json` が出力されます。

### テストの実行

```bash
# 全テスト
pytest

# 特定のテストのみ
pytest --target_dir=module/TEST_01_basic
pytest --target_dir=class/constructor/TEST_01_basic
pytest --target_dir=function/TEST_01_dispatch
pytest --target_dir=variable/TEST_01_value
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
    ├── test_resource_cases.py
    └── resources/
        ├── module/
        ├── class/
        ├── function/
        └── variable/
```
