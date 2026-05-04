# Evolution Spec 設計メモ

この文書は、`feature/evolution-spec-design` ブランチおよびその未コミット WIP で検討した内容を、実装ではなく設計メモとして整理し直したものである。

目的は次の2つ。

- いったん branch 上の実装を捨てても、考察を失わないようにすること
- 将来あらためて設計をやり直すときの論点と有力案を残すこと

## 背景

複数版モジュールの進化仕様を、従来の `modules.json` 的な公開名中心の対応付けから、意味的な entity 中心の仕様へ置き換えたい。

そのために `_mv_mapping/evolution.json` を中心とする設計を検討した。

大きな方向性としては妥当だったが、実装を進める中で次の問題が見えた。

- 名前変更と公開 API 名の扱いが曖昧になりやすい
- kind 変更まで一度に扱おうとすると runtime が汎化されすぎる
- mixed-kind や public name 衝突を 1 つの汎用 runtime に押し込むと意味論が濁る
- compiler が source AST から何を推論すべきかと、spec に何を書かせるべきかの境界が不明瞭になる

特に、名前変更と kind 変更を同時に一般化した実装は、動いても説明しにくく、研究仕様としてはあまりきれいではなかった。

## 中心概念

設計上、次の概念は有用だった。

- semantic entity
  版をまたいで「同じ意味的対象」とみなしたいもの。`evolution.json` の中心単位。
- public name
  統合後モジュールで実際に export される名前。
- public-name facade
  public name へのアクセスを受け取り、その名前が今どの entity / version を指すかを解決する公開側の入口。
- entity facade
  semantic entity へのアクセスを受け取り、その entity の current version、状態同期、実体アクセスを扱う入口。
- proxy
  facade のうち、値や名前のように透過的に振る舞う実行時オブジェクト。特に variable 系で自然。
- wrapper
  class instance の版管理と内部状態を持つ実行時オブジェクト。

この用語分け自体はかなり有望だった。

## 抽象的な処理フロー

アクセス処理は抽象的には次のように整理できる。

1. 呼び出し元からのアクセスを受け取る
2. 必要なら public-name facade に入る
3. 呼び出し元の文脈、呼び出し形、または保持している current version から、どの版で扱うかを決める
4. 必要なら entity facade に入る
5. 必要なら状態同期を行う
6. 実際の処理、値参照、メソッド呼び出しへ流す

この整理の利点は、次の責務分離ができる点にある。

- public-name facade は「公開名が今どの entity / version を指すか」を扱う
- entity facade は「その entity をどう実行・同期するか」を扱う

この見方は今後の再設計でも維持する価値が高い。

## class の見方

class では、クラス名へのアクセス時点とインスタンス生成後を分けて考える必要がある。

- constructor 呼び出し前
  public-name facade が入口になる
- constructor 呼び出し後
  instance wrapper が entity facade と wrapper の役割を実質的に併せ持つ

つまり class は、関数や変数のように facade を単純に 2 層に並べるより、

- クラス名レベルでは public-name facade
- 生成後は instance wrapper

と考えた方が整理しやすい。

## same-kind rename は有望

名前変更と kind 変更を一度に扱うのではなく、まず same-kind rename に限定すると、かなりきれいに整理できる。

### 基本原則

- semantic continuity は entity に属する
- export される名前解決は public name に属する

この分離を採ると、entity 側は kind ごとの既存ロジックを比較的そのまま使える。

### kind ごとの見通し

- function
  状態同期が不要なので、entity facade はかなり薄くできる。public-name facade は適切な function entity を選び、その中で callable な version を選べばよい。
- variable
  値の保持は entity 側に置き、public-name facade は proxy として entity を選ぶのが自然。
- class
  public-name facade が constructor 先の entity を決め、生成後は instance wrapper が管理を引き受ける。

このため、再設計の順番としては

1. variable
2. function
3. class

の順で詰めるのがよい。

## 名前衝突の問題

same-kind rename を許すと、rename の結果として同じ public name が版ごとに異なる entity を指すことがある。

例:

- v1: `x`, `y`
- v2: `y`, `z`
- semantic correspondence: `x -> y`, `y -> z`

このとき `y` は

- v1 では旧 `y`
- v2 では旧 `x`

を指す public name になる。

この問題は entity の問題ではなく、public name の問題として扱うべきである。

## 有力案: `name_collisions`

`entities` だけでは semantic correspondence は書けるが、

- public name の衝突が意図的なのか
- その名前が版ごとにどの entity を指すのか

までは分からない。

そのため、衝突名だけを別に明示する案が有力だった。

例:

```json
{
  "modules": {
    "sample": {
      "entities": {
        "position": {
          "versions": {
            "1": {"kind": "function", "name": "x"},
            "2": {"kind": "function", "name": "y"}
          }
        },
        "count": {
          "versions": {
            "1": {"kind": "function", "name": "y"},
            "2": {"kind": "function", "name": "z"}
          }
        }
      },
      "name_collisions": {
        "y": {
          "1": "count",
          "2": "position"
        }
      }
    }
  }
}
```

この案の意味は次の通り。

- `entities` は semantic correspondence だけを書く
- 公開名は原則として `entities.*.versions.*.name` から自動導出する
- 衝突している public name だけ `name_collisions` で明示する
- `name_collisions` に書かれていない衝突はエラーにする

これはかなり筋が良い案だった。

## kind change はまだ開かれている

kind change を same-kind rename と同じ仕組みで吸収しようとすると、意味論が急に重くなる。

例えば次のような変更は、単に「同じ entity の別版」と言い切ってよいかが怪しい。

- variable -> function
- function -> class
- class -> variable

この場合、

- 単一の public-name facade にまとめるべきか
- entity continuity をどこまで保つべきか
- 呼び出し可能性、代入可能性、状態同期可能性をどう扱うか

が未整理である。

したがって、再設計時は次の方針がよい。

- まず same-kind rename を仕様化する
- kind change は別フェーズに分ける
- mixed-kind 用の runtime を最初から一般解として据えない

## `evolution.json` 必須化

途中の検討では、`evolution.json` がない場合に source AST から自動推論する案もあったが、最終的には次の理由であまり良くないと感じた。

- spec と実装の責任分界が曖昧になる
- fixture 救済と本来仕様が混ざる
- public name 衝突の意図は AST だけでは分からない

このため、将来の本設計では、複数版モジュールについては `evolution.json` を必須にする方向が自然である。

## 今後の優先順位

再設計するなら、優先順位は次がよい。

1. `evolution.json` の最小仕様を確定する
2. same-kind rename に限定した public-name facade / entity facade の責務を固定する
3. `name_collisions` の位置づけを正式化する
4. variable の public-name facade を先に実装する
5. function を続ける
6. class は constructor と instance wrapper を分けて設計する
7. その後で kind change を別問題として扱う

## 残っている主要論点

- public-name facade 自体が current version を持つべきか
- current version は entity facade だけに持たせれば十分か
- class の公開オブジェクトを Python の `class` として見せるべきか、factory 的 facade として見せるべきか
- `state.sync = required` を entity facade にどう接続するか
- attribute-level access correspondence を entity facade 内でどう扱うか
- package 構成で module key をどう厳密化するか

## 結論

今回の branch で得られた一番重要な収穫は、実装そのものではなく、次の設計整理である。

- semantic continuity は entity の問題
- export される名前解決は public name の問題
- そのため `entity facade` と `public-name facade` を分けて考えるのがよい
- same-kind rename はこの整理でかなり自然に扱える
- kind change は別の問題として切り出すべきである

再着手するときは、この整理を出発点にした方が、今回の WIP 実装を直接育てるよりもきれいに進められるはずである。
