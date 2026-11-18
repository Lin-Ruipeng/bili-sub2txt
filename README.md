# bili-sub2txt

一款用于将 Bilibili 字幕转换为纯文本的 Python 工具。支持本地 VTT 文件批量转换，也可通过 BV 号直接下载 B 站字幕并转换。

## 功能特点

- 将 VTT 字幕文件转换为纯文本格式（去时间戳、去标记）
- 通过 BV 号或视频链接直接下载 B 站字幕（需登录）
- 扫码登录 B 站，登录态自动持久化
- 支持多 P 视频全量下载，文件名带序号前缀
- 支持指定字幕语言（`--lang`），未命中时列出所有可用轨道
- 字幕轨道自动选择（优先人工中文 → AI 中文 → 人工英文 → AI 英文）
- 递归处理整个目录结构，保留输出目录层级
- VTT 解析兼容规范变体（省略小时、逗号分隔符、cue 设置等）

## 安装

```bash
# 基础安装（仅本地 VTT 转换，零第三方依赖）
pip install -e .

# 含下载功能（安装 qrcode 用于终端渲染二维码）
pip install -e ".[download]"

# 开发模式（含 pytest）
pip install -e ".[dev]"
```

## 使用方法

### 转换本地 VTT 文件

```bash
bili-sub2txt convert source_vtt/ target_txt/
```

- `source_vtt/`：含 `.vtt` 文件的输入目录（递归查找）
- `target_txt/`：TXT 输出目录（自动创建，保留目录结构）

### 下载 B 站字幕

```bash
# 首次使用需扫码登录
bili-sub2txt login

# 无终端图形/自动化环境：把二维码写为图片文件（.png 需 qrcode[pil]，.svg 零依赖）
bili-sub2txt login --qr-out login_qr.svg

# 或仅打印登录 URL
bili-sub2txt login --print-url

# 通过 BV 号下载
bili-sub2txt fetch BV1jJ4m1J7ba

# 通过完整链接下载
bili-sub2txt fetch https://www.bilibili.com/video/BV1jJ4m1J7ba/

# 指定输出目录和字幕语言
bili-sub2txt fetch BV1jJ4m1J7ba --output my_output/ --lang zh-Hans
```

**fetch 参数：**
- `target`：BV 号或视频链接（必需）
- `-o, --output DIR`：输出目录（默认 `target_txt/`，在其下建 `<BV号>/`）
- `--lang LAN`：指定字幕语言（如 `zh-Hans`、`ai-zh`、`ja`；未指定时自动选择）

### 其他

```bash
bili-sub2txt --help       # 查看帮助
bili-sub2txt --version    # 查看版本
```

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 一般失败（无字幕、网络错误等） |
| 2 | 用法错误 |
| 3 | 需要登录 / 登录态失效 |

## 工作原理

### VTT 转换（convert）

1. CLI 递归查找输入目录中的所有 `.vtt` 文件
2. 解析 VTT 格式：按空行切分字幕块（块内多个时间戳再细分），丢弃 cue 标识符/`NOTE`/`STYLE`/`REGION` 块，剥离内联标记并解码 HTML 实体
3. 以单换行连接各字幕块，写入对应的 TXT 文件

### B 站下载（fetch + login）

1. `login`：调用 B 站 Web 端扫码登录接口，终端渲染二维码，扫码成功后提取 `SESSDATA` 并保存到配置文件。支持 `--qr-out PATH`（二维码写为 `.png`/`.svg` 图片）与 `--print-url`（仅打印登录 URL）；stdout 为非交互终端（管道/CI）时自动退化为打印 URL。库层可通过 `auth.login(on_qrcode=callback)` 获取登录 URL 自行渲染
2. `fetch`：解析 BV 号 → 获取视频信息 → 对每个分 P 请求字幕列表 → 选择轨道 → 下载 JSON → 转换为纯文本 → 写入文件
3. 字幕时长与视频时长交叉校验（0.5–1.25 倍区间），超出则告警但不阻断

## 项目结构

```
bili-sub2txt/
├── src/bili_sub2txt/
│   ├── __init__.py          # 版本信息
│   ├── __main__.py          # python -m bili_sub2txt 入口
│   ├── cli.py               # argparse 子命令（convert/fetch/login）
│   ├── converter.py         # VTT 转 TXT + B站 JSON 转 TXT
│   ├── path_mapper.py       # 路径转换工具
│   ├── errors.py            # 异常体系、退出码、SESSDATA 脱敏
│   ├── naming.py            # 文件名清洗与输出路径构造
│   └── bilibili/
│       ├── net.py           # HTTP transport（可注入，支持离线测试）
│       ├── wbi.py           # WBI 签名
│       ├── session.py       # SESSDATA 持久化
│       ├── auth.py          # 扫码登录状态机
│       ├── qr_output.py     # 登录二维码图片输出（--qr-out）
│       ├── api.py           # 视频信息、字幕轨道、下载
│       └── fetcher.py       # fetch 编排与时长校验
├── tests/
│   ├── conftest.py          # FakeTransport 测试 fixture
│   ├── unit/                # 单元测试
│   └── integration/         # 集成测试
├── source_vtt/              # 示例 VTT 文件
├── pyproject.toml           # 项目配置
├── README.en.md             # 英文文档
└── README.md                # 中文文档
```

## 运行测试

```bash
pip install -e ".[dev]"
pytest              # 运行所有测试
pytest -v           # 详细输出
```

所有测试离线运行（`FakeTransport` mock），不依赖真实网络与凭据。

## 安全说明

- `SESSDATA` 等同 B 站账号登录态，属于高敏凭据
- 登录态存储在 `~/.config/bili-sub2txt/session.json`（Windows 为 `%APPDATA%/bili-sub2txt/session.json`），仅含 SESSDATA，尽力设 `0600` 权限
- SESSDATA 只走 Cookie 请求头，绝不拼入 URL；日志和报错中自动脱敏
- 配置文件权限在 Windows 上保护有限，建议注意目录 ACL

## 免责声明

本工具为非官方项目，使用 B 站 Web 端内部接口，接口可能随时变更。字幕版权归 B 站与创作者所有，AI 字幕准确度有限，仅供个人学习与笔记使用。用户须自行遵守 B 站用户协议。

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件
