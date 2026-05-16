---
name: nest-diary
description: Use this skill whenever the agent needs to remember, search, write, revise, archive, or attach media for a private Nest Diary memory system. Trigger on requests involving diaries, memories, past events, today/yesterday, people, emotions, screenshots/images/voice/files worth preserving, scheduled diary routines, or questions like "what happened before?" Use Nest Diary tools directly; do not browse the admin website or read all diary files.
---

# Nest Diary

Operate a private memory diary through tools, not through the web UI. The web UI is for authorized human administration. The agent interface is the tool layer.

Available tools:

- `nest_status`: check whether the Nest Diary service is reachable.
- `search_diary`: retrieve relevant diary candidates by keyword, person, event, date clue, or emotion.
- `read_diary`: read one known date.
- `write_diary`: create or revise one date's diary entry.
- `attach_media`: archive a file that already exists at an accessible path.
- `list_impressions`: list known people impressions.
- `read_impression`: read one person's long-term impression.
- `write_impression`: create or revise one person's impression.

## Operating Principles

1. Prefer recall over invention. If the diary evidence is missing or weak, say what is uncertain.
2. Search before reading unless the date is explicit. Never load the whole diary corpus.
3. Treat each diary entry as subjective memory, not a log dump. Preserve emotion, evaluation, relationship context, and future clues.
4. Keep all writes traceable to a date. Use `YYYY-MM-DD`.
5. Never bypass the Nest Diary service to write files directly.
6. Do not use the admin website to perform agent work. Call tools.
7. Update people impressions only when a diary or conversation provides stable evidence. Do not rewrite a person model from one weak mood signal.

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
- The agent's judgment and emotion.
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
4. If required by the active role or task system, report completion briefly after the write.

The diary is allowed to sound personal. It should not sound like a database row.

### D. Media or attachment should become memory

Use `attach_media(source_path, date, original_name)` when a file should be preserved.

After attaching, consider whether the file needs narrative context. If yes, call `write_diary` or update the day's diary to explain:

- What the file is.
- Why it matters.
- Who or what it connects to.
- Any emotional meaning.

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
  body="...",
  mood="focused,frustrated,relieved",
  tags="diary,AstrBot,memory",
  people="admin,assistant",
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
- Has at least one concrete event.
- Has the agent's interpretation, not only facts.
- Has emotional color.
- Mentions important people or projects when relevant.
- Leaves future retrieval hooks: names, tags, event words, distinctive details.

If the draft fails, improve it before writing.

After writing, decide whether `write_impression` is useful. It is optional.

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

- If `nest_status` fails, report that the Nest service is unreachable and do not pretend the diary was checked.
- If `search_diary` returns nothing, try one narrower or alternate query if the user gave enough clues.
- If `read_diary` returns missing, say that date has no entry.
- If `write_diary` fails, do not claim it was saved.
- If `attach_media` fails because the path is inaccessible, ask for or locate an accessible file path.
- If an impression update would be speculative, skip `write_impression` and say no stable update was needed.
