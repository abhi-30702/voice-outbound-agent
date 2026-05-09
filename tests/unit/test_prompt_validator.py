from app.conversation_prompts.validator import ConstraintError, ConstraintValidator


def test_clean_text_passes():
    validator = ConstraintValidator()
    text = "Hi, this is Priya. I am calling about a great plan. Are you free?"
    errors = validator.check(text)
    assert errors == []


def test_long_sentence_caught():
    validator = ConstraintValidator()
    # 16 words — well over the 12-word limit
    text = "This sentence has sixteen words in it and goes way over the allowed maximum limit right here."
    errors = validator.check(text)
    sentence_errors = [e for e in errors if e.rule == "sentence_length"]
    assert len(sentence_errors) >= 1
    assert errors[0].rule == "sentence_length"


def test_bullet_caught():
    validator = ConstraintValidator()
    text = "Some intro.\n- first item\n- second item"
    errors = validator.check(text)
    bullet_errors = [e for e in errors if e.rule == "no_bullets"]
    assert len(bullet_errors) == 2


def test_numbered_list_caught():
    validator = ConstraintValidator()
    text = "Steps:\n1. Do this\n2. Do that"
    errors = validator.check(text)
    bullet_errors = [e for e in errors if e.rule == "no_bullets"]
    assert len(bullet_errors) == 2


def test_special_char_bracket_caught():
    validator = ConstraintValidator()
    text = "This has a [bracket] in it."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_special_char_hash_caught():
    validator = ConstraintValidator()
    text = "# Heading\nSome text."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_special_char_double_asterisk_caught():
    validator = ConstraintValidator()
    text = "This is **bold** text."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_constraint_error_fields():
    validator = ConstraintValidator()
    text = "This is **bold**."
    errors = validator.check(text)
    err = next(e for e in errors if e.rule == "no_special_chars")
    assert isinstance(err.rule, str)
    assert isinstance(err.excerpt, str)
    assert len(err.excerpt) > 0


def test_double_asterisk_not_flagged_as_bullet():
    validator = ConstraintValidator()
    # **bold** should produce no_special_chars, NOT no_bullets
    text = "**bold text here**"
    errors = validator.check(text)
    bullet_errors = [e for e in errors if e.rule == "no_bullets"]
    assert len(bullet_errors) == 0  # must not be a false bullet


def test_decimal_not_split_as_sentence():
    validator = ConstraintValidator()
    # "3.5" should not be treated as a sentence boundary
    text = "The plan covers 3.5 lakh rupees per year."
    errors = validator.check(text)
    sentence_errors = [e for e in errors if e.rule == "sentence_length"]
    # 8 words — well under 12, should pass
    assert len(sentence_errors) == 0
