"""The assignment equation: weights decide which spoke is offered; nothing is rolled.

    weight = boosts × alignment_fit × archetype_fit × claim_fit

`boosts` multiplies the trope's factor for every listed fact the hero carries.
`alignment_fit` is 1 + gain × (pull · alignment) / |pull|, floored, so a spoke whose pull
matches the hero's colour is favoured and an opposed one is damped but never removed.
`archetype_fit` and `claim_fit` are flat multipliers when the hero's archetype or claim
verb is one the trope names. The breakdown is exported so the lab can show the arithmetic.
"""
import math


def alignment_fit(pull, alignment, policy):
    dot = pull['law'] * alignment['law'] + pull['good'] * alignment['good']
    norm = max(math.hypot(pull['law'], pull['good']), policy['pull_floor'])
    return max(policy['fit_floor'], 1. + policy['fit_gain'] * dot / norm)


def weight(trope, facts, hero, policy):
    boosts = 1.
    applied = []
    for fact, factor in trope['boosts'].items():
        if fact in facts:
            boosts *= factor
            applied.append(fact)
    fit = alignment_fit(trope['pull'], hero['alignment'], policy)
    archetype = policy['fits_factor'] if hero.get('archetype') in trope['fits'] else 1.
    verb = (hero.get('claim') or {}).get('verb') or 'none'
    claim = policy['claim_factor'] if verb in trope['claims'] else 1.
    boosts, fit = round(boosts, 4), round(fit, 4)
    value = round(boosts * fit * archetype * claim, 4)  # from the rounded parts, so the exported breakdown reproduces it
    return value, {'boosts': boosts, 'boosted_by': applied, 'alignment_fit': fit, 'archetype_fit': archetype, 'claim_fit': claim}


def angle_degrees(law, good):
    """Direction on the web: good to the right, lawful up; 0..360 counter-clockwise from good."""
    return round(math.degrees(math.atan2(law, good)) % 360., 2)
