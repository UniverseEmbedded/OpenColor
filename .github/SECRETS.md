# GitHub Actions Secrets 配置说明

本文档说明发布工作流所需的 Secrets 配置。

## 必需的 Secrets

### 基础权限

| Secret 名称 | 说明 | 如何获取 |
|------------|------|---------|
| `GITHUB_TOKEN` | 自动提供，无需手动配置 | GitHub 自动生成 |

### Tauri 自动更新签名

| Secret 名称 | 说明 | 如何获取 |
|------------|------|---------|
| `TAURI_SIGNING_PRIVATE_KEY` | Tauri 更新私钥 | 运行 `tauri signer generate` 生成 |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | 私钥密码（可选） | 生成密钥时设置的密码 |

生成命令：
```bash
cd web
npx tauri signer generate
```

### Windows 代码签名（可选）

| Secret 名称 | 说明 | 如何获取 |
|------------|------|---------|
| `WINDOWS_CERTIFICATE` | Base64 编码的 PFX 证书 | 从证书颁发机构购买 |
| `WINDOWS_CERTIFICATE_PASSWORD` | 证书密码 | 导出证书时设置 |

### macOS 代码签名（可选）

| Secret 名称 | 说明 | 如何获取 |
|------------|------|---------|
| `MACOS_CERTIFICATE` | Base64 编码的 P12 证书 | Apple Developer 后台下载 |
| `MACOS_CERTIFICATE_PASSWORD` | 证书密码 | 导出证书时设置 |
| `KEYCHAIN_PASSWORD` | 临时钥匙串密码 | 任意设置 |
| `MACOS_TEAM_ID` | Apple Team ID | Apple Developer 后台查看 |
| `MACOS_APPLE_ID` | Apple ID | 你的 Apple 账号 |
| `MACOS_APP_PASSWORD` | App 专用密码 | Apple ID 设置中生成 |

### 通知（可选）

| Secret 名称 | 说明 | 如何获取 |
|------------|------|---------|
| `DISCORD_WEBHOOK` | Discord Webhook URL | Discord 服务器设置中创建 |

## 配置步骤

1. 进入 GitHub 仓库页面
2. 点击 Settings -> Secrets and variables -> Actions
3. 点击 "New repository secret"
4. 输入 Secret 名称和值
5. 点击 "Add secret"

## 测试发布

配置完成后，可以通过以下方式测试：

### 方式一：推送标签
```bash
git tag v0.1.0
git push origin v0.1.0
```

### 方式二：手动触发
1. 进入 GitHub 仓库 Actions 页面
2. 选择 "Release" 工作流
3. 点击 "Run workflow"
4. 输入版本号（如 0.1.0）
5. 选择是否为预发布版本
6. 点击 "Run workflow"
