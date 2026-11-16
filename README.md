# vtt2txt

一款用于将 Bilibili VTT 字幕文件转换为纯文本的 Python 工具。

## 功能特点

- 将 VTT 字幕文件转换为纯文本格式
- 递归处理整个目录结构
- 保留输出目录结构
- 简单的命令行界面
- 批量转换多个文件

## 安装

本项目使用 [uv](https://github.com/astral-sh/uv) 进行依赖管理。

```bash
# 安装依赖
uv sync

# 或以开发模式安装
uv pip install -e .
```

## 使用方法

```bash
uv run python -m vtt2txt source_vtt/ target_txt/
```

参数说明：
- `source_vtt/`：包含 VTT 文件的输入目录
- `target_txt/`：转换后 TXT 文件的输出目录

## 工作原理

1. CLI 递归查找输入目录中的所有 `.vtt` 文件
2. 对于每个 VTT 文件：
   - 以 UTF-8 文本方式读取文件内容
   - 解析 VTT 格式，提取字幕文本块
   - 跳过 WEBVTT 头部和时间戳行
   - 映射输出路径并保留目录结构
   - 将纯文本内容写入对应的 TXT 文件

转换器通过以下方式提取字幕文本：
- 按空行切分字幕块（块内若出现多个时间戳则再按时间戳细分）
- 识别时间戳行（支持省略小时、`,` 作毫秒分隔符、行尾带 cue 设置等规范变体）
- 丢弃 cue 标识符、`WEBVTT` 头部元数据与 `NOTE` / `STYLE` / `REGION` 块
- 剥离内联标记（`<i>`、`<v Speaker>` 等）并解码 HTML 实体
- 以单换行连接各字幕块

## 项目结构

```
vtt2txt/
├── src/
│   └── vtt2txt/
│       ├── __init__.py      # 包初始化及版本信息
│       ├── __main__.py      # python -m vtt2txt 入口点
│       ├── cli.py           # CLI 参数解析和文件处理
│       ├── converter.py     # VTT 转 TXT 转换逻辑
│       └── path_mapper.py   # 路径转换工具
├── tests/
│   ├── unit/                # 各模块单元测试
│   └── integration/         # 完整转换集成测试
├── source_vtt/              # 示例输入目录
├── target_txt/              # 示例输出目录
├── pyproject.toml           # 项目配置
├── README.en.md             # 英文说明文档
└── README.md                # 中文说明文档
```

## 运行测试

```bash
# 运行所有测试
uv run pytest

# 带详细输出运行
uv run pytest -v
```

## Git

本项目使用 git 进行本地版本控制。初始化仓库（如需要）：

```bash
git init
git add .
git commit -m "Initial commit"
```

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件