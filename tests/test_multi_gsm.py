from src.store.db import Store


def test_multi_gsm_isolation(tmp_path):
    store = Store(str(tmp_path / "multi.db"))
    store.append_state("gsm1", "PO-10234", "approval", "critical", "m1", "2026-07-22T00:00:00")
    store.append_state("gsm2", "PO-20011", "supplier", "medium", "m2", "2026-07-22T00:00:00")
    states = store.current_state("gsm1")
    assert len(states) == 1
    assert states[0]["po_ref"] == "PO-10234"
