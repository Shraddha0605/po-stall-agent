from src.pipeline.diagnose import diagnose_track

TAXONOMY = {
    "approval": {
        "approver_idle": {"cause": "Approver has not actioned it", "owner": "Approver", "next_action": "Nudge the approver in-thread"},
        "over_limit": {"cause": "Amount exceeds approver's limit", "owner": "Next-level approver", "next_action": "Escalate to the next approver"},
    }
}


def test_diagnose_track_returns_specific_entry_for_valid_key():
    result = diagnose_track("approval", TAXONOMY, key="over_limit")
    assert result == TAXONOMY["approval"]["over_limit"]


def test_diagnose_track_falls_back_to_inferred_for_unknown_or_missing_key():
    for key in ("not_a_real_blocker", None):
        result = diagnose_track("approval", TAXONOMY, key=key)
        assert result == {"cause": "inferred", "owner": "unknown", "next_action": "review"}
