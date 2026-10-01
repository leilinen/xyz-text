# Media Transcript Skill

自动转录与总结媒体链接的工具，支持视频下载。支持 Bilibili、YouTube、小宇宙播客，优先提取字幕后回退到 SenseVoice ASR，生成结构化总结并发布到飞书文档。也支持直接下载 Bilibili / YouTube 视频（含播放列表/合集）。

## 两种模式

| 模式 | 说明 | 默认 |
|------|------|------|
| `transcript` | 完整流水线：字幕提取/ASR → 清洗 → LLM 总结 → 飞书发布 | 是 |
| `download` | 仅下载视频文件，不进行转录或总结 | 否 |

通过 `--mode` 参数选择模式。

## 功能流程

### 转录模式（默认）

1. 识别 URL 对应的平台（Bilibili / YouTube / 小宇宙）
2. 优先使用 `yt-dlp` 提取字幕
3. 无字幕时下载音频，使用 SenseVoice 进行 ASR 转录
4. ASR 文本经 LLM 纠错+分段（修正同音错字、漏字、多字，按话题分段）
5. 清洗转录文本，按句子边界自动分段
6. 调用 LLM 生成结构化总结（一句话摘要、主题、要点、金句、实体提取）
7. 提取热门评论（YouTube / Bilibili / 小宇宙）
8. 保存 Markdown 文件（YAML frontmatter + 结构化内容）
9. 发布到飞书文档（含实体、热门评论区段）
10. 输出统一 JSON 结果

### 下载模式

1. 识别 URL 对应的平台
2. 自动检测是否为播放列表/合集
3. 使用 yt-dlp 下载最佳画质视频（合并为 MP4）
4. 输出下载结果 JSON

## 快速开始

### 依赖安装

```bash
# 基础依赖
pip install yt-dlp ffmpeg-python requests pytest openai pyyaml

# ASR 依赖（SenseVoice）
pip install funasr torchaudio modelscope

# 系统工具
brew install ffmpeg  # macOS
```

首次运行时 SenseVoice 模型会自动从 ModelScope 下载缓存到 `~/.cache/modelscope/`。

### 配置

复制 `config.json` 并填入必要信息：

```json
{
  "work_dir": "/tmp/media_tool_work",
  "temp_dir": "/tmp/media_tool_work/tmp",
  "sensevoice_model_path": null,
  "sensevoice_device": "mps",
  "sensevoice_language": "auto",
  "llm_base_url": "https://api.openai.com/v1",
  "llm_api_key": "<your-key>",
  "llm_model": "gpt-4o",
  "llm_max_tokens": 4096,
  "llm_timeout": 120,
  "feishu_app_id": "<your-id>",
  "feishu_app_secret": "<your-secret>",
  "feishu_share_user_id": "<your-user-id>",
  "log_level": "INFO",
  "log_output": "file",
  "log_file": "media_tool.log",
  "summary_max_chars": 12000,
  "refine_max_chars": 8000,
  "cleaner_segment_length": 800,
  "cleaner_min_sentence_length": 20,
  "cleaner_paragraph_length": 400,
  "request_timeout": 900,
  "llm_max_retries": 3,
  "llm_retry_delay": 2.0
}
```

### LLM 配置

采用统一的 OpenAI 兼容 API 配置，支持任何兼容 `/v1/chat/completions` 的服务：

```json
{
  "llm_base_url": "https://api.openai.com/v1",
  "llm_api_key": "<your-key>",
  "llm_model": "gpt-4o"
}
```

兼容旧版 `llm_backend` + 后端专属字段配置（自动映射）：

| 旧版 `llm_backend` | 映射到 |
|---------------------|--------|
| `zhipu` | `llm_base_url` = 智谱 API, `llm_model` = `glm_model` |
| `ollama` | `llm_base_url` = `ollama_base_url`, `llm_model` = `ollama_model` |
| `openai` | 直接使用 `openai_*` 字段 |

所有 LLM 调用共享自动重试机制（指数退避），通过 `llm_max_retries` 和 `llm_retry_delay` 配置。

**必填项：**
- `llm_base_url` / `llm_api_key` / `llm_model` — LLM 服务配置
- `feishu_app_id` / `feishu_app_secret` — 用于飞书文档发布

**可选项：**
- `sensevoice_model_path` — 模型本地路径，`null` 时自动下载
- `sensevoice_device` — 推理设备：`mps`（macOS）/ `cuda`（GPU）/ `cpu`
- `feishu_share_user_id` — 文档发布后自动分享给该用户
- `refine_max_chars` — ASR 纠错分段的单批次最大字符数（默认 8000）
- `yt_dlp_cookies_file` — yt-dlp 使用的 Netscape 格式 cookie 文件（项目根目录 `cookies.txt`），提供 YouTube 登录态，优先于浏览器模式
- `yt_dlp_cookies_from_browser` — 从浏览器读取 cookie（如 `edge:Default`），macOS 首次使用会弹钥匙串授权窗

### 运行

```bash
# 转录模式（默认）
python3 media_processor.py "https://www.youtube.com/watch?v=abc123"

# 下载单个视频
python3 media_processor.py "https://www.youtube.com/watch?v=abc123" --mode download

# 下载视频到指定目录
python3 media_processor.py "https://www.bilibili.com/video/BV1xx..." --mode download -o ~/Downloads

# 下载播放列表/合集（自动检测）
python3 media_processor.py "https://www.youtube.com/playlist?list=PL..." --mode download -o ~/Downloads/playlist

# 跳过飞书发布（转录模式）
python3 media_processor.py "URL" --no-feishu

# 保留临时文件（调试用）
python3 media_processor.py "URL" --no-cleanup

# 跳过 AI 总结
python3 media_processor.py "URL" --no-summary

# 保存转录文本到文件（转录模式）
python3 media_processor.py "URL" -o transcript.txt

# 从已保存的 JSON 重试飞书上传
python3 media_processor.py --retry result.json
```

**注意：** 始终从仓库根目录运行，确保 `src/` 路径可解析。

## 支持平台

| 平台 | URL 示例 | 字幕 | ASR | 热门评论 | 视频下载 | 播放列表 |
|------|----------|------|-----|----------|----------|----------|
| YouTube | `youtu.be/xxx` / `youtube.com/watch?v=xxx` / `youtube.com/playlist?list=xxx` | 自动字幕 | SenseVoice | yt-dlp | 支持 | 支持 |
| Bilibili | `b23.tv/xxx` / `bilibili.com/video/BVxxx` | - | SenseVoice | API 直接获取 | 支持 | 支持（合集/多P） |
| 小宇宙 | `xiaoyuzhoufm.com/episode/xxx` | - | SenseVoice | SSR HTML 解析 | - | - |

## 项目结构

```
src/media_tool/
  core/            — 配置、数据模型、错误类与通用工具
  platforms/       — 平台适配器（Bilibili / YouTube / 小宇宙）
  ingestion/       — 字幕提取、视频元数据、SenseVoice ASR、视频下载
  text/            — 文本清洗、分段、LLM 总结与 ASR 纠错分段
  enrichment/      — 热门评论与小宇宙 shownote 提取
  integrations/    — OpenAI 兼容 LLM 客户端、飞书文档 API 与通知
  outputs/         — Markdown 输出与本地结果持久化
  orchestration/   — 主编排流程（转录 + 下载）
  *.py             — 兼容旧导入路径的薄包装模块
media_processor.py          — CLI 入口
media_transcript_skill.py   — OpenClaw Skill 封装
skills/media-transcript/    — OpenClaw SKILL.md 技能定义
```

## ASR 纠错分段（Refine）

当转录来源为 ASR（无字幕回退）时，pipeline 会自动执行 LLM 纠错分段：

1. 将长文本按 `refine_max_chars`（默认 8000 字）在句子边界处分批
2. 每批调用 LLM 进行：
   - **纠错**：修正同音错字（如"积德利益"→"既得利益"）、漏字、多字
   - **分段**：按话题和逻辑段落分段
3. 合并所有批次结果

该步骤仅在 ASR 来源时触发，字幕来源不执行。

## 输出格式

### Markdown

生成带 YAML frontmatter 的 Markdown 文件，保存在 `markdown_dir` 目录下：

```yaml
---
platform: xiaoyuzhou
url: https://www.xiaoyuzhoufm.com/episode/xxx
date: "2026-04-26"
topics: [自我认知, 命运哲学, 反脆弱系统]
entities:
  - name: 尼采
    type: person
  - name: 《道德经》
    type: book
---
```

正文包含：一句话摘要、实体列表、结构化总结、要点、金句（blockquote）、热门评论、完整转录文本。

### 飞书文档

自动发布为飞书文档，包含：
- 一句话摘要（引用块）
- 实体列表（按人物/组织/书籍分类）
- 结构化总结与要点
- 金句（引用块）
- 热门评论
- 完整转录文本

## 扩展新平台

1. 在 `src/media_tool/platforms/` 下新建适配器文件
2. 继承 `PlatformAdapter`，实现 `matches()` 方法
3. 在 `registry.py` 中注册

`pipeline.py` 无需任何改动。

## 运行测试

```bash
pytest tests/
```

## 常见问题

**为什么优先提取字幕而不是 ASR？**
字幕提取速度快、精度高，只有在没有字幕时才回退到 ASR。

**SenseVoice 模型下载太慢？**
首次运行从 ModelScope 下载约 900MB。可以手动下载 `iic/SenseVoiceSmall` 并设置 `sensevoice_model_path` 指向本地路径。

**飞书文档看不到？**
需要在 `config.json` 中配置 `feishu_share_user_id`，程序会自动将文档分享给你。

**ASR 转录准确度不够？**
ASR 文本会自动经过 LLM 纠错分段（refine），修正同音错字和逻辑分段。可通过 `refine_max_chars` 调整批次大小。

**LLM 返回非 JSON？**
`summarizer.py` 内置了多层容错解析（JSON 修复、正则提取），若仍失败会抛出明确异常。可切换到能力更强的模型。

**飞书文档写入失败？**
`feishu.py` 会抛出 `FeishuAPIError`，可使用 `--retry` 从已保存的结果重试上传。

**YouTube 下载报 "Sign in to confirm you're not a bot"？**
Cookie 登录态缺失或过期。先验证现有 cookie 是否有效：

```bash
yt-dlp --cookies cookies.txt --skip-download --print title "https://www.youtube.com/watch?v=xxx"
```

能打印标题说明 cookie 有效，问题在别处；报错则更新 `cookies.txt`（任选其一）：

```bash
# 方式一：从 Edge 重新导出（前提：Edge 里已登录 YouTube）
yt-dlp --cookies-from-browser edge:Default --cookies cookies.txt --skip-download --simulate "https://www.youtube.com/watch?v=xxx"
```

方式二：Edge 安装 "Get cookies.txt LOCALLY" 扩展，登录 YouTube 后导出，覆盖项目根目录的 `cookies.txt`（不依赖钥匙串，最稳）。

注意：`cookies.txt` 等同于 YouTube 登录凭据，已被 `.gitignore` 忽略，切勿提交或分享；Edge 中退出登录会使文件立即失效；会话 cookie 一般可用数月。

**YouTube 下载报 "find-generic-password failed" / "cannot decrypt v10 cookies"？**
macOS 钥匙串拒绝了 yt-dlp 读取浏览器加密密钥，仅影响 `--cookies-from-browser` 方式。改用 `yt_dlp_cookies_file` 配置即可绕开；若坚持使用浏览器方式，在钥匙串授权弹窗中输入 Mac 密码并点「始终允许」。

**YouTube 下载报 "The page needs to be reloaded"？**
新版 yt-dlp 需要外部 EJS 脚本求解 YouTube 的 JS 挑战。本项目已对所有 yt-dlp 调用自动附加 `--remote-components ejs:github`（脚本首次使用时从 GitHub 下载并缓存），正常情况下无需手动处理；若仍报错，检查网络能否访问 GitHub 后重试。

## 作为 OpenClaw Skill 使用

本项目已包含 OpenClaw 技能定义（`skills/media-transcript/SKILL.md`），通过 SSH 远程调用目标机器上的 `media_processor.py`。

### 前置条件

目标机器需安装 xyz-text 及全部依赖，并配置好 `config.json`。

### 安装方式

**方式一：复制到 OpenClaw 技能目录**

```bash
cp -r skills/media-transcript ~/.openclaw/skills/media-transcript
```

**方式二：通过配置加载（推荐）**

在 `~/.openclaw/openclaw.json` 中添加项目 `skills/` 目录：

```json
{
  "skills": {
    "load": {
      "extraDirs": ["/path/to/xyz-text/skills"]
    }
  }
}
```

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `MEDIA_TRANSCRIPT_HOST` | SSH 目标地址 | `user@192.168.1.100` |
| `MEDIA_TRANSCRIPT_PATH` | xyz-text 在目标机器上的绝对路径 | `/home/user/xyz-text` |

### 验证安装

```bash
openclaw skills list
```

安装后，当用户在 OpenClaw 中发送 Bilibili / YouTube / 小宇宙 URL 时，agent 会通过 SSH 调用目标机器上的 `media_processor.py` 进行转录、总结并同步到飞书。
