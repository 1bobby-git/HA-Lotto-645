"""Public data fixtures for legacy HA regression tests; no private engine import."""
from datetime import date
import importlib,sys,types,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name,path in [('custom_components',ROOT/'custom_components'),('custom_components.lotto_645',ROOT/'custom_components/lotto_645')]:
    package=types.ModuleType(name);package.__path__=[str(path)];sys.modules.setdefault(name,package)
models=importlib.import_module('custom_components.lotto_645.models')
methods=importlib.import_module('custom_components.lotto_645.methods')
const=importlib.import_module('custom_components.lotto_645.const')

def _history(count=180):
    rng=random.Random(645);start=date(2022,1,1);rows=[]
    for i in range(1,count+1):
        vals=rng.sample(range(1,46),7)
        rows.append(models.LottoDraw(i,date.fromordinal(start.toordinal()+(i-1)*7).isoformat(),tuple(sorted(vals[:6])),vals[6]))
    return rows
