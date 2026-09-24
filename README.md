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

### レシートプリンター設定

murchace は注文確定時にネットワーク経由（ESC/POS）でレシートを自動印刷する機能を備えています。  
セイコーエプソン社製のTM-T70Ⅱにて動作を確認していますが、ESC/POS に対応している他のプリンターでも動作する可能性があります。

`.env.example` をコピーして `.env` を作成し、環境に合わせて設定してください。

#### 設定項目（環境変数）

| 環境変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `MURCHACE_RECEIPT_PRINTER_HOST` | *(空文字)* | レシートプリンターの IP アドレス（未指定の場合は印刷をスキップ） |
| `MURCHACE_RECEIPT_PRINTER_PORT` | `9100` | プリンターの RAW ポート番号 |
| `MURCHACE_RECEIPT_STORE_NAME` | `murchace` | レシート上部に印字される店舗名 |
| `MURCHACE_RECEIPT_STORE_ADDRESS` | *(空文字・印字なし)* | レシート上部に印字される店舗住所 |
| `MURCHACE_RECEIPT_LOGO_PATH` | *(空文字・印字なし)* | 印字するロゴ画像のパス（未指定または見つからない場合はスキップ） |

> **Note**: プリンターの IP アドレス（`MURCHACE_RECEIPT_PRINTER_HOST`）が未設定の場合、印刷処理は自動的にスキップされ、通常の注文処理のみが実行されます。
