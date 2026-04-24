# 複数版モジュール仕様

この機能は、`foo__1__.py` と `foo__2__.py` のようなファイルを同じ論理モジュール `foo.py` の別バージョンとして扱い、単一の出力モジュールへ統合する。

## 入力ファイル規約

- `module_name__1__.py`: version 1 のモジュール定義
- `module_name__2__.py`: version 2 のモジュール定義
- 出力は `module_name.py`
- version は整数
- 通常ファイルはそのままコピーされる
- 通常ファイルから版付きモジュールを参照するときは、統合後の論理モジュール名 `foo` を import する
- `_mv_mapping/` はコンパイル用メタデータの専用ディレクトリであり、出力対象の通常ソースにはしない

## evolution JSON

`_mv_mapping/evolution.json` を移行仕様の入力として扱う。`modules.json` はこの PoC では使わない。

```json
{
  "modules": {
    "sample": {
      "versions": [1, 2],
      "imports": {
        "1": ["import os"],
        "2": ["from math import sqrt"]
      },
      "entities": {
        "position": {
          "state": {"sync": "required"},
          "versions": {
            "1": {"kind": "variable", "name": "x"},
            "2": {"kind": "function", "name": "y"}
          }
        },
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

`entities` の key は公開名ではなく、開発者が与える意味的 entity id である。各 entity は version ごとに `kind` と source `name` を持つ。`kind` は `function` / `variable` / `class` のいずれかである。`import` は top-level kind として扱うが、意味的 entity ではないため `imports` に分ける。

## import

`imports` は version 昇順、各 version 内の配列順で重複なしに union する。各文字列は単一の `import` または `from ... import ...` 文でなければならない。

`evolution.json` がない module では、既存 fixture を動かすために source AST から同名 entity と import を推論する。この推論は PoC 用のフォールバックであり、研究仕様としては `evolution.json` に意味的対応を書く。

## アクセス対応

公開 API の名前集合は、全 entity の `versions.*.name` から導出する。同じ entity が version ごとに別名・別 kind になってもよい。同じ公開名が version ごとに別 entity を指してもよい。

例:

```json
{
  "entities": {
    "position": {
      "state": {"sync": "required"},
      "versions": {
        "1": {"kind": "variable", "name": "x"},
        "2": {"kind": "variable", "name": "y"}
      }
    },
    "count": {
      "state": {"sync": "required"},
      "versions": {
        "1": {"kind": "variable", "name": "z"},
        "2": {"kind": "variable", "name": "x"}
      }
    }
  }
}
```

この場合、公開名 `x` は v1 では `position`、v2 では `count` を指す。状態同期で見るべき対応は公開名 `x` ではなく、`position` と `count` の entity 内対応である。

## 版決定

関数 facade は関数オブジェクトごとに現在 version を持つ。クラス wrapper は object ごとに現在 version を持つ。変数 proxy は proxy ごとに現在 version を持つ。

アクセス時はまず現在 version の候補を試す。現在 version がその操作に対応できない場合、操作可能な候補のうち latest version を選び、現在 version を更新する。関数・メソッドの呼び出し可能判定は `inspect.signature(...).bind(...)` の成否で決める。

## 状態同期制約

`state.sync` は `none` または `required` である。省略時は `none` とみなす。

状態同期は、状態を runtime が生成する proxy / wrapper の内側に閉じ込められる場合だけ扱う。Python の通常の top-level name rebinding は追跡しない。primitive / immutable value の更新は、生成された proxy API 経由で行う必要がある。

`identity` は入力仕様には書かせない。compiler/runtime が kind 構成から binding proxy、instance wrapper、または access facade を推論する。

## 未対応範囲

現在の主な未対応範囲は、同期関数と `state.sync = required` の接続、属性単位の対応、proxy を迂回する参照の診断、クラス構文の拡張、package 内 module key の厳密化である。

実装ロードマップは [未対応範囲ロードマップ](roadmap.md) を参照する。
