"""Heritage: what a people is like, as static data, one layer deriving the next.

`civilizations.json` already answers where a people can live - 37 numeric fields of climate
comfort, slope limit, water reach and food. This package answers what they are like: 17
categorical key traits per race, a culture derived from them, a language genome derived
from culture and soma, and an authored appearance. Traits are authored, the middle two
layers are derived and then patched by sparse overrides, so adding a people yields a
plausible culture and tongue for free while anything can still be hand-tuned.

Appearance is the exception to the derivation: a race carries a complete body and each
subrace extends it, because a skin range or an ear form is new information rather than a
consequence of the seventeen axes. It is also the only layer here that carries numbers,
and `policy.lint_appearance` says why that is safe.

The package is a leaf. It never imports `icarus_sim`, so `resolve` is handed a parent race
rather than looking one up, and the two enums it has to restate - the civilization ids and
the eight known magic schools - are locked against the registry from the repository test
suite rather than by an import. It also carries no seed logic: callers pass their own
deterministic draw, which keeps every seeding decision with the subsystem that owns it.
"""
from .derive import (heritage_identity, lexicon, reset_cache, resolve, revisions)
from .naming import (name_stock, name_table, person_name, person_name_with_gloss, realm_name,
                     settlement_name, stock_name)
from .policy import (APPEARANCE_BLOCKS, AXES, BODY_SCALE_HEIGHT_M, CULTURE_BLOCKS,
                     KNOWN_SCHOOLS, load, load_all)

VERSION = 1

__all__ = ('APPEARANCE_BLOCKS', 'AXES', 'BODY_SCALE_HEIGHT_M', 'CULTURE_BLOCKS',
           'KNOWN_SCHOOLS', 'VERSION', 'heritage_identity',
           'lexicon', 'load', 'load_all', 'name_stock', 'name_table', 'person_name',
           'person_name_with_gloss', 'realm_name', 'reset_cache', 'resolve', 'revisions',
           'settlement_name', 'stock_name')
