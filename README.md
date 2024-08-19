# murchace

このREADMEは、主に開発環境構築と実行方法について説明しています。
詳細なドキュメントは、 [docs](/docs) ディレクトリに置かれています。

## プロジェクト名について

purchase /ˈpɜː.t͡ʃəs/ 「購入する」、merchandise /ˈmɜːt͡ʃəndaɪs/ 「商品」を組み合わせ、接尾語に ace /eɪs/ 「秀でている」を充てた造語です。
マーチェス /ˈmɜːt͡ʃəs/ もしくはマーチェイス /ˈmɜːt͡ʃeɪs/ と読みます。

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
$ rye run watch
```

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
