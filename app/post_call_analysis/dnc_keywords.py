DNC_PHRASES: frozenset[str] = frozenset({
    "do not call",
    "don't call",
    "stop calling",
    "remove me",
    "remove my number",
    "take me off",
    "unsubscribe",
    "opt out",
    "not interested ever",
    "never call again",
    "don't contact",
    "do not contact",
})


def scan(transcript: str) -> bool:
    lower = transcript.lower()
    return any(phrase in lower for phrase in DNC_PHRASES)
