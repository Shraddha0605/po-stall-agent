from src.pipeline.reconcile import reconcile_counts


def test_reconcile_detects_mismatch():
    balanced = reconcile_counts(5, 3, 2, 2, 1)
    assert balanced["ok"] is True

    mismatched = reconcile_counts(5, 3, 1, 2, 1)
    assert mismatched["ok"] is False


def test_reconcile_balances_with_nonzero_review_items():
    result = reconcile_counts(10, 7, 3, 4, 3)
    assert result["ok"] is True
    assert result["ingested"] == result["passed"] + result["discarded"]
    assert result["passed"] == result["state_updated"] + result["review_items"]
