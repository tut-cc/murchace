[![CI](https://github.com/tut-cc/murchace/actions/workflows/CI.yaml/badge.svg)](https://github.com/tut-cc/murchace/actions/workflows/CI.yaml)

## murchace

murchace は以下の機能を備えた注文管理 Web システムです。

- 誰が何の商品を買ったかを把握
- 提供待ちキューを賢く捌く
- 売上を即座に知る

開発者向けのドキュメントは、 [docs](/docs) を参照してください。

### プロジェクト名について

purchase /ˈpɜː.t͡ʃəs/ 「購入する」、merchandise /ˈmɜːt͡ʃəndaɪs/ 「商品」を組み合わせ、接尾語に ace /eɪs/ 「秀でている」を充てた造語です。
マーチェス /ˈmɜːt͡ʃəs/ もしくはマーチェイス /ˈmɜːt͡ʃeɪs/ と読みます。

### 実行方法

Python のパッケージマネージャ [uv](https://github.com/astral-sh/uv) のインストールが必要です。
インストールが終わった後に、次のコマンドを実行すると Web サーバが起動します:

```console
$ uv run --frozen doit serve
```

別の実行方法として、[podman](https://podman.io/) でコンテナを利用する場合は以下のコマンドを実行してください:

```console
$ podman volume create murchace-db
$ podman run -d --name murchace -p 8000:8000 -v murchace-db:/murchace/db ghcr.io/tut-cc/murchace:main
```
