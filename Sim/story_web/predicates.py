"""Entry predicates: any-of-conjunctions over facts, the same shape the archetype cards use.

A token `x` holds when `x` is in the fact set; `!x` holds when it is not. A trope is
eligible when any one conjunction holds entirely. `missing` reports, for the conjunction
closest to holding, exactly which tokens fail, so the ledger and the thread compiler can
say what would have to change.
"""


def holds(token, facts):
    if token.startswith('!'):
        return token[1:] not in facts
    return token in facts


def eligible(requires, facts):
    return any(all(holds(t, facts) for t in conjunction) for conjunction in requires)


def missing(requires, facts):
    """The failing tokens of the nearest conjunction (fewest failures, then catalogue order)."""
    best = None
    for conjunction in requires:
        failed = [t for t in conjunction if not holds(t, facts)]
        if best is None or len(failed) < len(best):
            best = failed
    return best or []
