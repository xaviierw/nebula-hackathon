# Door dataset limitations found during the leakage audit

Checked with `audit/check_identifier_columns.py`. These are properties of the
supplied data, not of the model.

## 1. No door, car or vehicle identifier exists

`Door Data Headers.md` lists `Car Type`, `Car Number` and `Door Number` as
parameters of the dataset. **None of the three is present in the delivered
CSVs.** This was checked explicitly, because "absent" and "present but constant"
are different findings with different consequences:

| Column | Train.csv | Test.csv |
|---|---|---|
| `Car Type` | absent | absent |
| `Car Number` | absent | absent |
| `Door Number` | absent | absent |

Both files carry exactly 17 columns:

```
Datetime, Motor current(mA), Motor Voltage(10mV), Motor electrodynamic force,
Door opening time(.1s), Door closing time(.1s), Close command, Open command,
DCSR, DCSL, DLSR, DLSL, Door Opened, Door Locked, Door is opening,
Door is closing, Door leaf position
```

(A loose name search matches `Door opening time`, `Door Opened`, `Door Locked`
and similar, but these are signal columns, not identifiers.)

The columns are genuinely **absent, not constant**. The distinction matters:

- **Present and constant** would mean the stream is one known door, and
  cross-door generalisation would be untestable *by construction* -- a clean,
  stateable limitation.
- **Absent**, which is what we have, is weaker. We cannot tell whether the
  stream is one door or several pooled together, because nothing in the data
  says. Any per-door variation is invisible.

### Consequence

Leave-one-door-out validation is impossible, and so is checking whether the
class separation holds *within* a door or only *across* doors. The info kit
(Section 1.2) specifically warns that "data distributions differ among doors" --
that is precisely the risk this dataset gives no way to measure.

`audit/grouped_cv.py` substitutes leave-one-contiguous-time-block-out, which
tests generalisation to an unseen operating session. That is the closest
available proxy and is *not* the same test. It is reported as a substitute, not
as a per-door result.

## 2. The faults present are not "slight"

The mildest fault in the training data sits 19 sigma (Open) and 54 sigma (Close)
from the Normal cluster. **All figures in this section are over all 110 Train
cycles** -- see the scope warning below before comparing them with anything.

```
Open   normals 258.8 .. 276.6 mA    mildest fault 333.1 mA   (+25%)
Close  normals 186.6 .. 197.7 mA    mildest fault 309.8 mA   (+63%)
```

Info kit Section 1.2 names "missed detection of slight resistance faults" as a
core problem to solve, but no slight fault appears in the data. The task as
shipped is easier than the task as described, and reported scores should be read
with that in mind.

### Quoting a figure from this dataset: state its scope

Every summary statistic here has three defensible scopes, and they disagree.
Quoting one without saying which produces contradictions that look like errors
but are not. This has already happened twice:

**Population scope -- all 110 cycles vs the 77-cycle fit split.**

| | all 110 | 77-cycle fit split |
|---|---|---|
| mildest Open fault | **333.1 mA** | **336.8 mA** |
| Open highest Normal | 276.6 mA | 272.5 mA |
| Close Normal MAD | 1.03 mA | 0.74 mA |
| mildest fault, sigma | 19.1 / 54.5 | 24.1 / 81.8 |

`audit/threshold_k_sweep.py` and the `K_OPEN`/`K_CLOSE` comments in
`training/train.py` use the **fit split**, because that is what the model is
fitted on. This file uses **all 110**, because it describes the dataset. The
mildest Open fault lands in the holdout, which is the whole of the 333.1 / 336.8
discrepancy.

**Class scope -- both classes together vs one class alone.**

The Open duration envelope is **2.72-2.92 s** over all 55 Open cycles. But:

```
Open Normal    2.76 .. 2.88 s   (n=40)
Open Abnormal  2.72 .. 2.92 s   (n=15)
both           2.72 .. 2.92 s   (n=55)
```

So a quoted "2.72-2.88 s" is not a scope at all -- it takes the minimum from the
Abnormal cycles and the maximum from the Normal ones, describing no population.
The runtime duration guard in `prediction/predict.py` uses the both-classes
envelope (2.72-2.92 s Open, 3.54-3.78 s Close), exported to
`model/door_reference.json` at training time, because at prediction time the
class is exactly what is not yet known.

**The rule:** whenever a number from this dataset appears in code, a comment or
the write-up, say which cycles it came from. The two scopes above are each
correct for their purpose; only the unlabelled quote is wrong.

## 3. The Normal cluster is implausibly tight

Normal cycles vary by roughly 1% across 40 repetitions (Open CV 1.3%, Close
CV 1.2%), with pairwise waveform correlation 0.98-0.996. Real door hardware
would spread wider -- supply voltage, temperature, friction and wear all drift.
This is consistent with simulated or fault-injected data rather than recorded
operation, which is a further reason not to read a perfect score as evidence the
method would hold up on real vehicles.

## 4. `travel_fraction` was designed after inspecting the Test inputs

`core/features.py` normalises door-leaf position to a fraction of each cycle's
own travel range. The docstring of `travel_fraction` cites an Open cycle
overshooting to 807 position units. **That cycle exists only in `Test.csv`**
(`2023-7-5-0-20-55-731`); every `Train.csv` Open travels 695-705. So the function
was written after looking at the unlabelled Test inputs.

Recorded here rather than left to be inferred:

- **No labels were involved.** `Test.csv` is distributed unlabelled and its
  reference labels are held by the organisers, so none were available at any
  point. No label information could have leaked, and the scores reported on
  Train and its holdout are unaffected.
- **Input distributions were seen.** The unlabelled Test inputs were inspected
  during development. That is materially weaker than label leakage, but it is
  not nothing: a design informed by the evaluation inputs is a real, if mild,
  information flow, and it is disclosed rather than hidden.
- **The design is correct on its own merits.** A fixed absolute mid-travel window
  measures a different phase of the stroke on any cycle whose travel differs from
  the training norm. Fraction-based normalisation is the right choice whether or
  not such a cycle happens to appear in the data you looked at. Verified in the
  segmentation audit: the 0.20-0.85 window maps to absolute positions 164-683 on
  the 807-travel cycle and 141-590 on a 700-travel Train cycle -- the same phase
  of stroke in both. Seeing the 807 cycle prompted the fix; it did not justify it.

The original docstring line is deliberately left unchanged, and a short pointer
to this section sits in the `core/features.py` module docstring, so a reader of
the code meets the disclosure without needing this file.

## 5. Both streams are curated subsets, not continuous logs

Open and Close cycles **do not alternate** in either file:

| | segments | Open / Close | same-operation adjacencies |
|---|---|---|---|
| `Train.csv` | 110 | 55 / 55 | **57 of 109** transitions |
| `Test.csv` | 38 | 18 / 20 | **19 of 37** transitions |

The Test operation sequence, in time order:

```
C C O O C C O C O O C O C O O O C O O O C C C C C C O O O C C C O C O O C C
```

Strict alternation over 38 segments would give 19 Open / 19 Close; 18/20 is
arithmetically impossible under alternation (it needs 39 segments). And
same-operation adjacency is not an edge effect -- it occurs at half of all
transitions in both files, scattered throughout, with ordinary 10-58 s gaps at
those points.

### What this implies

A physical door cannot open twice without closing in between. So between two
consecutively recorded Opens, a Close occurred that **is not in the file**. Both
streams are a sampled selection of cycles drawn from a longer recording, not a
continuous operational log.

The inter-cycle gaps are therefore **elided cycles, not idle dwell time**. Any
model that reads meaning into gap duration, cycle cadence, or operation sequence
is modelling the curation, not the door.

### The row arithmetic behind it

This is about cycles missing *from* the stream, not unlabelled cycles *within*
it. Every row present is accounted for:

```
Train.csv rows                          18036
  consecutive sampling intervals        18035
  at exactly 0.020 s (within a cycle)   17926
  above the gap threshold (boundaries)    109   ->  110 blocks
detected blocks                           110
rows in Train_Segments_Answer.csv         110   ->  0 unlabelled blocks
sum(n_rows) over the answer file        18036   =  len(Train.csv)
```

Block starts, ends and row counts match the answer file exactly for all 110.
`Test.csv` is the same shape: 6253 rows, 37 boundaries, 38 blocks, every row
inside one. So the detector emits no spurious segments, and the false-positive
count of zero stands. The missing cycles were removed before the file was
written, leaving no trace in it beyond the broken alternation.
