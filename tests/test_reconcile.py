from src.pipeline.reconcile import reconcile_counts


def test_reconcile_detects_mismatch():
    balanced = reconcile_counts(5, 3, 2, 2, 1)
    assert balanced["ok"] is True

    mismatched = reconcile_counts(5, 3, 1, 2, 1)
    assert mismatched["ok"] is False
