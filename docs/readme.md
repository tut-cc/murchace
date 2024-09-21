この readme は開発者向けのドキュメントです。

- [./architecture.md]: コードベースの構造を解説
- [./style.md]: コーディングスタイルやガイドライン

---

## 開発環境のインストール

DockerとVSCodeを利用して開発環境を構築する場合は、[こちら](./docker-vscode.md)を参照してください。

[tailwindcss のインストール](https://tailwindcss.com/blog/standalone-cli)

```
$ target=linux-x64 # or linux-arm{64,v7}, macos-{arm,x}64, windows-{arm,x}64.exe
$ curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${target}
$ chmod u+x tailwindcss-${target}
$ ln -sf tailwindcss-${target} tailwindcss
```

venv 環境の構築

```
$ just sync
```

### 開発環境

テンプレートファイルの変更に応じてCSSを生成する:

```
$ just tailwind-watch
```

別のttyで、開発Webサーバーを立ち上げる:

```
$ just watch
```

## 技術スタック

murchace は htmx、Tailwind CSS、FastAPI で構築されています。
クライアントの要望に応じて、FastAPIサーバで注文情報を管理します。
UIは基本HTMLで記述します。

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

### VSCodeの拡張機能一覧

- [charliermarsh.ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff): 高速なPython LSP
- [ms-pyright.pyright](https://marketplace.visualstudio.com/items?itemName=ms-pyright.pyright): Python の型チェックに特化した LSP
  VSCode の場合はPylanceでも可
- [ms-python.debugpy](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy): Python のデバッグサポート
- [monosans.djlint](https://marketplace.visualstudio.com/items?itemName=monosans.djlint): Jinja テンプレートのリンター
- [otovo-oss.htmx-tags](https://marketplace.visualstudio.com/items?itemName=otovo-oss.htmx-tags): htmx の拡張属性の自動補完
- [CraigRBroughton.htmx-attributes](https://marketplace.visualstudio.com/items?itemName=CraigRBroughton.htmx-attributes): htmx の拡張属性の自動補完（代替プラグイン）
- [bradlc.vscode-tailwindcss](https://marketplace.visualstudio.com/items?itemName=bradlc.vscode-tailwindcss): tailwindcss の LSP

Vim、Emacs、他のエディタでの環境構築については説明を省きます。
