# DockerとVSCodeを利用した開発環境のインストール

## DockerとVSCodeのインストール

- [Docker](https://docs.docker.com/get-docker/)のインストール

```
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

- VSCodeのインストール

```
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

- VSCodeの拡張機能のインストール  
[ms-vscode-remote.remote-containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) をインストール

## 開発環境の構築
VSCodeを開いて`F1`キーを押してコマンドパレットを開き、`Remote-Containers: Clone Repository in Container Volume...`を選択して、このリポジトリ (https://github.com/tut-cc/order-notifier.git) をCloneしてください。  
拡張機能やRye、tailwindcssなどのインストールは自動で行われます。  
コンテナが起動した後、[開発環境](https://github.com/tut-cc/order-notifier?tab=readme-ov-file#%E9%96%8B%E7%99%BA%E7%92%B0%E5%A2%83) の手順に従って開発を行ってください。