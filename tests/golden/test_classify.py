from src.eval import main


def test_golden_set_eval_gate():
    assert main([]) == 0
