この readme は開発者向けのドキュメントです。

- [architecture.md](./architecture.md): コードベースの構造を解説
- [style.md](./style.md): コーディングスタイルやガイドライン

---

## 開発環境の構築

### Docker & VSCode で環境構築

ローカルで開発したい場合は [ローカルで環境構築](#ローカルで環境構築) を参照してください。

- [Docker](https://docs.docker.com/get-docker/) のインストール

```sh
## Windows
winget install Docker.DockerDesktop

## macOS
brew install --cask docker

## Debian/Ubuntu
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/{debian,ubuntu}/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/{debian,ubuntu} \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

## Fedora/CentOS/RHEL
sudo dnf remove docker docker-client docker-client-latest docker-common docker-latest \
                docker-latest-logrotate docker-logrotate docker-engine podman runc
sudo dnf config-manager --add-repo https://download.docker.com/linux/{fedora,centos,rhel}/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

- VSCode のインストール

```sh
## Windows
winget install Microsoft.VisualStudioCode

## macOS
brew install --cask visual-studio-code

## Debian/Ubuntu
curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
sudo install -o root -g root -m 644 microsoft.gpg /etc/a[pt/trusted.gpg.d/
sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt-get install apt-transport-https
sudo apt-get update
sudo apt-get install code

## Fedora/CentOS/RHEL
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo sh -c 'echo -e "[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" > /etc/yum.repos.d/vscode.repo'
sudo dnf check-update
sudo dnf install code
```

- VSCode を開いて拡張機能の [ms-vscode-remote.remote-containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) をインストール

- `F1` キーを押してコマンドパレットを開く。`Remote-Containers: Clone Repository in Container Volume...` を実行し、このリポジトリ (https://github.com/tut-cc/murchace.git) 選んで Clone する。すると、拡張機能や依存ライブラリが自動でインストールされる。

テンプレートファイルへの CSS の変更を反映させたいときは、`just tailwind-watch` もしくは `just tw` を実行してください。変更を保存すると自動的に CSS を再生成します。

`just watch` もしくは `just w` を実行すると開発 Web サーバーが立ち上がります。Python ファイルに変更を加えると、サーバが自動的に再起動します。

### ローカルで環境構築

Python のパッケージマネージャ [uv](https://github.com/astral-sh/uv) と、CLIツール [just](https://github.com/casey/just) のインストールが必要です。どちらもインストールが終わったら、次のコマンドを実行してください。

```console
$ git clone tut-cc/murchace.git && cd murchace
$ just dev
```

テンプレートファイルへの CSS の変更を反映させたいときは、`just tailwind-watch` もしくは `just tw` を実行してください。変更を保存すると自動的に CSS を再生成します。

`just watch` もしくは `just w` を実行すると開発 Web サーバーが立ち上がります。Python ファイルに変更を加えると、サーバが自動的に再起動します。

## 技術スタック

murchace は htmx、Tailwind CSS、FastAPI で構築されています。
クライアントの要望に応じて、FastAPI サーバで注文情報を管理します。
UI は基本 HTML で記述します。

### 参考リンク

- FastAPI: https://fastapi.tiangolo.com/ja/ (日本語)
- FastAPI: https://fastapi.tiangolo.com/ (English)
- Python の型チートシート: https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html (English)
- テンプレート言語: https://jinja.palletsprojects.com/en/3.1.x/ (English)
- Tailwind CSS: https://tailwindcss.com/docs/utility-first (English)
- htmx: https://htmx.org/docs/ (English)
- 非同期データベースライブラリ: https://www.encode.io/databases/ (English)
- SQL のドメイン固有言語: https://docs.sqlalchemy.org/en/20/core/ (English)

## VSCode の拡張機能一覧

- [charliermarsh.ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff): 高速な Python LSP
- [ms-pyright.pyright](https://marketplace.visualstudio.com/items?itemName=ms-pyright.pyright): Python の型チェックに特化した LSP (VSCode の場合は Pylance でも可)
- [ms-python.debugpy](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy): Python のデバッグサポート
- [monosans.djlint](https://marketplace.visualstudio.com/items?itemName=monosans.djlint): Jinja テンプレートのリンター
- [otovo-oss.htmx-tags](https://marketplace.visualstudio.com/items?itemName=otovo-oss.htmx-tags): htmx の拡張属性の自動補完
- [CraigRBroughton.htmx-attributes](https://marketplace.visualstudio.com/items?itemName=CraigRBroughton.htmx-attributes): htmx の拡張属性の自動補完（代替プラグイン）
- [bradlc.vscode-tailwindcss](https://marketplace.visualstudio.com/items?itemName=bradlc.vscode-tailwindcss): Tailwind CSS の LSP

Vim、Emacs、その他のエディタでの環境構築については説明を省きます。
