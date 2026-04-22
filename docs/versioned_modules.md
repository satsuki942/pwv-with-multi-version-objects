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

## top-level 変数

top-level 変数は値を作る構文ではなく名前束縛なので、デフォルトでは複数版対応しない。版間で意味が異なる変数だけ、ライブラリ開発者が明示的に `binding` を指定する。

- `plain`: latest 側の値をそのまま公開する
- `versioned_value`: `VersionedValue` proxy で包み、演算や属性アクセスを現在版の値へ委譲する
- `versioned_reference`: すでにMVO wrapperなど版管理を持つ値への参照として扱い、二重には包まない

`VersionedValue` は `get()`, `set()`, `switch_to(version)` を持つ。加えて、基本的な演算・属性アクセス・添字アクセスは内部の現在版の値へ委譲する。ただし、`type(X) is int` のような完全な型透過性は保証しない。

## 未対応範囲

- import文の書き換え
- 各version固有のimportを、個別要素のコンパイル結果へ正しく反映する処理
- 3版以上の関数exportに対する洗練されたversion dispatch
- 名前が異なる要素同士の mapping
- class / function / variable など種類が異なる要素同士の mapping
- コンパイル外コードでの名前再束縛
- 関数内の `global X; X = ...` を `VersionedValue.set()` へ変換する処理
- 複雑な変数間同期関数
