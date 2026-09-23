# Branch governance
phase/<number>-<name> → CI → review → merge to main → verify main → next phase.
One active phase branch at a time. Phase branches start from green main. PRs target main. Main must remain green. No legacy production migration before Phase 0 is green.
