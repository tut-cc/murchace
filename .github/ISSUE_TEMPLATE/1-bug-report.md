---
name: Bug report
about: バグの報告
title: ''
labels: 'bug'
assignees: ''
---

<!-- 簡単にバグの概要を説明してください。イシューのタイトルに収まる場合は繰り返し書かなくてもいいです。 -->

例: 処理済み商品の表示上限数を下げた後に注文を完了すると、処理済み一覧に表示されなくなることがあります。

## 再現方法

<!-- バグの再現方法をステップ毎に記述してください。 -->

例:
murchaceのバージョンv0.xで実行しました。

+ 7個注文を完了する (動作・アクション)
+ 設定画面で処理済みの商品表示数の上限を100から8に変更する (動作・アクション)
  - Web上で変更が反映されていることが確認できる (挙動・洞察)
+ 新たに注文を完了する (動作・アクション)
  - サーバのログにエラーが出る (挙動・洞察)
    ```
    IndexError: list index out of range
    ```
  - 処理済み一覧で新たに完了した注文カードが表示されない (挙動・洞察)

期待している挙動: 設定を変えた後であっても、新たに完了した注文が処理済み一覧に表示されてほしい。

<!-- 構想段階でも解決方法の目処があれば記載してください。 -->

<!-- その他、関連イシューやスクリーンショットなどがあれば記載してください。 -->