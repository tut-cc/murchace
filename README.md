# order-notifier

## 開発環境のインストール

DockerとVSCodeを利用して開発環境を構築する場合は、[こちら](.devcontainer/docker-vscode.md)を参照してください。 

- [tailwindcss のインストール](https://tailwindcss.com/blog/standalone-cli)

```
$ target=linux-x64 # or linux-arm{64,v7}, macos-{arm,x}64, windows-{arm,x}64.exe
$ curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${target}
$ chmod u+x tailwindcss-${target}
$ ln -sf tailwindcss-${target} tailwindcss
```

- [rye](https://rye.astral.sh/) を用いて venv 環境の構築

```
$ rye sync --no-lock
```

### 開発環境

テンプレートファイルの変更に応じてCSSを生成する:

```
$ rye run tailwind-watch
```

別のttyで、開発Webサーバーを立ち上げる:

```
$ source .venv/bin/activate
$ rye run watch
```

- /docs でAPIの仕様が見れて、リクエストを投げることもできる
- /orders が（今の所）メインの画面

#### VSCodeの拡張機能一覧

- [otovo-oss.htmx-tags](https://marketplace.visualstudio.com/items?itemName=otovo-oss.htmx-tags): htmx の拡張属性の自動補完
- [CraigRBroughton.htmx-attributes](https://marketplace.visualstudio.com/items?itemName=CraigRBroughton.htmx-attributes): htmx の拡張属性の自動補完（代替プラグイン）
- [bradlc.vscode-tailwindcss](https://marketplace.visualstudio.com/items?itemName=bradlc.vscode-tailwindcss): tailwindcss の LSP
- [ms-pyright.pyright](https://marketplace.visualstudio.com/items?itemName=ms-pyright.pyright): Python の型チェックに特化した LSP
- [charliermarsh.ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff): 高速なPython LSP
- [monosans.djlint](https://marketplace.visualstudio.com/items?itemName=monosans.djlint): Jinja テンプレートのリンター

Vim、Emacs、他のエディタでの環境構築については説明を省きます。

### 本番環境

```
$ rye run tailwind-build
$ rye run serve
```

## 参考リンク

htmx

- https://htmx.org/docs/

tailwindcss

- https://tailwindcss.com/docs/utility-first

Python

- https://fastapi.tiangolo.com/
- https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html
- https://www.encode.io/databases/
- https://docs.sqlalchemy.org/en/20/core/
- https://jinja.palletsprojects.com/en/3.1.x/
