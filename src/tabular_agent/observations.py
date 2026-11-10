"""Compare whole numeric observations, preserving multiplicities and paired coordinates."""

import math

from .reference import equal


def compare_observations(actual: list[dict], expected: list[dict], columns: list[str], order_by: list[str]):
    details = {"actual_observations": len(actual), "expected_observations": len(expected)}
    if len(actual) != len(expected):
        return False, details
    invalid = [i for i, row in enumerate(actual) if not isinstance(row, dict) or set(row) != set(columns)
               or any(type(v) not in {int, float} or (type(v) is float and not math.isfinite(v)) for v in row.values())]
    if invalid:
        return False, {**details, "invalid_observation_positions": invalid[:3]}

    def agrees(got, want, fields=columns):
        return all(equal(got[c], want[c]) for c in fields)

    if order_by:
        for position, (got, want) in enumerate(zip(actual, expected)):
            if not agrees(got, want, order_by):
                return False, {**details, "first_order_difference": {
                    "position": position, "actual": got, "expected": want,
                }}
    # A demonstrated one-to-one correspondence is sufficient at any table size.
    def ordered(rows):
        return sorted(rows, key=lambda row: tuple(row[c] for c in columns))

    got, want = ordered(actual), ordered(expected)
    if all(agrees(a, b) for a, b in zip(got, want)):
        return True, details
    # Crossing tolerance neighborhoods can make a sorted pairing fail even when
    # another complete pairing exists. Use maximum matching for bounded cases.
    # Never turn an unresolved large approximate matching problem into a pass/fail.
    if len(actual) > 200:
        if all(type(value) is int for row in expected for value in row.values()):
            mismatch = next((a, b) for a, b in zip(got, want) if not agrees(a, b))
            return False, {**details, "different_integer_observation_example": {
                "actual": mismatch[0], "expected": mismatch[1],
            }}
        raise NotImplementedError("Raw approximate matching is ambiguous above 200 observations; exact/sorted correspondences remain covered")
    neighbors = [[j for j, target in enumerate(expected) if agrees(row, target)] for row in actual]
    assigned = {}

    def augment(index, seen):
        for other in neighbors[index]:
            if other in seen:
                continue
            seen.add(other)
            if other not in assigned or augment(assigned[other], seen):
                assigned[other] = index
                return True
        return False

    for index in range(len(actual)):
        augment(index, set())
    if len(assigned) == len(expected):
        return True, details
    matched = set(assigned.values())
    return False, {**details,
                   "missing_observation_examples": [row for i, row in enumerate(expected) if i not in assigned][:3],
                   "unexpected_observation_examples": [row for i, row in enumerate(actual) if i not in matched][:3]}
