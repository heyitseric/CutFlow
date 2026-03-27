# 在新电脑上设置 CutFlow 开发环境

> 这份指南只需要做一次。设置完成后，日常使用只需 `git pull` 拉取最新代码。

---

## 第一步：安装 GitHub CLI 并登录

打开「终端」(Terminal) 应用，输入以下命令。

### 1.1 安装 Homebrew（Mac 软件管理工具）

如果之前没装过 Homebrew，先装它：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装完成后，如果终端提示你执行 `eval` 命令，跟着执行一次。

### 1.2 安装 GitHub CLI

```bash
brew install gh
```

### 1.3 登录 GitHub

```bash
gh auth login
```

按照提示操作：
1. 选择 **GitHub.com**
2. 选择 **HTTPS**
3. 选择 **Login with a web browser**
4. 终端会显示一个 8 位代码，复制它
5. 浏览器会自动打开 GitHub 登录页面，粘贴代码即可

完成后终端会显示 `✓ Logged in as heyitseric`。

---

## 第二步：下载项目代码

```bash
cd ~/Desktop
gh repo clone heyitseric/CutFlow
cd CutFlow
```

代码会下载到桌面的 `CutFlow` 文件夹。

---

## 第三步：安装项目依赖

```bash
./setup.sh
```

这个脚本会自动安装所有需要的东西（Python、Node.js、FFmpeg 等），可能需要几分钟。

---

## 第四步：配置 API 密钥

启动项目后（`./start.sh`），在浏览器打开 http://localhost:5173 ，进入「设置」页面填写 API 密钥。

需要填写的密钥（和家里电脑一样）：
- **ARK_API_KEY** — 火山方舟 API 密钥
- **VOLCENGINE_CAPTION_APPID** — 火山字幕 App ID
- **VOLCENGINE_CAPTION_TOKEN** — 火山字幕 Token

> 💡 建议把这些密钥存在手机备忘录或密码管理器里，方便在不同电脑上填写。

---

## 第五步：安装 Claude Code（可选）

如果你想在这台电脑上也用 Claude Code 开发：

```bash
npm install -g @anthropic-ai/claude-code
```

安装完后，在项目目录启动：

```bash
cd ~/Desktop/CutFlow
claude
```

Claude Code 会自动读取项目中的 `CLAUDE.md`，了解项目背景和工作流程。

---

## 日常使用

设置完成后，每次开工只需要：

```bash
cd ~/Desktop/CutFlow
git pull          # 拉取最新代码
./start.sh        # 启动项目
```

如果需要修 bug 或加功能，告诉 Claude Code：
> "帮我创建一个分支，我要修复 XXX 问题"

改完后：
> "/commit"

Claude Code 会自动提交代码并创建 PR。

---

## 常见问题

### `setup.sh` 报错？
确保已安装 Homebrew（第一步），然后重新运行 `./setup.sh`。

### `git pull` 说有冲突？
让 Claude Code 帮你处理：告诉它"git pull 有冲突，帮我解决"。

### 忘记 API 密钥？
启动项目后在「设置」页面可以重新填写，不影响代码。
