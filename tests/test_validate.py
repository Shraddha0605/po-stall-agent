from src.pipeline.validate import validate_classification


def test_validate_rejects_amount_mismatch_and_missing_evidence():
    po_map = {
        "PO-10234": {"po_ref": "PO-10234", "supplier_email": "orders@acme-motors.example", "amount": 48200},
    }
    valid, reason = validate_classification(
        {"po_ref": "PO-10234", "amount": 100, "sender": "orders@acme-motors.example", "message_id": "m1", "evidence": "looks good"},
        po_map,
        set(),
    )
    assert not valid
    assert reason == "amount_mismatch"

    valid, reason = validate_classification(
        {"po_ref": "PO-10234", "amount": 48200, "sender": "orders@acme-motors.example", "message_id": "m2", "evidence": ""},
        po_map,
        {"m1"},
    )
    assert not valid
    assert reason == "no_evidence"
