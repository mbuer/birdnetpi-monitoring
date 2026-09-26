# 2026-09-26 — Live Forward-Validation Checkpoint

## Purpose

Record the first substantial live forward-validation checkpoint before the next ML implementation phase.

All results below come from forecasts that were stored before their target outcomes occurred. These results must not be treated as an untouched future evaluation set after being used to guide model or threshold decisions.

## Aggregate activity

Matched scored target hours:

- 233 shared Random Forest / XGBoost target hours
- Random Forest MAE: 3.850
- XGBoost MAE: 4.069
- persistence MAE: 7.622
- Random Forest wins: 143
- XGBoost wins: 89
- ties: 1

### Day versus night

| Period | Hours | RF MAE | XGBoost MAE | RF wins | XGBoost wins |
|---|---:|---:|---:|---:|---:|
| Day | 123 | 6.567 | 6.687 | 65 | 58 |
| Night | 110 | 0.813 | 1.141 | 78 | 31 |

The current Random Forest advantage is concentrated mainly in quiet/night periods. Daytime performance is much closer.

### Activity bands

| Actual activity | Hours | RF MAE | XGBoost MAE | RF wins | XGBoost wins |
|---|---:|---:|---:|---:|---:|
| 0 | 109 | 1.162 | 1.501 | 78 | 30 |
| 1–5 | 33 | 4.476 | 4.608 | 18 | 15 |
| 6–15 | 40 | 4.904 | 4.729 | 18 | 22 |
| 16+ | 51 | 8.366 | 8.690 | 29 | 22 |

XGBoost is slightly better in the 6–15 activity band, while Random Forest is stronger overall and especially at zero activity.

## Species classification

Matched live target-hour results:

| Species | Model | Scored | Accuracy | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|
| American Crow | Random Forest | 199 | 0.819 | 0.429 | 0.086 | 0.143 |
| American Crow | XGBoost | 199 | 0.829 | 0.538 | 0.200 | 0.292 |
| American Crow | bootstrap XGBoost | 199 | 0.794 | 0.438 | 0.600 | 0.506 |
| Black Phoebe | Random Forest | 199 | 0.789 | 0.481 | 0.317 | 0.382 |
| Black Phoebe | XGBoost | 199 | 0.804 | 0.526 | 0.488 | 0.506 |
| Black Phoebe | tuned XGBoost | 199 | 0.704 | 0.408 | 0.976 | 0.576 |
| House Finch | Random Forest | 273 | 0.810 | 0.791 | 0.582 | 0.671 |
| House Finch | XGBoost | 273 | 0.806 | 0.738 | 0.648 | 0.690 |

### Probability quality

Brier score is lower-is-better.

| Species | Model | Mean probability | Actual prevalence | Brier score |
|---|---|---:|---:|---:|
| American Crow | Random Forest | 0.128 | 0.176 | 0.1170 |
| American Crow | XGBoost | 0.130 | 0.176 | 0.1140 |
| American Crow | bootstrap XGBoost | 0.252 | 0.176 | 0.1427 |
| Black Phoebe | Random Forest | 0.210 | 0.206 | 0.1256 |
| Black Phoebe | XGBoost | 0.211 | 0.206 | 0.1240 |
| Black Phoebe | tuned XGBoost | 0.440 | 0.206 | 0.1968 |
| House Finch | Random Forest | 0.286 | 0.333 | 0.1246 |
| House Finch | XGBoost | 0.296 | 0.333 | 0.1198 |

At this checkpoint, the ordinary XGBoost reference model has the best Brier score for all three species.

The Black Phoebe tuned challenger achieves very high recall but is substantially overconfident on average. Its behavior is useful as a high-recall classifier, but its probability values should not be interpreted as well-calibrated occurrence probabilities.

The American Crow bootstrap challenger materially improves recall and F1, but its probability calibration is worse than the ordinary reference models.

## Threshold sweep

A threshold sweep from 0.20 to 0.80 showed that much of the Black Phoebe tuned challenger's apparent threshold-based advantage can be reproduced by changing the threshold on the reference models.

Examples from the same inspected forward dataset:

- Black Phoebe Random Forest reaches F1 0.595 at threshold 0.25
- Black Phoebe ordinary XGBoost reaches F1 0.593 at threshold 0.25 and 0.592 at 0.35
- Black Phoebe tuned XGBoost reaches F1 0.593 at threshold 0.75

American Crow retains a more interesting challenger signal:

- Random Forest best observed F1 in the sweep: 0.500
- ordinary XGBoost best observed F1: 0.493
- bootstrap XGBoost best observed F1: 0.528

These are exploratory results, not newly validated production thresholds. Because this forward dataset has now been inspected, it must not be reused as an untouched test set for threshold tuning.

## Interpretation

Current evidence supports:

- keeping Random Forest as the aggregate reference model
- keeping XGBoost live for matched comparison
- adding HistGradientBoosting as a third aggregate challenger so true forward history begins accumulating
- treating ordinary species XGBoost probabilities as more trustworthy than the current tuned/bootstrap challenger probabilities
- retaining the American Crow bootstrap challenger because it appears to add useful classification behavior
- treating the Black Phoebe tuned challenger primarily as a high-recall experiment rather than as a calibrated probability model
- expanding the live reference species set conservatively with Black-crowned Night-Heron and Lesser Goldfinch
- prioritizing ingestion/completeness evidence before adding further model complexity

## Data-quality caution

The current pipeline still cannot always distinguish a genuinely quiet hour from a station or ingestion outage.

The aggregate view is also weather-backed even though the current live aggregate models do not use weather variables directly.

Those limitations should be addressed before increasingly fine-grained model comparisons are treated as authoritative.

## Next phase

The intended sequence after this checkpoint is:

```text
preserve this checkpoint
    -> snapshot infrastructure
    -> inspect/fix data completeness
    -> start HistGradientBoosting forward validation
    -> add the two selected species reference forecasts
    -> continue matched live evaluation
    -> improve Grafana ML observability
```
