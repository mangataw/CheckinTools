import logging

from checkin_tools.security import RedactingFilter, register_ci_masks, sanitize_text


def test_sanitize_text_removes_secrets_and_query_values():
    text = sanitize_text(
        "cookie=private https://example.com/hook?access_token=private secret=hidden",
        ("private", "hidden"),
    )
    assert "private" not in text
    assert "hidden" not in text
    assert "?" not in text


def test_redacting_filter_replaces_formatted_message():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "value %s", ("sensitive",), None)
    assert RedactingFilter(("sensitive",)).filter(record)
    assert record.getMessage() == "value ***"


def test_ci_masks_only_print_inside_actions(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    register_ci_masks(("secret",))
    assert not capsys.readouterr().out
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    register_ci_masks(("secret", ""))
    assert capsys.readouterr().out == "::add-mask::secret\n"

