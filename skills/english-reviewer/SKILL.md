---
name: english-reviewer
description: ALWAYS trigger when the user's message is written in English prose (not code, commands, or pasted foreign text) — even for short, casual, everyday messages. Do not skip this just because the request itself seems simple or easy to answer directly. Reviews grammar/vocabulary of the user's own prompt and appends a correction. Do not wait to be asked.
---

# English Reviewer

After the real answer, if the message was English prose, append:

English review — my message:
Original: <user's sentence(s), trimmed if long>
Corrected: <fixed version>
Why: <1 short sentence>
Another example: <1 new correct sentence, same pattern>
Pattern to learn: <short name>

Rules:
- Skip for code/commands/pasted foreign text, or say "No errors found" if flawless.
- Keep review under ~80 words. Don't delay the main answer.
- Only flag real errors, not style/tone.
