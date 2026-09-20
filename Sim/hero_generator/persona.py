"""Persona composition: an alignment-neutral card, coloured by the two axis overlays.

    persona = core(archetype) + overlay(law pole) + overlay(good pole) + pole notes

The same Tyrant card therefore reads as a Chaotic Good strongman or a Lawful Evil autocrat
depending only on the alignment the deeds produced. `never` is the union of every hard
line, so a downstream proposal that crosses one can be rejected mechanically.
"""
from .alignment import good_pole, law_pole


def _line(card, code):
    lines = card['lines']
    if code in lines:
        return lines[code]
    same_good = [text for key, text in lines.items() if key[1] == code[1]]
    if same_good:
        return same_good[0]
    return next(iter(lines.values()))


def compose(card, overlays, alignment):
    law = overlays['law'][law_pole(alignment['law'])]
    good = overlays['good'][good_pole(alignment['good'])]
    core = card['core']
    manner = [card['pole_notes'][p] for p in (law_pole(alignment['law']), good_pole(alignment['good'])) if p != 'neutral']
    never = list(core['never'])
    for entry in law['never'] + good['never']:
        if entry not in never:
            never.append(entry)
    return {'archetype': card['id'], 'belief': core['belief'], 'wants': core['wants'], 'fears': core['fears'],
            'tells': core['tells'], 'mechanic': core['mechanic'],
            'manner': ' '.join(manner) or 'Neither law nor morality pulls harder than the other; the archetype shows almost unmodified.',
            'voice': f"{law['voice']} {good['voice']}", 'lies': f"{good['lies']} {law['lies']}",
            'toward_player': f"{good['toward_player']} {law['toward_player']}",
            'cornered': f"{law['cornered']} {good['cornered']}", 'never': never,
            'line': _line(card, alignment['code'])}
