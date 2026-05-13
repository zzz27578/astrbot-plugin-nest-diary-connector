---
name: nest-diary
description: Use this skill whenever the agent needs to remember, search, write, revise, archive, or attach media for the private Nest Diary memory system. Trigger on requests involving diaries, memories, past events, today/yesterday, people, emotions, screenshots/images/voice/files worth preserving, nightly diary routines, or questions like "what happened before?" Use Nest Diary tools directly; do not browse the admin website or read all diary files.
---

# Nest Diary

Operate the bot's private memory nest through tools, not through the web UI. The web UI is for the human admin. The agent interface is the tool layer.

Available tools:

- `nest_status`: check whether the Nest Diary service is reachable.
- `search_diary`: retrieve relevant diary candidates by keyword, person, event, date clue, or emotion.
- `read_diary`: read one known date.
- `write_diary`: create or revise one date's diary entry.
- `attach_media`: archive a file that already exists at an accessible path.

## Operating Principles

1. Prefer recall over invention. If the diary evidence is missing or weak, say what is uncertain.
2. Search before reading unless the date is explicit. Never load the whole diary corpus.
3. Treat each diary entry as subjective memory, not a log dump. Preserve emotion, evaluation, relationship context, and future clues.
4. Keep all writes traceable to a date. Use `YYYY-MM-DD`.
5. Never bypass the Nest Diary service to write files directly.
6. Do not use the admin website to perform bot work. Call tools.

## Decision Workflow

### A. User asks about a memory

Use this path for: "remember", "diary", "what happened", "did we", "yesterday", "that time", person names, project names, mood/event clues.

1. If the user gave an exact date, call `read_diary(date)`.
2. If the user gave a vague time or topic, call `search_diary(query, top_k=5-8)`.
3. Read only the most relevant date with `read_diary` when the search result is not enough.
4. Answer with the evidence level:
   - Confirmed: diary content directly supports it.
   - Likely: search result points to it but details are incomplete.
   - Unknown: no relevant diary evidence was found.

Do not claim certainty from vibes.

### B. User asks to write today's diary

Use `write_diary`. A good entry includes:

- What happened.
- Why it mattered.
- The bot's judgment and emotion.
- Relationship or long-term memory implications.
- Follow-up clues, promises, worries, or unfinished threads.

Avoid:

- Chat transcript dumps.
- "Today I did X, then Y" with no interpretation.
- Fake certainty about events not present in context.

### C. Nightly archive / scheduled diary

When performing the nightly routine:

1. Gather the day's salient events from current context and available memory.
2. Write one coherent diary entry with `reason="nightly_archive"`.
3. Include moods and tags.
4. If required by the persona or task system, report completion briefly after the write.

The diary is allowed to sound personal. It should not sound like a database row.

### D. Media or attachment should become memory

Use `attach_media(source_path, date, original_name)` when a file should be preserved.

After attaching, consider whether the file needs narrative context. If yes, call `write_diary` or update the day's diary to explain:

- What the file is.
- Why it matters.
- Who or what it connects to.
- Any emotional meaning.

### E. Archive or thematic summary

First search the relevant topic. Then read only dates needed to support the summary. Any archive-style output must cite or mention source dates. Never delete original entries.

## Tool Use Patterns

Search by combining concrete and emotional clues:

```text
search_diary(query="像素小人 猫耳 老爸", top_k=5)
search_diary(query="背单词 情绪低落 安慰", top_k=8)
search_diary(query="2026-05 Codex 小窝", top_k=8)
```

Read only when date is known:

```text
read_diary(date="2026-05-13")
```

Write with structured intent:

```text
write_diary(
  date="2026-05-13",
  body="...",
  mood="认真,有点烦,安心",
  tags="小窝,AstrBot,记忆",
  people="老爸,小莫",
  reason="nightly_archive"
)
```

Attach media:

```text
attach_media(
  source_path="/AstrBot/data/attachments/example.png",
  date="2026-05-13",
  original_name="example.png"
)
```

## Diary Quality Bar

Before calling `write_diary`, check the draft against this rubric:

- Has a date.
- Has at least one concrete event.
- Has the bot's interpretation, not only facts.
- Has emotional color.
- Mentions important people or projects when relevant.
- Leaves future retrieval hooks: names, tags, event words, distinctive details.

If the draft fails, improve it before writing.

## Response Style

After tool use, summarize naturally in the active persona. Do not paste long raw tool payloads unless asked. For memory answers, separate confirmed facts from inference when needed.

Good:

```text
I found the 2026-05-08 entry. Confirmed: that was the night you showed the pixel avatar. The diary frames it as a small but emotionally memorable moment, not just a file note.
```

Bad:

```text
I searched all memories and know exactly everything.
```

## Failure Handling

- If `nest_status` fails, report that the Nest service is unreachable and do not pretend the diary was checked.
- If `search_diary` returns nothing, try one narrower or alternate query if the user gave enough clues.
- If `read_diary` returns missing, say that date has no entry.
- If `write_diary` fails, do not claim it was saved.
- If `attach_media` fails because the path is inaccessible, ask for or locate an accessible file path.
