from src.store.db import Store


def test_idempotency_prevents_duplicate_draft_registration(tmp_path):
    store = Store(str(tmp_path / "idempotency.db"))
    store.record_draft("gsm1", "message-1", "PO-10234", "draft-1", "run-1")
    assert store.draft_seen("gsm1", "message-1", "PO-10234", "run-1") is True
