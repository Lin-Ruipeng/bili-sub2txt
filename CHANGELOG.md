# Changelog

本项目所有显著变更均记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，并遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)（0.x 阶段 minor 版本可包含破坏性变更）。

## [0.3.0] - 2026-11-18

### 安全

- **P0**：登录成功路径不再向 stderr 打印 `data.url` 与原始 `Set-Cookie`，避免明文 SESSDATA 泄漏到终端 / CI 日志（与 README 既有的脱敏承诺一致）。**建议所有 0.2.0 用户升级。**（[#7](https://github.com/Lin-Ruipeng/bili-sub2txt/issues/7)，[#8](https://github.com/Lin-Ruipeng/bili-sub2txt/pull/8)）

### 新增

- **P1**：`login` 子命令新增 `--qr-out PATH`（按扩展名写 `.png` / `.svg` 二维码图片）与 `--print-url`（仅打印登录 URL）；库层 `auth.login(on_qrcode=...)` 回调暴露二维码 URL，提供时替代默认终端渲染；stdout 为非交互终端时自动退化为打印 URL。
- **P3**：二维码过期（poll code 86038）在 `max_wait` 全局预算内自动刷新（`max_refreshes=2`，可传 `0` 复现旧行为），刷新时重触发 `on_qrcode` / 重写 `--qr-out`。
- **P4**：Windows 上 `session.json` 改用 DPAPI 加密存储（ctypes 调 `CryptProtectData`，零第三方依赖），密文绑定当前用户与机器，文件被复制到其他机器无法解密。

### 变更

- **P2**：终端二维码静默区由 1 提升至 4 模块（ISO/IEC 18004 建议）；输出以 ANSI 黑底白字固定极性，暗色主题终端下不再反色；改用半块字符（▀▄█）使二维码行数减半。
- **P4（行为变更）**：Windows 上 `session.json` 文件格式由 `{"SESSDATA": "..."}` 变为 `{"scheme": "dpapi", "data": "<base64>"}`；**旧明文文件可透明读取，升级后无需重新扫码**。外部直接解析该文件的工具会受影响。DPAPI 不可用时回退明文并输出警告；解密失败（如文件来自其他机器）视为未登录，退出码走标准的 3。
- `download` 可选依赖由 `qrcode>=7.4` 升级为 `qrcode[pil]>=7.4`：`pip install bili-sub2txt[download]` 现会安装 Pillow（用于 PNG 二维码输出）；SVG 仍零额外依赖。

### 测试

- 离线测试 137 → **159 passed**；真实链路冒烟 5/5（含真实 DPAPI 往返、`--qr-out` 产物与 B 站下发 URL 参照渲染逐字节一致、`--print-url`、旧明文 session 兼容）。

## [0.2.0] - 2026-11-17

### 新增

- 由 `bili-vtt-extractor` 重命名为 `bili-sub2txt`，版本升至 0.2.0。
- `fetch` 子命令：通过 BV 号或链接下载 B 站字幕并转 TXT（多 P 全量、`--lang` 指定语言、轨道自动选择优先级、字幕时长与视频时长交叉校验）。
- `login` 子命令：B 站 Web 端扫码登录，SESSDATA 持久化至 `session.json`。
- WBI 签名、可注入 HTTP transport（`FakeTransport` 离线测试）、统一异常与退出码体系、137 项离线测试。
- PyPI 元数据（classifiers、authors、urls）、MIT 许可证。
