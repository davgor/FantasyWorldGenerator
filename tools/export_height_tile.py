"""Export resolved metre elevations from a saved world, without regenerating history."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Sim'))
from icarus_sim.terrain_detail import export_height_tile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('world',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--level',type=int,required=True)
    p.add_argument('--x',type=int,required=True);p.add_argument('--z',type=int,required=True)
    p.add_argument('--cells',type=int,default=64)
    a=p.parse_args()
    tile=export_height_tile(json.loads(a.world.read_text(encoding='utf-8')),a.level,a.x,a.z,a.cells)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(tile,allow_nan=False),encoding='utf-8')

if __name__=='__main__':main()
