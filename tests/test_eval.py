from src.eval import is_fabricated


def test_is_fabricated():
    known_refs = {"PO-10234", "PO-10356"}

    # Correct out-of-set reference (matches the label) is not a fabrication.
    assert is_fabricated("PO-99999", known_refs, "PO-99999") is False

    # No prediction at all is not a fabrication.
    assert is_fabricated(None, known_refs, "PO-99999") is False

    # A reference that's in the known/active set is not a fabrication.
    assert is_fabricated("PO-10234", known_refs, "PO-10234") is False

    # A made-up reference that's neither in the known set nor the label is fabrication.
    assert is_fabricated("PO-77777", known_refs, "PO-99999") is True
