"""Score Rail Corrugation predictions against held-out labels.

The metric for this subsystem is FIXED and fully disclosed, with a worked
example, in its info kit (Backend/03_References/Rail_Corrugation/, section 4). Do not
invent one -- implement that.

Methodology is judged as heavily as the score: use a split appropriate to this
data (by file, by operating condition, by whatever grouping the info kit
implies) and state the assumption you made.
"""

from __future__ import annotations


def main(argv=None) -> int:
    raise NotImplementedError("Rail Corrugation evaluation not written yet")


if __name__ == "__main__":
    raise SystemExit(main())
