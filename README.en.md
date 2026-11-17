# bili-sub2txt

A Python tool to convert Bilibili subtitles to plain text. Supports both local VTT file batch conversion and direct download from Bilibili via BV number.

## Features

- Convert VTT subtitle files to plain text (strip timestamps and markup)
- Download Bilibili subtitles directly via BV number or video URL (requires login)
- QR-code login with persistent session
- Multi-part video support — all pages downloaded with indexed filenames
- Language selection (`--lang`); lists all available tracks when not found
- Automatic track selection (human Chinese > AI Chinese > human English > AI English)
- Recursive directory processing with preserved output structure
- VTT parser accepts spec variants (optional hours, comma separator, cue settings)

## Installation

```bash
# Basic install (local VTT conversion only, zero third-party dependencies)
pip install -e .

# With download support (installs qrcode for terminal QR rendering)
pip install -e ".[download]"

# Development mode (includes pytest)
pip install -e ".[dev]"
```

## Usage

### Convert local VTT files

```bash
bili-sub2txt convert source_vtt/ target_txt/
```

- `source_vtt/`: input directory containing `.vtt` files (searched recursively)
- `target_txt/`: output directory for TXT files (auto-created, structure preserved)

### Download from Bilibili

```bash
# First-time use requires QR-code login
bili-sub2txt login

# Download by BV number
bili-sub2txt fetch BV1jJ4m1J7ba

# Download by full URL
bili-sub2txt fetch https://www.bilibili.com/video/BV1jJ4m1J7ba/

# Specify output directory and subtitle language
bili-sub2txt fetch BV1jJ4m1J7ba --output my_output/ --lang zh-Hans
```

**fetch options:**
- `target`: BV number or video URL (required)
- `-o, --output DIR`: output directory (default `target_txt/`, creates `<BV>/` inside)
- `--lang LAN`: subtitle language (e.g. `zh-Hans`, `ai-zh`, `ja`; auto-selected if omitted)

### Other

```bash
bili-sub2txt --help       # show help
bili-sub2txt --version    # show version
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic failure (no subtitles, network error, etc.) |
| 2 | Usage error |
| 3 | Login required / session expired |

## How it works

### VTT conversion (convert)

1. The CLI recursively finds all `.vtt` files in the input directory
2. Parses VTT: splits on blank lines into cues (further split on timestamps), drops cue identifiers / NOTE / STYLE / REGION blocks, strips inline markup and decodes HTML entities
3. Joins subtitle blocks with single newlines and writes to corresponding TXT files

### Bilibili download (fetch + login)

1. `login`: calls Bilibili's Web QR-code login API, renders QR in terminal, extracts `SESSDATA` on success and persists to config file
2. `fetch`: parses BV → fetches video info → for each page requests subtitle list → selects track → downloads JSON → converts to plain text → writes file
3. Duration cross-check (subtitle last `to` vs video `duration`, 0.5–1.25× range) — warns but does not block

## Project structure

```
bili-sub2txt/
├── src/bili_sub2txt/
│   ├── __init__.py          # version
│   ├── __main__.py          # python -m bili_sub2txt entry
│   ├── cli.py               # argparse subcommands (convert/fetch/login)
│   ├── converter.py         # VTT-to-TXT + Bilibili-JSON-to-TXT
│   ├── path_mapper.py       # path mapping
│   ├── errors.py            # exceptions, exit codes, SESSDATA redaction
│   ├── naming.py            # filename sanitisation
│   └── bilibili/
│       ├── net.py           # HTTP transport (injectable for offline testing)
│       ├── wbi.py           # WBI signature
│       ├── session.py       # SESSDATA persistence
│       ├── auth.py          # QR-code login state machine
│       ├── api.py           # video info, subtitle tracks, download
│       └── fetcher.py       # fetch orchestration and duration check
├── tests/
│   ├── conftest.py          # FakeTransport test fixture
│   ├── unit/                # unit tests
│   └── integration/         # integration tests
├── source_vtt/              # sample VTT files
├── pyproject.toml           # project config
├── README.en.md             # English docs
└── README.md                # Chinese docs
```

## Running tests

```bash
pip install -e ".[dev]"
pytest              # run all tests
pytest -v           # verbose output
```

All tests run offline (`FakeTransport` mock) — no real network or credentials required.

## Security

- `SESSDATA` is equivalent to your Bilibili account login — treat as a high-sensitivity credential
- Session is stored at `~/.config/bili-sub2txt/session.json` (Windows: `%APPDATA%/bili-sub2txt/session.json`), containing only SESSDATA, with best-effort `0600` permissions
- SESSDATA is sent only via the Cookie header, never in URLs; automatically redacted in logs and error messages
- On Windows, file permission protection is limited — mind the directory ACL

## Disclaimer

This is an unofficial tool that uses Bilibili's internal Web APIs, which may change at any time. Subtitle copyright belongs to Bilibili and the content creators. AI subtitle accuracy is limited. For personal study and note-taking only. Users must comply with Bilibili's terms of service.

## License

MIT License - see [LICENSE](LICENSE)
