"""Print the story-web calibration report for a world.

    python tools/story_web_report.py --fixture            # the hand-built cast from the hero generator tests
    python tools/story_web_report.py --world path.json    # a saved world (heroes attached or not)
    python tools/story_web_report.py --seed 42 --size 17  # generate a world first (slow)
    add --quiet for the flag list only, --json to dump the block

The report is read-only: it never writes to the world or the policies.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Sim'))
sys.path.insert(0, str(ROOT / 'Sim' / 'tests'))


def load_world(args):
    if args.fixture:
        import test_hero_generator
        return test_hero_generator.world(seed=args.seed or 42)
    if args.world:
        return json.loads(Path(args.world).read_text(encoding='utf-8'))
    from fantasy_world_generator.cli import world_document
    return world_document({'recipe_version': 3, 'seed': args.seed or 42, 'overrides': {'size': args.size or 17}})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--world')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--size', type=int)
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # the report uses arrows; Windows consoles default to cp1252
    os.environ.setdefault('FANTASY_WORLD_HEROES', '1')
    world = load_world(args)
    import hero_generator
    import story_web
    from story_web.policy import load_all
    from story_web.report import lines
    if world.get('heroes', {}).get('status') != 'ok':
        world['heroes'] = hero_generator.generate(world)
    block = story_web.generate(world)
    if args.json:
        print(json.dumps(block, indent=1, sort_keys=True))
        return 0
    tropes = {t['id']: t for t in load_all()['tropes']['tropes']}
    for line in lines(block, tropes, world['heroes'], verbose=not args.quiet):
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
