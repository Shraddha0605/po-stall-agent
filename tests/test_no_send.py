from pathlib import Path


def test_no_send_scope_and_messages_send_calls():
    root = Path(__file__).resolve().parents[1]
    src_files = list((root / "src").rglob("*.py"))
    joined = "\n".join(path.read_text(encoding="utf-8") for path in src_files)
    assert "gmail.send" not in joined
    assert "messages.send" not in joined
