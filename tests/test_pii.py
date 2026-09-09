from guardrail_agent.guardrails.pii import redact_evidence, redact_text, scan_pii
from guardrail_agent.schema import Evidence


def test_scan_detects_kinds():
    text = "reach raj@example.com or +1-415-555-0142, SSN 123-45-6789"
    kinds = scan_pii(text)
    assert set(kinds) == {"EMAIL", "PHONE", "SSN"}


def test_redact_text_replaces_and_reports():
    red, kinds = redact_text("email raj@example.com now")
    assert "raj@example.com" not in red
    assert "[REDACTED_EMAIL]" in red
    assert kinds == ["EMAIL"]


def test_redact_text_noop_when_clean():
    red, kinds = redact_text("the beta launch is on track")
    assert kinds == []
    assert red == "the beta launch is on track"


def test_redact_evidence_marks_redacted_flag():
    ev = [
        Evidence(id="a", source="gmail", title="Contact", text="call 202-555-0173"),
        Evidence(id="b", source="notion", title="Roadmap", text="Q3 beta, Q4 GA"),
    ]
    cleaned, kinds = redact_evidence(ev)
    assert kinds == ["PHONE"]
    assert cleaned[0].redacted is True
    assert cleaned[1].redacted is False
    assert "202-555-0173" not in cleaned[0].text


def test_phone_not_confused_by_ticket_numbers():
    assert scan_pii("PX-101 has 12 of 12 items and 5000 users") == []
