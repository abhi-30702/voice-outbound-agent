from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ConstraintError:
    rule: str
    excerpt: str


class ConstraintValidator:
    MAX_WORDS = 12
    _BULLET = re.compile(r'^(?:[-•]|\*\s|\d+\.)')
    _SPECIAL = re.compile(r'\[|\]|#|\*\*|__')

    def check(self, rendered: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        errors.extend(self._check_sentence_length(rendered))
        errors.extend(self._check_no_bullets(rendered))
        errors.extend(self._check_no_special_chars(rendered))
        return errors

    def _check_sentence_length(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for line in text.splitlines():
            for sentence in re.split(r'(?<!\d)[.!?](?!\d)', line):
                stripped = sentence.strip()
                if not stripped:
                    continue
                if len(stripped.split()) > self.MAX_WORDS:
                    errors.append(ConstraintError(rule="sentence_length", excerpt=stripped[:80]))
        return errors

    def _check_no_bullets(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and self._BULLET.match(stripped):
                errors.append(ConstraintError(rule="no_bullets", excerpt=stripped[:80]))
        return errors

    def _check_no_special_chars(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for match in self._SPECIAL.finditer(text):
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            errors.append(ConstraintError(rule="no_special_chars", excerpt=text[start:end]))
        return errors
