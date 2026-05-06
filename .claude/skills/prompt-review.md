# Skill: prompt-review
Rules to check (fail any = rewrite):
1. No sentence > 12 words
2. No bullet points or numbered lists in TTS text
3. No special characters (*, #, /, |)
4. Acronyms spelled out phonetically
5. Every flow step has explicit "wait for response" instruction
6. Objection paths present: busy / not_interested / angry
7. Escape hatch present (email follow-up -> end call)
Report: PASS or FAIL with line numbers
