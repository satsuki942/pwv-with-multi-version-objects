# 複数版モジュール仕様

この機能は、`foo__1__.py` と `foo__2__.py` のようなファイルを同じ論理モジュール `foo.py` の別バージョンとして扱い、単一の出力モジュールへ統合する。

## 入力ファイル規約

- `module_name__1__.py`: version 1 のモジュール定義
- `module_name__2__.py`: version 2 のモジュール定義
- 出力は `module_name.py`
- version は整数
- 1版以上を対象にする。1版だけの場合も、複数版対応済みの公開要素を持つモジュールとして出力される
- 通常ファイルはそのままコピーされる。通常ファイル内のクラス名は、versioned module の判定には使わない
- `_mv_mapping/` はコンパイル用メタデータの専用ディレクトリであり、出力対象の通常ソースにはしない

## mapping JSON

`_mv_mapping/modules.json` に `modules` キーを置くと、版付きモジュールの公開要素の対応関係として扱う。

```json
{
  "modules": {
    "foo": {
      "imports": {
        "1": [
          "import os",
          "from math import sqrt"
        ],
        "2": [
          "from decimal import Decimal"
        ]
      },
      "exports": {
        "Point": {
          "kind": "class"
        },
        "make_label": {
          "kind": "function"
        },
        "THRESHOLD": {
          "kind": "variable",
          "binding": "versioned_value"
        }
      }
    }
  }
}
```

現時点では同名・同種要素だけを mapping できる。mapping がない要素は、他の version に同名要素があっても latest 側の定義をそのまま公開する。

`imports` は各 version が必要とする import 文の移行仕様である。コンパイラは versioned module のASTから import 文を収集せず、`modules.json` に書かれた import 文だけを出力する。`imports` がない module、または version key がない version は import なしとして扱う。

出力される import 文は version 昇順、各 version 内の配列順で並ぶ。同じ import 文は1回だけ出力する。各文字列は単一の `import` または `from ... import ...` 文でなければならない。

## top-level 関数

top-level 関数 export は、公開関数ごとに現在 version を保持する。現在 version は生成された関数オブジェクトの `_mvo_current_version` 属性に保存されるため、同じモジュール内の複数関数は互いに独立して version を持つ。

呼び出し時はまず現在 version の関数実装が引数に対して呼び出し可能かを検査し、可能ならその version を呼ぶ。呼び出し不可の場合は version 昇順で呼び出し可能な実装を探し、見つかった version をその関数の現在 version として保存してから呼ぶ。

## top-level 変数

top-level 変数は値を作る構文ではなく名前束縛なので、デフォルトでは複数版対応しない。版間で意味が異なる変数だけ、ライブラリ開発者が明示的に `binding` を指定する。

- `plain`: latest 側の値をそのまま公開する
- `versioned_value`: `VersionedValue` proxy で包み、演算や属性アクセスをその変数オブジェクト自身が選ぶ現在版の値へ委譲する
- `versioned_reference`: すでにMVO wrapperなど版管理を持つ値への参照として扱い、二重には包まない

`VersionedValue` は `get()`, `set(new_value)` を持つ。値を読むたびに、その値がどこから参照されたかではなく、対象 `VersionedValue` オブジェクト自身の strategy と現在 version に従って実体値を決定する。関数やメソッドの実装 version は、そこで参照される `VersionedValue` の version を固定しない。加えて、基本的な演算・属性アクセス・添字アクセスは内部の現在版の値へ委譲する。ただし、`type(X) is int` のような完全な型透過性は保証しない。

## 未対応範囲

- import文の書き換え
- 関数・メソッド dispatch の引数判定における `*args` / `**kwargs` / keyword-only / positional-only を含む複雑なシグネチャの完全対応
- 名前が異なる要素同士の mapping
- class / function / variable など種類が異なる要素同士の mapping
- コンパイル外コードでの名前再束縛
- 関数内の `global X; X = ...` を `VersionedValue.set()` へ変換する処理
- 複雑な変数間同期関数
