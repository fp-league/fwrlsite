"""
Lightweight sanity tests for the OCR parsing logic in capture_agent.py.
No game footage or Tesseract binary required — these just check the
regex/logic that turns raw OCR text into structured values.

Run: python test_parsing.py
"""

from capture_agent import parse_position, parse_lap, ConfirmedValue


def check(label, actual, expected):
    status = "PASS" if actual == expected else "FAIL"
    print(f"[{status}] {label}: got {actual!r}, expected {expected!r}")
    return actual == expected


def test_parse_position():
    results = []
    results.append(check("plain number", parse_position("3"), 3))
    results.append(check("with P prefix", parse_position("P7"), 7))
    results.append(check("with noise", parse_position("P 12 "), 12))
    results.append(check("garbage text", parse_position("!!"), None))
    results.append(check("out of range", parse_position("P99"), None))
    results.append(check("zero rejected", parse_position("P0"), None))
    return all(results)


def test_parse_lap():
    results = []
    results.append(check("simple lap", parse_lap("2/3"), "2/3"))
    results.append(check("with spaces", parse_lap("LAP 1 / 3"), "1/3"))
    results.append(check("garbage text", parse_lap("no lap here"), None))
    return all(results)


def test_confirmed_value():
    cv = ConfirmedValue(confirm_frames=3)
    results = []
    results.append(check("no confirm on 1st read", cv.update(5), None))
    results.append(check("no confirm on 2nd read", cv.update(5), None))
    results.append(check("confirms on 3rd matching read", cv.update(5), 5))

    cv2 = ConfirmedValue(confirm_frames=3)
    cv2.update(5)
    cv2.update(5)
    results.append(check("mismatched read resets streak", cv2.update(6), None))
    results.append(check("still not confirmed after reset", cv2.update(6), None))
    results.append(check("confirms new value after 3 consistent reads", cv2.update(6), 6))
    return all(results)


if __name__ == "__main__":
    all_passed = all([
        test_parse_position(),
        test_parse_lap(),
        test_confirmed_value(),
    ])
    print("\nALL TESTS PASSED" if all_passed else "\nSOME TESTS FAILED")
    raise SystemExit(0 if all_passed else 1)
