from src.pipeline.prefilter import prefilter_messages


def test_prefilter_keeps_known_po_and_discards_unknown():
    messages = [
        {"id": "1", "sender": "orders@acme-motors.example", "subject": "PO-10234 needs approval", "body": "", "threadId": "t1"},
        {"id": "2", "sender": "someone@example.com", "subject": "Hello", "body": "Please review", "threadId": "t2"},
    ]
    kept, discarded = prefilter_messages(messages, ["PO-10234"], allowlist=["orders@acme-motors.example"], pattern=r"PO-\d{5}")
    assert len(kept) == 1
    assert discarded[0]["reason"] == "not in scope"
