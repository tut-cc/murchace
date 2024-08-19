## murchace とは

以下に挙げる目的を達成するための、注文管理Webシステム。

- 誰が何の商品を買ったかを把握
- 提供待ちキューを賢く捌く
- 商品ごとの売上を即座に知る

## 技術スタック

murchace は htmx、Tailwind CSS、FastAPI で構築されている。
クライアントの要望に応じて、FastAPIサーバで注文情報を管理する。
UIは基本HTMLで記述する。

## パス操作一覧

### `/`

ホーム。
他リソースへのハイパーリンクを列挙する。

### `/orders`

新規注文のリソース。
`/orders/{session_id}` と `/orders/{session_id}/item/` に対する操作で注文セッションを管理する。

### `/placements`

`/orders` で確定した注文に関するリソース。
提供待ち、受け渡し済みどちらも確定注文に含まれる。

### `/products` (未実装)

商品に関するリソース。
商品の追加・削除、名前・画像・値段・在庫の変更が可能。

### `/settings` (未実装)

システムの詳細な設定に関するリソース。

## 参考リンク

- FastAPI: https://fastapi.tiangolo.com/ja/ (日本語)
- FastAPI: https://fastapi.tiangolo.com/ (English)
- Pythonの型チートシート: https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html (English)
- テンプレート言語: https://jinja.palletsprojects.com/en/3.1.x/ (English)
- Tailwind CSS: https://tailwindcss.com/docs/utility-first (English)
- htmx: https://htmx.org/docs/ (English)
- 非同期データベースライブラリ: https://www.encode.io/databases/ (English)
- SQLのドメイン固有言語: https://docs.sqlalchemy.org/en/20/core/ (English)
