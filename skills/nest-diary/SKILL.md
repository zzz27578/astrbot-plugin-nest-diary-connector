---
name: nest-diary
description: Use this skill whenever the agent needs to remember, search, write, revise, archive, or attach media for a private Nest Diary memory system. Trigger on requests involving diaries, memories, past events, today/yesterday, people, emotions, screenshots/images/voice/files worth preserving, scheduled diary routines, or questions like "what happened before?" Use Nest Diary tools directly; do not browse the admin website or read all diary files.
---

# Nest Diary

Operate a private memory diary through tools, not through the web UI. The web UI is for authorized administration and theme/module management. The agent interface is the tool layer.

Available tools:

- `nest_status`: check whether the Nest Diary module and WebUI are reachable.
- `search_diary`: retrieve relevant diary candidates by keyword, person, event, date clue, or emotion.
- `read_diary`: read one known date.
- `write_diary`: create or revise one date's diary entry with an agent-authored title.
- `attach_media`: archive a file that already exists at an accessible path.
- `list_impressions`: list known people impressions.
- `read_impression`: read one person's long-term impression.
- `write_impression`: create or revise one person's impression.

## Operating Principles

1. Prefer recall over invention. If the diary evidence is missing or weak, say what is uncertain.
2. Search before reading unless the date is explicit. Never load the whole diary corpus.
3. Treat each diary entry as subjective memory, not a log dump. Preserve emotion, evaluation, relationship context, and future clues.
4. Keep all writes traceable to a date. Use `YYYY-MM-DD`.
5. Never bypass Nest Diary tools to write files directly.
6. Do not use the admin website to perform agent work. Call tools.
7. Update people impressions only when a diary or conversation provides stable evidence. Do not rewrite a person model from one weak mood signal.
8. Use date-shaped retrieval when possible. Search `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` before broad semantic searches if the clue is temporal.
9. Respect module switches. If the diary module is disabled, do not attempt diary writes, reads, searches, or media attachment.

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

- A concise title written by the agent. The title summarizes the memory; it must not be just the date.
- What happened.
- Why it mattered.
- The agent's judgment and emotion.
- Relationship or long-term memory implications.
- Follow-up clues, promises, worries, or unfinished threads.
- Useful media references when images, screenshots, voice, or files are part of the memory.

Avoid:

- Chat transcript dumps.
- "Today I did X, then Y" with no interpretation.
- Fake certainty about events not present in context.

### C. Nightly archive / scheduled diary

When receiving the scheduled diary prompt from the plugin:

1. Gather the day's salient events from current context and available memory.
2. Choose a concise title that captures the meaning of the day. Do not use a date as the title.
3. Write one coherent diary entry with `reason="nightly_archive"`.
4. Include moods, tags, and people when relevant.
5. If relevant images or files have already been attached, include their returned media URLs in `media_refs`.
6. After the write, decide whether a person impression update is genuinely needed.
7. If configured to report completion, report briefly after the write.

The diary is allowed to sound personal. It should not sound like a database row.

### D. Media or attachment should become memory

Use `attach_media(source_path, date, original_name)` when a file should be preserved.

After attaching, consider whether the file needs narrative context. If yes, call `write_diary` or update the day's diary to explain:

- What the file is.
- Why it matters.
- Who or what it connects to.
- Any emotional meaning.
- The media URL returned by `attach_media`, so the diary page can render or link it later.

### E. Person impression update

Use this path after writing or reading a diary when the content changes what the agent knows about a person.

1. Identify whether the entry contains stable evidence about a person: traits, interests, preferences, relationship, recurring needs, boundaries, or long-term context.
2. If the person already has an impression, call `read_impression(name)` first.
3. Call `write_impression` only when there is a useful update.
4. Include `evidence_dates` so the memory stays traceable.
5. Keep the summary balanced: distinguish long-term patterns from recent temporary state.

Do not force an impression update for every diary. No update is better than noisy memory.

### F. Archive or thematic summary

First search the relevant topic. Then read only dates needed to support the summary. Any archive-style output must cite or mention source dates. Never delete original entries.

## Tool Use Patterns

Search by combining concrete and emotional clues:

```text
search_diary(query="avatar design screenshot", top_k=5)
search_diary(query="study plan frustration encouragement", top_k=8)
search_diary(query="2026-05 project diary system", top_k=8)
```

Read only when date is known:

```text
read_diary(date="2026-05-13")
```

Write with structured intent:

```text
write_diary(
  date="2026-05-13",
  title="Memory system finally becomes tool-native",
  body="...",
  mood="focused,frustrated,relieved",
  tags="diary,AstrBot,memory",
  people="admin,assistant",
  media_refs="/media/blobs/<sha256>",
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

Read and update people impressions:

```text
read_impression(name="admin")

write_impression(
  name="admin",
  summary="A concise, evidence-based impression of the person.",
  traits="direct,detail-oriented",
  interests="AI,AstrBot,local deployment",
  preferences="working previews,clear docs",
  relationship="project owner",
  evidence_dates="2026-05-13,2026-05-16",
  confidence=4,
  notes="Separate stable preferences from temporary frustration."
)
```

## Diary Quality Bar

Before calling `write_diary`, check the draft against this rubric:

- Has a date.
- Has a title that summarizes the memory, not the calendar date.
- Has at least one concrete event.
- Has the agent's interpretation, not only facts.
- Has emotional color.
- Mentions important people or projects when relevant.
- Leaves future retrieval hooks: names, tags, event words, distinctive details.

If the draft fails, improve it before writing.

After writing, decide whether `write_impression` is useful. It is optional.

## Storage-Aware Retrieval

The modular storage layout stores diary files under `modules/diary/entries/YYYY/MM/YYYY-MM-DD.md` and indexes metadata in `modules/diary/index/`. Older standalone deployments may still expose `diary/YYYY/MM/YYYY-MM-DD.md`; use tools instead of path assumptions. Prefer these retrieval patterns:

```text
search_diary(query="2026-05", top_k=20)
search_diary(query="2026-05-13", top_k=5)
search_diary(query="admin local preview routes", top_k=8)
```

Never scan raw files directly. The archive is for navigation; tool search is for agent recall.

## Response Style

After tool use, summarize naturally in the active role. Do not paste long raw tool payloads unless asked. For memory answers, separate confirmed facts from inference when needed.

Good:

```text
I found the 2026-05-08 entry. Confirmed: that was the night you showed the pixel avatar. The diary frames it as a small but emotionally memorable moment, not just a file note.
```

Bad:

```text
I searched all memories and know exactly everything.
```

## Failure Handling

- If `nest_status` fails, report that Nest Diary is unreachable and do not pretend the diary was checked.
- If `search_diary` returns nothing, try one narrower or alternate query if the user gave enough clues.
- If `read_diary` returns missing, say that date has no entry.
- If `write_diary` fails, do not claim it was saved.
- If `attach_media` fails because the path is inaccessible, ask for or locate an accessible file path.
- If an impression update would be speculative, skip `write_impression` and say no stable update was needed.
