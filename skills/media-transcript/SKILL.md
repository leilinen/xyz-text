---
name: media_transcript
description: Transcribe and summarize media links (Bilibili, YouTube, Xiaoyuzhou podcasts) with auto Feishu sync.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires":
          {
            "bins": ["ssh", "python3", "yt-dlp", "ffmpeg"],
            "config": ["llm_api_key", "feishu_app_id", "feishu_app_secret"],
            "env": ["MEDIA_TRANSCRIPT_HOST", "MEDIA_TRANSCRIPT_PATH"],
          },
      },
  }
---

# Media Transcript

Transcribe media links, generate structured summaries (with entity extraction), and publish to Feishu documents.

## Constraints

- **Do NOT modify any source code** in `$MEDIA_TRANSCRIPT_PATH/`. This skill only invokes `media_processor.py` via SSH. If the script fails, report the error to the user — never attempt to edit, patch, or fix the code on the target machine.

## When to use (trigger phrases)

Use this skill immediately when the user asks any of:

- Shares a Bilibili, YouTube, or Xiaoyuzhou URL
- "Transcribe this video/podcast"
- "Summarize this link"
- "What's this video about?"
- Any message containing a URL from: `bilibili.com`, `b23.tv`, `youtube.com`, `youtu.be`, `xiaoyuzhoufm.com`

## Quick start

This skill runs remotely via SSH. The target machine must have xyz-text installed with all dependencies.

Required environment variables (set at install time):
- `MEDIA_TRANSCRIPT_HOST` — SSH target, e.g. `user@192.168.1.100`
- `MEDIA_TRANSCRIPT_PATH` — absolute path to xyz-text on the target, e.g. `/home/user/xyz-text`

```bash
ssh "$MEDIA_TRANSCRIPT_HOST" "cd $MEDIA_TRANSCRIPT_PATH && python3 media_processor.py '<url>'"
```

The command outputs JSON to stdout with the transcript, summary, entities, and Feishu link.

## Supported platforms

| Platform | URL patterns | Subtitles | ASR fallback |
|----------|-------------|-----------|-------------|
| YouTube | `youtube.com/watch?v=`, `youtu.be/` | Auto captions | SenseVoice |
| Bilibili | `bilibili.com/video/BV`, `b23.tv/` | - | SenseVoice |
| Xiaoyuzhou | `xiaoyuzhoufm.com/episode/` | - | SenseVoice |

## Processing pipeline

1. **Platform resolution** — identify URL platform via adapter registry
2. **Subtitle extraction** — yt-dlp with platform-specific args (YouTube only)
3. **ASR fallback** — audio download via yt-dlp, then SenseVoice transcription
4. **ASR refine** — LLM-based error correction + paragraph segmentation (ASR sources only)
5. **Text cleaning** — clean, segment, paragraph splitting
6. **Structured summary** — LLM generates title, one-line summary, topics, key points, quotes, entities
7. **Hot comments** — fetch top comments (YouTube/Bilibili/Xiaoyuzhou)
8. **Output** — save Markdown (YAML frontmatter) + JSON result
9. **Feishu publish** — create Feishu doc with entities, summary, comments, transcript

## Flags

| Flag | Description |
|------|-------------|
| `--no-feishu` | Skip Feishu document publishing |
| `--no-cleanup` | Keep temporary files for debugging |
| `--no-summary` | Skip AI summarization |
| `--output PATH` | Save raw transcript to file |
| `--retry FILE` | Retry Feishu upload from a saved JSON result |

### Examples

```bash
# Process and publish to Feishu (default)
ssh "$MEDIA_TRANSCRIPT_HOST" "cd $MEDIA_TRANSCRIPT_PATH && python3 media_processor.py 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'"

# Transcribe only, no Feishu
ssh "$MEDIA_TRANSCRIPT_HOST" "cd $MEDIA_TRANSCRIPT_PATH && python3 media_processor.py 'https://www.bilibili.com/video/BV1GJ411x7h7' --no-feishu"

# Skip summary (no API key needed)
ssh "$MEDIA_TRANSCRIPT_HOST" "cd $MEDIA_TRANSCRIPT_PATH && python3 media_processor.py 'https://www.xiaoyuzhoufm.com/episode/abc123' --no-summary"
```

## Output format

Successful response (JSON to stdout):

```json
{
  "ok": true,
  "result": {
    "platform": "youtube",
    "url": "https://...",
    "title": "Video Title",
    "transcript": "Full transcript text...",
    "summary": {
      "title": "Generated Title",
      "one_line_summary": "One-sentence summary of the content",
      "summary": "Structured summary...",
      "topics": ["topic1", "topic2"],
      "key_points": ["point1", "point2"],
      "quotes": ["notable quote 1", "notable quote 2"],
      "entities": [
        {"name": "Person Name", "type": "person", "context": "mentioned in discussion about X"},
        {"name": "Book Title", "type": "book", "context": "recommended reading"}
      ]
    },
    "feishu": {
      "doc_token": "abc123",
      "url": "https://open.feishu.cn/..."
    }
  }
}
```

Error response:

```json
{
  "ok": false,
  "error": "Error message",
  "error_type": "ConfigError"
}
```

## Entity types

Extracted entities are categorized as:

| Type | Description | Examples |
|------|-------------|---------|
| `person` | People mentioned | 尼采, 巴菲特, 塔勒布 |
| `organization` | Organizations | 中信出版社, 高盛 |
| `book` | Books or publications | 《道德经》, 《反脆弱》 |

## Error handling

| Error | Cause | Fix |
|-------|-------|-----|
| `ConfigError` | Missing `config.json` or required fields | Ensure `config.json` exists with `llm_api_key` and Feishu credentials |
| `UnsupportedPlatformError` | URL doesn't match any platform | Check the URL is from a supported platform |
| `ASRError` | Audio transcription failed | Try `--no-cleanup` to inspect audio files, check ffmpeg installation |
| `FeishuAPIError` | Feishu upload failed | Use `--retry result.json` to retry from saved data |

## Configuration

`config.json` lives on the target machine at `$MEDIA_TRANSCRIPT_PATH/config.json`. Key required fields:

```json
{
  "llm_base_url": "https://api.openai.com/v1",
  "llm_api_key": "<key>",
  "llm_model": "gpt-4o",
  "feishu_app_id": "<id>",
  "feishu_app_secret": "<secret>"
}
```

Optional but recommended:

- `feishu_share_user_id` — auto-share published docs with this user
- `refine_max_chars` — max chars per batch for ASR refine (default: 8000)
- `sensevoice_device` — `mps` (macOS), `cuda` (GPU), or `cpu`

Legacy config (`llm_backend` + backend-specific fields like `zhipu_api_key`, `ollama_base_url`) is still supported with automatic mapping.
