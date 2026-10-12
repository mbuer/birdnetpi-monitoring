# 2026-09-18 — American Crow Bootstrap Ensemble

## Goal

Test whether a class-balanced bootstrap XGBoost ensemble improves sparse-species presence classification compared with the current single XGBoost baseline.

This experiment was diagnostic when run. Its result later justified running an American Crow bootstrap challenger alongside the unchanged reference models for forward-validation; see [2026-09-18-species-challengers.md](2026-09-18-species-challengers.md).

## Dataset

Species: American Crow

- raw hourly rows: 542
- valid feature rows: 516
- development rows: 412
- chronological diagnostic holdout rows: 104
- holdout positive targets: 20 / 104 (19.2%)
- prediction horizon: completed hour T -> target hour T+2

The same final time window had already been inspected in an earlier tuning experiment, so this holdout is no longer considered untouched evidence.

## Hyperparameter Search

Search objective: mean chronological validation PR-AUC.

Best development result:

- mean CV PR-AUC: 0.4239
- n_estimators: 250
- max_depth: 5
- learning_rate: 0.08
- min_child_weight: 2.0
- subsample: 1.0
- colsample_bytree: 0.75
- gamma: 0.0
- reg_alpha: 0.2
- reg_lambda: 2.0
- class_weight_factor: 0.0

## Ensemble Method

The ensemble used 15 XGBoost members.

For each member:

1. split the training rows into positive and negative target classes
2. sample both classes with replacement
3. use equal sample counts for positive and negative classes
4. train one XGBoost model
5. repeat with a different bootstrap sample
6. average the member probabilities

Probability averaging was used instead of majority voting.

Because each bootstrap sample is explicitly class-balanced, no additional class weighting was applied inside the ensemble members.

## Development Thresholds

Single tuned XGBoost:

- threshold: 0.500
- F1: 0.444
- precision: 0.571
- recall: 0.364

Bootstrap ensemble:

- threshold: 0.500
- F1: 0.273
- precision: 0.182
- recall: 0.545

The development-period ensemble showed substantially higher recall but lower precision.

## Diagnostic Holdout Results

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Current XGBoost @ 0.50 | 0.817 | 0.600 | 0.150 | 0.240 | 0.817 | 0.539 |
| Tuned XGBoost @ 0.50 | 0.817 | 0.600 | 0.150 | 0.240 | 0.807 | 0.521 |
| Bootstrap average @ 0.50 | 0.827 | 0.571 | 0.400 | 0.471 | 0.790 | 0.516 |

## Interpretation

The ensemble did not improve probability ranking metrics:

- ROC-AUC decreased from 0.817 to 0.790
- PR-AUC decreased from 0.539 to 0.516

However, classification behavior improved materially at the selected threshold:

- recall increased from 0.150 to 0.400
- F1 increased from 0.240 to 0.471
- precision remained similar at 0.571 vs 0.600
- accuracy increased slightly from 0.817 to 0.827

For a presence-detection use case, this is promising because the ensemble caught substantially more positive target hours without a large precision penalty.

## Current Conclusion

Do not replace the current live model yet.

Treat the bootstrap ensemble as a challenger because:

- the dataset is still short
- positive samples remain limited
- the same holdout window has already influenced the research direction
- development and holdout precision differed substantially
- live forward-validation has not yet been collected for this ensemble

That follow-up comparison has now been completed for House Finch, Black Phoebe, and Anna's Hummingbird. The consolidated results and current challenger decisions are recorded in [2026-09-18-species-challengers.md](2026-09-18-species-challengers.md).
