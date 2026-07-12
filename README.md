# Bili Video Summarizer — B站视频转文字概述工具

输入B站视频链接，自动生成完整逐字稿 + AI 概述。支持批量处理关注 UP主更新、AI 问答。

## 功能

- **单视频处理**：输入 B站链接 → 字幕提取或语音识别 → AI 生成概述。四档识别精确度、三档概览详细度、实时 ETA、中途停止
- **批量处理**：B站 Cookie 登录 → 选择时间范围 → 自动检测关注 UP主新视频 → 批量生成。支持 UP主筛选、412 风控自动重试、已处理标记、搜索过滤
- **AI 问答**：选择已处理视频 → 向 AI 提问视频内容。树形列表（UP主/视频）、多选、第一人称回答、保存对话
- **设置页**：三种 AI 模型切换（DeepSeek / 通义千问 / 智谱）、输出格式（md/txt）、深色/浅色主题、模型下载、运行日志查看

## 快速开始

1. 下载 `BiliVideoSummarizer.zip`，解压到任意目录
2. 双击 `BiliVideoSummarizer.exe`
3. 在设置页填入 API Key（三选一，免费/廉价）：
   - 智谱 GLM-4-Flash（永久免费）：open.bigmodel.cn
   - 通义千问 Qwen-Plus（月送500万Token）：dashscope.aliyun.com
   - DeepSeek V3（近乎免费）：platform.deepseek.com

即可使用。语音识别模型已自带（`models/` 目录），无需额外下载。


## 使用

| Tab | 操作 |
|-----|------|
| 单视频处理 | 粘贴 B站链接 → 开始处理 → 输出 `output/<UP主>/<视频标题>/` |
| 批量处理 | 设置页填 B站 Cookie → 登录 → 选时间 → 刷新 → 勾选 → 批量处理 |
| AI 问答 | 勾选视频 → 输入问题 → AI 基于内容回答 |
| 设置 | 切换模型/精确度/详细度/格式/主题，下载模型，查看日志 |

> B站 Cookie 获取：Edge → F12 → Application → Cookies → bilibili.com → SESSDATA、bili_jct、buvid3

## 参数参考

### 识别精确度

| 预设 | 模型 | 精确度 | 速度 | 适合 |
|------|------|:-----:|:----:|------|
| 最精确 | large-v3 | 95% | 3.0 min/分钟 | 专业字幕 |
| 精确 | medium | 88% | 1.5 min/分钟 | 学习笔记 |
| 普通 | small | 75% | 0.5 min/分钟 | 快速浏览 |
| 急速 | tiny | 60% | 0.2 min/分钟 | 预览（不推荐中文） |

### 概览详细度

| 级别 | 占原文 | 10分钟视频 |
|------|--------|-----------|
| 精细概览 | 25-35% | 750-1200字 |
| 大致概览 | 10-15% | 300-500字 |
| 极简概览 | ≤5%（≤200字） | 100-200字 |

### AI 模型

| 模型 | 准确度 | 速度 | 费用 |
|------|:-----:|:----:|------|
| deepseek-chat | 8.5 | 8 | ¥1/M Token |
| qwen-plus | 8 | 7.5 | 月送500万Token |
| glm-4-flash | 7.5 | 9 | 永久免费 |

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | CustomTkinter |
| 视频处理 | yt-dlp |
| 语音识别 | faster-whisper（本地） |
| AI 概述/问答 | OpenAI 兼容 API（DeepSeek / 通义 / 智谱） |
| B站 API | bilibili-api-python |

## 项目结构

```
bili-video-summarizer/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── gui/           # app / single_video_tab / batch_tab / qa_tab / settings_tab / widgets / styles
│   ├── pipeline/      # orchestrator / video_info / subtitle_extractor / asr_engine / summarizer / qa_engine / output_writer
│   ├── bilibili/      # client.py (B站 API)
│   └── utils/         # logger / text_utils / validators
├── models/            # 语音识别模型
├── output/            # 生成结果
├── download_model.py
├── requirements.txt
├── app.log
└── settings.json
```

## 系统要求

Windows 10+ · 网络连接 · 8GB+ 内存 · 约 5GB 磁盘空间
