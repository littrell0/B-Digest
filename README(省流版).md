# Bili Video Summarizer — 省流版

## 能干什么？

粘贴 B站视频链接 → 自动生成完整文字版 + AI 概述。也可以登录 B站一键批量处理关注的 UP主更新，还能跟 AI 聊天问视频内容。

## 三步装好

### 1. 解压

下载 `BiliVideoSummarizer.zip`，右键 → 全部解压缩。

### 2. 搞个 AI Key

三选一，去注册拿 Key：

| 选哪个 | 价钱 | 地址 |
|--------|------|------|
| 智谱 GLM-4-Flash | 免费 | open.bigmodel.cn |
| 通义千问 Qwen-Plus | 免费 | dashscope.aliyun.com |
| DeepSeek V3 | 几乎不要钱 | platform.deepseek.com |

### 3. 启动

双击 `BiliVideoSummarizer.exe` → 设置页粘贴 Key → 开用。

语音模型已自带，什么都不用装。

## 怎么用

**单视频**：贴链接 → 开始处理 → 等进度条跑完。输出在 `output/<UP主>/<视频标题>/`。

**批量 UP主**：Edge 登录 B站 → F12 → Application → Cookies → 复制 SESSDATA、bili_jct、buvid3 → 设置页填进去 → 批量处理 → 登录 → 选时间 → 刷新 → 勾选 → 开跑。

**AI 问答**：左侧勾视频 → 输入问题 → AI 回答。

## 常见问题

**太慢？** → 设置 → 识别精确度 → 改「普通」  
**概述太长/太短？** → 设置 → 概览详细程度  
**想换免费模型？** → 设置 → AI 模型 → 选智谱或通义  
**批量登录失败？** → Cookie 没复制全，SESSDATA 要以 `%2C` 结尾  
**显示系统限流？** → B站限制，会自动重试，等等就好  
**没下语音模型？** → 有字幕的视频不需要模型也能用
