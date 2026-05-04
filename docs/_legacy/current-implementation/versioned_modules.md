# 複数版モジュール仕様

この機能は、`modules.json` に宣言された `foo__1__.py` と `foo__2__.py` のようなファイルを、同じ論理モジュール `foo.py` の別バージョンとして扱い、単一の出力モジュールへ統合する。

## 入力ファイル規約

- `_mv_mapping/modules.json` に宣言された module だけを versioned module として扱う。
- `module_path: "models/location"` と `versions: [1, 2]` は、`models/location__1__.py` と `models/location__2__.py` を入力にして `models/location.py` を出力する。
- `__<version>__` というファイル名は、宣言された場合だけ versioned module の一部になる。未宣言の `foo__1__.py` は通常モジュール `foo__1__` として扱う。
- 通常ファイルはそのままコピーされる。通常ファイルから版付きモジュールを参照するときは、統合後の論理モジュール名を import する。
- `_mv_mapping/` はコンパイル用メタデータの専用ディレクトリであり、出力対象の通常ソースにはしない。

## mapping JSON

`modules` は object で、key は設定上の論理識別子である。実ファイルの場所と出力先は `module_path` で決める。

```json
{
  "modules": {
    "foo": {
      "module_path": "foo",
      "versions": [1, 2],
      "imports": {
        "1": ["import os", "from math import sqrt"],
        "2": ["from decimal import Decimal"]
      },
      "entity_mappings": [
        {
          "entity_key": "Point",
          "kind": "class",
          "source_names": {
            "1": "Point",
            "2": "Point"
          }
        },
        {
          "entity_key": "make_label",
          "kind": "function",
          "source_names": {
            "1": "make_label",
            "2": "make_label"
          }
        },
        {
          "entity_key": "threshold",
          "kind": "variable",
          "versioned_by": "generated",
          "source_names": {
            "1": "THRESHOLD",
            "2": "LIMIT"
          }
        }
      ]
    }
  }
}
```

`versions` は number array で必須であり、存在する version の正とする。宣言された version の source file が欠ける場合はコンパイルエラーになる。

`entity_mappings` は、版間で同一 semantic entity とみなす top-level class / function / variable の対応関係を宣言する。`kind` は `class`, `function`, `variable` のいずれかである。

`entity_key` は任意だが、指定する場合は module 内で一意でなければならない。これは public name ではなく、sync module / incompatibility lookup と内部 entity 識別に使う。省略時は `source_names` から自動導出する。

`source_names` は、module の `versions` 全件分を持つ object である。全 version で同じ名前なら rename なし、異なる名前なら same-kind rename として扱う。

```json
{
  "modules": {
    "sample": {
      "module_path": "sample",
      "versions": [1, 2],
      "entity_mappings": [
        {
          "entity_key": "position",
          "kind": "class",
          "source_names": {
            "1": "Dot",
            "2": "Point"
          }
        }
      ]
    }
  }
}
```

異名 mapping は同種要素だけを対象にする。生成コードでは entity 本体を作り、各 source name をその entity への alias として公開する。異 kind 要素同士の対応付けと、rename によって別 entity の公開名が衝突するケースは未対応である。

`imports` は各 version が必要とする import 文の移行仕様である。コンパイラは versioned module のASTから import 文を収集せず、`modules.json` に書かれた import 文だけを出力する。出力される import 文は version 昇順、各 version 内の配列順で並び、同じ import 文は1回だけ出力する。

## top-level 関数

top-level 関数 entity は、公開関数ごとに現在 version を保持する。現在 version は生成された関数オブジェクトの `_mvo_current_version` 属性に保存されるため、同じモジュール内の複数関数は互いに独立して version を持つ。初期 version は strategy にかかわらず latest version である。

呼び出し時はまず現在 version の関数実装が引数に対して呼び出し可能かを検査し、可能ならその version を呼ぶ。呼び出し不可の場合は version 降順で呼び出し可能な実装を探し、見つかった version をその関数の現在 version として保存してから呼ぶ。

## top-level 変数

variable entity は `versioned_by` を必須とする。

- `generated`: compiler が `VersionedValue` proxy を生成し、各 version の代入右辺を保持する。
- `referenced`: 参照先がすでに versioned な値だとみなし、`VersionedValue` では包まない。latest 側の右辺を代表束縛にし、rename がある場合は各 source name を alias にする。

`VersionedValue` は `get()`, `set(new_value)` を持つ。値を読むたびに、対象 `VersionedValue` オブジェクト自身の現在 version に従って実体値を決定する。初期 version は latest version である。

## 関数・メソッド dispatch

関数・メソッド dispatch の呼び出し可能判定は、生成後の実体関数に対する `inspect.signature(...).bind(...)` の成否で決める。つまり、`*args` / `**kwargs` / keyword-only / positional-only を含む Python の通常の関数呼び出し binding に従い、binding できない候補は呼び出さない。

## 未対応範囲

現在の主な未対応範囲は、異 kind 要素同士の mapping、変数再束縛の検出・診断、クラス構文の拡張、複雑な状態同期、import 取り扱いの改善である。

旧ロードマップは退避時点でリポジトリ上に残っていない。
