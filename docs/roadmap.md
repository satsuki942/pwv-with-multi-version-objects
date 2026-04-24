# 未対応範囲ロードマップ

この文書は、複数版モジュール機能の未対応範囲を実装ロードマップとして整理する。優先順位は、利用者が扱える Python パターンを増やす機能価値を基準にする。

重要度は `高` / `低` の2段階で表す。`高` は利用者が基本的な複数版モジュールを書くときに詰まりやすい制約、`低` は特定の書き方や高度な状態管理で問題になりやすい制約とする。

詳細な入力形式と現在の仕様は [複数版モジュール仕様](versioned_modules.md) を参照する。

## 優先順位

### 1. state.sync と同期関数の接続 [重要度: 高]

目的: `evolution.json` の semantic entity と、版間の状態変換関数を接続する。

現状制約:

- `state.sync = required` は内部 IR に残せるが、同期関数の呼び出し条件にはまだ接続していない。
- 同期対象は proxy / wrapper 内に閉じ込められる状態に限定している。
- top-level name rebinding は追跡しない。

完了条件の概要:

- semantic entity id と sync 関数の対応規約を決める。
- access facade / VersionedValue / class wrapper の version 切替点に同期 hook を置く。
- 同期関数がない `required` entity の失敗時挙動を仕様化する。

### 2. 属性単位のアクセス対応 [重要度: 高]

目的: class instance の field / property 名変更を semantic entity と同じ考え方で扱う。

現状制約:

- 現在の access correspondence は top-level entity が中心である。
- 属性名変更は古い incompatibility JSON ベースの暫定 `__getattr__` / `__setattr__` に依存している。
- 属性の read/write converter と state sync の境界が未整理である。

完了条件の概要:

- `evolution.json` に属性対応を追加するか、別の state spec に分けるかを決める。
- wrapper 経由の attribute read/write で version 決定と converter を呼べるようにする。
- proxy / wrapper を迂回する属性参照の扱いを明記する。

### 3. クラス対応範囲の拡張 [重要度: 高]

目的: より広い Python クラス構文を複数版クラスとして扱えるようにする。

現状制約:

- クラス定義は主にトップレベルメソッドを対象にしている。
- クラス属性は統合対象として扱われない。
- 内部クラスは未対応。
- decorator、descriptor、property などの高度なクラス機能は明示的な仕様がない。

完了条件の概要:

- クラス属性を版ごとの値または latest 側の定義として扱う方針を決め、実装に反映する。
- 内部クラスを非対応のままにする場合は明確に検出する。対応する場合は名前解決と出力形を仕様化する。
- 代表的な decorator / property / classmethod / staticmethod の扱いをテストで固定する。

### 4. 変数再束縛の検出・診断 [重要度: 低]

目的: `VersionedValue` proxy 自体が再束縛される危険な書き方を、利用者が避けられるようにする。

現状制約:

- `versioned_value` として公開した名前は、`X = ...` のように再束縛されないことを前提とする。
- 値を差し替える場合は、明示的に `X.set(new_value)` を使う。
- 関数内の `global X; X = ...` は現在 `X.set(...)` に変換されない。
- コンパイル外コードで `X = ...` のように名前を再束縛すると、`VersionedValue` proxy 自体が置き換わるため追跡しない。

完了条件の概要:

- コンパイル対象内の危険な global 再束縛を検出し、必要ならエラーまたは警告にできる。
- コンパイル外コードからの再束縛は非対応として仕様に明記する。
- `X.set(new_value)` による明示的な値差し替えが、strategy と現在 version の規則に従って読み出されることをテストで確認する。

### 5. import / package 取り扱いの改善 [重要度: 低]

目的: package 構成での `evolution.json` module key と import 解決を安定させる。

現状制約:

- `imports` の各要素は単一の `import` または `from ... import ...` 文でなければならない。
- 相対 import、package 内 import、通常ファイルからの参照規約は利用者側の記述に依存する部分が大きい。
- `evolution.json` がない場合の AST 推論は PoC 用フォールバックである。

完了条件の概要:

- package 配下の論理 module key と import 解決の規則を明確化する。
- version ごとの import 差分、重複排除、順序の仕様をテストで固定する。
- 推論フォールバックを維持するか、明示 spec 必須にするかを決める。

## 運用方針

- 実装前に、各大項目を issue 化できるサイズのサブタスクへ分割する。
- 実装が進んだ項目は、この文書から「未対応」としての記述を削除し、必要な内容を仕様文書へ移す。
- 仕様として利用者に必要な制約は [複数版モジュール仕様](versioned_modules.md) に残し、将来実装の候補はこの文書に集約する。
