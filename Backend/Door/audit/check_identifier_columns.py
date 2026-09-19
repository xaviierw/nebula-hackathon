"""Audit: are Car Type / Car Number / Door Number absent, or present-but-constant?

Those are different findings. Absent means we cannot tell whether the stream is
one door or several pooled; present-but-constant would mean it is provably a
single door. Prints the full column list of both files, and for any of the three
that exist, their distinct values and counts.

    python audit/check_identifier_columns.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from core.data import DATA_DIR

D = str(DATA_DIR) + "/"
TARGETS=["Car Type","Car Number","Door Number"]
for f in ["Train.csv","Test.csv"]:
    df=pd.read_csv(D+f)
    print(f"\n{'='*60}\n{f}: {len(df)} rows, {len(df.columns)} columns\n{'='*60}")
    for i,c in enumerate(df.columns,1): print(f"  {i:2d}. {c}")
    print("  -- target columns --")
    for t in TARGETS:
        hits=[c for c in df.columns if c.strip().lower()==t.lower()]
        loose=[c for c in df.columns if t.split()[0].lower() in c.lower()]
        if hits:
            col=df[hits[0]]; u=col.unique()
            print(f"  '{t}': PRESENT, {col.nunique()} distinct -> {u[:10]}")
            if col.nunique()==1: print(f"      CONSTANT at {u[0]}")
        else:
            print(f"  '{t}': ABSENT (no exact column). loose name matches: {loose or 'none'}")
