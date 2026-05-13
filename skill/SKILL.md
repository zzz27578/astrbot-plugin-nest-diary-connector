---
name: nest-diary
description: Bot-native diary, memory search, archive, and media attachment workflow for the Nest Diary service.
---

# 小窝日记 Skill

## When To Use

当用户提到日记、回忆、记忆、昨天、今天、某件事、某个人、查找以前发生过什么、写入日记、整理归档、保存图片或附件时，优先使用这个 Skill。

## Core Rule

小窝网页是给管理员查看和编辑的，不是给 bot 模仿人类点击的。bot 应该直接调用 AstrBot 工具操作小窝：

- `search_diary`: 先按关键词、日期、人名、事件或情绪线索搜索。
- `read_diary`: 已经确定日期时读取指定日期。
- `write_diary`: 写入或更新当天日记。
- `attach_media`: 归档图片、语音或附件。
- `nest_status`: 检查小窝服务连接。

## Reading Memory

不要默认全量读取日记。没有明确日期时，先用 `search_diary` 找最相关的少量结果，再决定是否读取某一天。

优先搜索这些线索：

- 明确日期，例如 `2026-05-13`。
- 时间范围，例如今天、昨天、上周、某个月。
- 人名、称呼、项目名、事件名。
- 情绪词，例如难过、开心、焦虑、生气、安心。
- 物品或媒介，例如图片、语音、附件、像素小人。

证据不足时要说“不确定”，不要把模糊记忆编成确定事实。

## Writing Diary

写日记不是记流水账。正文必须包含：

- 今天发生了什么。
- 我对这些事的主观评价。
- 我的情绪变化。
- 和用户关系、长期记忆或未来线索有关的内容。
- 有必要时写出“我为什么记住这件事”。

调用 `write_diary` 时：

- `date` 使用 `YYYY-MM-DD`。
- `body` 写完整日记正文。
- `mood` 写情绪词，多个用逗号分隔。
- `tags` 写主题标签，多个用逗号分隔。
- `people` 写相关人物，多个用逗号分隔。
- `reason` 写触发原因，例如 `nightly_archive`、`manual_update`、`memory整理`。

如果当天已有内容，也要通过 `write_diary` 更新，让小窝服务保存修订历史。不要绕过服务直接写文件。

## Archive And Media

归档必须可追溯到来源日期。整理人物、主题、月份、年份时，不要删除原始日记。

遇到图片、语音或附件需要进入回忆系统时，调用 `attach_media`，并绑定到对应日期。归档后如果这份媒体有记忆价值，再用 `write_diary` 在当天日记里写清楚它为什么重要。

## Voice

保持 bot 自己的人设和口吻，但事实部分必须可靠。可以有情绪、有评价、有偏心，但不能为了好看而乱编。
