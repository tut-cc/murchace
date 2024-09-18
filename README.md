## murchace

murchace は以下の機能を~~備えた~~実装しようとしている注文管理 Web システムです。

- 誰が何の商品を買ったかを把握
- 提供待ちキューを賢く捌く
- 売上を即座に知る

開発者向けのドキュメントは、 [docs](/docs) を参照してください。

### プロジェクト名について

purchase /ˈpɜː.t͡ʃəs/ 「購入する」、merchandise /ˈmɜːt͡ʃəndaɪs/ 「商品」を組み合わせ、接尾語に ace /eɪs/ 「秀でている」を充てた造語です。
マーチェス /ˈmɜːt͡ʃəs/ もしくはマーチェイス /ˈmɜːt͡ʃeɪs/ と読みます。

### 実行方法

Python のパッケージマネージャ [uv](https://github.com/astral-sh/uv) と、CLIツール [just](https://github.com/casey/just) のインストールが必要です。
どちらもインストールが終わった後に、次のコマンドを実行すると Web サーバが起動します:

```console
$ just run
```

別の実行方法として、コンテナを利用する場合は以下のコマンドを実行してください:

```console
$ sudo dnf install podman
$ podman volume create murchace-db
$ podman run -d --name murchace -p 8000:8000 -v murchace-db:/murchace/db ghcr.io/tut-cc/murchace:main
```
