from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'modules'))
import policy_model as PM
import revision_engine as EF

def load_inputs(sh,ny):
    return PM.prepare(PM.load_stocks(sh,ny))

def output_dir(path):
    p=Path(path);p.mkdir(parents=True,exist_ok=True);return p
