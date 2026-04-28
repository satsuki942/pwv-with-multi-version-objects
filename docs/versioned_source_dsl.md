# Versioned Source DSL

この文書は、top-level versioned source DSL を使う入力形式の仕様である。
このブランチでは、旧来の `_mv_mapping/modules.json` と `foo__N__.py` による入力互換は要件にしない。

## 基本モデル

1つの `.py` ファイルを、単一の論理モジュールとして扱う。
通常の top-level 定義は最古版 `v1` のプログラムであり、その直後に置いた差分ブロックが同じ semantic entity の履歴を表す。

差分ブロックは module top-level にだけ置ける。class body や function body 内の差分ブロックは未対応である。

## Version 指定

差分ブロックは `with _mv.v(N).operation(...):` で書く。
`N` は整数だけを許す。

```python
with _mv.v(2).change():
    ...
```

## Import

import は entity ではなく、全 version の import の和として扱う。
通常 import と `imports()` ブロック内の import を集め、重複を除去して出力する。

```python
import os

with _mv.v(2).imports():
    import sys
    from pathlib import Path
```

## Variable

変数 entity の初回定義は通常の Python 代入として書く。
その変数を複数版 entity として扱う最初の差分ブロックで、`variable_versioning` を明示する。

```python
x = 1

with _mv.v(2).change(variable_versioning="generated"):
    x = 2
```

`variable_versioning` は `"generated"` または `"referenced"` を許す。
`generated` は compiler が versioned value proxy を生成する。
`referenced` は最新の具体定義を代表束縛として使う。

途中 version で変数を追加する場合は、通常の追加として `add()` を使う。
`add()` は新しい semantic entity の導入であり、履歴分岐ではないため `variable_versioning` は書かない。

```python
with _mv.v(2).add():
    z = 10
```

## Function / Class

関数とクラスは通常の Python 定義として書く。

```python
def f(x):
    return x

with _mv.v(2).rename("g"):
    def g(x, y=0):
        return x + y
```

```python
class A:
    def value(self):
        return 1

with _mv.v(2).change():
    class A:
        def value(self):
            return 2
```

## Operations

### `change`

同じ semantic entity の実装を変更する。
名前は変わらない。

### `rename`

同じ semantic entity の公開名を変える。
引数の新名と body 内の定義名は一致していなければならない。

```python
with _mv.v(2).rename("NewName"):
    class NewName:
        pass
```

### `add`

新しい semantic entity を追加する。
MVP では body に単一の variable / function / class 定義だけを置く。
`variable_versioning` は `add()` では指定できない。

### `delete`

semantic entity がその version 以降のソース上では存在しないことを表す。
ただし旧版互換のため、過去の具体定義は生成コードに残る。

```python
with _mv.v(3).delete():
    del f
```

### `revive`

`delete` された semantic entity が復活したことを表す。
`add` は別 semantic entity の追加、`revive` は同じ semantic entity の再登場である。

```python
with _mv.v(4).revive():
    def f(x):
        return x * 2
```

## Sync

sync 関数専用の差分ブロックは置かない。
class の `change` / `rename` / `revive` ブロック内に、既存規約の sync 関数を直接置く。

```python
class A:
    def __init__(self, x):
        self.x = x

with _mv.v(2).change():
    class A:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    def _sync_from_v1_to_v2(obj):
        obj.y = 0
```

sync 関数は通常の function entity にはしない。

## Well-formedness

名前衝突は well-formed な入力では起きない前提にする。
特に `delete` 後に同じ名前を `add` して別 semantic entity として使う入力は、この仕様では扱わない。

kind change、class 内差分、method 単位差分、public name collision の解決は後続フェーズで扱う。
