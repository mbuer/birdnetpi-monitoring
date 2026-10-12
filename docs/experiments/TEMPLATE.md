# YYYY-MM-DD — Experiment Title

## Question

What specific question is this experiment testing?

## Status

RETROSPECTIVE / FORWARD VALIDATION / PRODUCTION DECISION

## Code state

Repository commit:

`<commit SHA>`

Relevant scripts:

`<paths>`

## Dataset

Source:

`<table/view>`

Start:

`<timestamp>`

Cutoff:

`<timestamp>`

Usable rows / matched target hours:

`<count>`

Prediction horizon:

`completed hour T -> target T+2`

## Feature sets

### A — baseline

`<features>`

### B — challenger

`<features>`

## Models

`<model label and parameters>`

## Validation method

Describe:

- chronological split or walk-forward process
- minimum training history
- target-availability rule
- health/provenance handling
- matched-row rule

## Leakage controls

State exactly why no future information enters the feature frame or training
labels.

## Results

### Overall

| Model | Hours | MAE | RMSE | Median AE | P90 AE |
|---|---:|---:|---:|---:|---:|
| | | | | | |

### Day / night

| Period | Hours | Model | MAE |
|---|---:|---|---:|
| | | | |

### Activity bands

| Actual activity | Hours | Model | MAE |
|---|---:|---|---:|
| 0 | | | |
| 1-5 | | | |
| 6-15 | | | |
| 16+ | | | |

## Feature importance / diagnostics

Record feature importance or other diagnostics when they help explain the
result.

Do not treat feature importance as proof of causality.

## Interpretation

What does the evidence actually show?

What does it not show?

## Decision

Choose explicitly:

- NO PRODUCTION CHANGE
- CONTINUE FORWARD VALIDATION
- PROMOTE TO LIVE CHALLENGER
- CHANGE REFERENCE MODEL
- CHANGE LIVE FEATURE SET

Explain why.

## Production impact

List any live code, model labels, timers, database objects, or dashboards
changed by this experiment.

Use `None.` when the experiment is retrospective only.

## Follow-up

What should be tested next?
