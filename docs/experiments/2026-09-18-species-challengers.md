# 2026-09-18 — Species Challenger Comparison

## Goal

Compare the existing species XGBoost baseline with tuned single-model and class-balanced bootstrap challengers before deciding which approaches deserve live forward-validation.

Prediction horizon:

```text
completed hour T -> target hour T+2
```

The experiments use chronological development/holdout splits. The final windows below are diagnostic because they have now been inspected and must not be reused as untouched evidence for additional tuning.

---

## House Finch

Diagnostic holdout:

- 104 target hours
- 32 positive targets (30.8%)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Current XGBoost @ 0.50 | 0.808 | 0.731 | 0.594 | 0.655 | 0.893 | 0.753 |
| Tuned XGBoost @ 0.50 | 0.779 | 0.605 | 0.812 | **0.693** | 0.887 | 0.748 |
| Bootstrap average @ 0.50 | 0.769 | 0.591 | 0.812 | 0.684 | 0.889 | **0.759** |

Interpretation: the current model is already strong. Tuning/bootstrapping mainly trades precision for recall, so no House Finch challenger was promoted to live forward-validation.

---

## Black Phoebe

Diagnostic holdout:

- 104 target hours
- 16 positive targets (15.4%)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Current XGBoost @ 0.50 | 0.788 | 0.312 | 0.312 | 0.312 | 0.782 | 0.328 |
| Tuned XGBoost @ 0.50 | 0.663 | 0.298 | **0.875** | 0.444 | **0.831** | **0.467** |
| Bootstrap average @ 0.475 | 0.731 | **0.342** | 0.812 | **0.481** | 0.825 | 0.389 |

Interpretation: the tuned single XGBoost produced the clearest ranking improvement and very large recall improvement. It was selected as the Black Phoebe live challenger under model label:

`xgboost_tuned_species_v1`

The bootstrap ensemble achieved slightly higher F1 on this diagnostic window but weaker PR-AUC than the tuned single model.

---

## American Crow

Detailed results are recorded in:

`docs/experiments/2026-09-18-american-crow-bootstrap-ensemble.md`

Diagnostic holdout summary:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Current XGBoost @ 0.50 | 0.817 | 0.600 | 0.150 | 0.240 | **0.817** | **0.539** |
| Tuned XGBoost @ 0.50 | 0.817 | 0.600 | 0.150 | 0.240 | 0.807 | 0.521 |
| Bootstrap average @ 0.50 | **0.827** | 0.571 | **0.400** | **0.471** | 0.790 | 0.516 |

Interpretation: bootstrapping did not improve ranking metrics, but it substantially improved recall and F1 while preserving useful precision. American Crow therefore receives a live bootstrap challenger under model label:

`xgboost_bootstrap_species_v1`

The ordinary Random Forest/XGBoost reference rows are also issued live so future comparisons use matched target hours.

---

## Anna's Hummingbird

Diagnostic holdout:

- 104 target hours
- 8 positive targets (7.7%)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Current XGBoost @ 0.50 | **0.923** | 0.000 | 0.000 | 0.000 | 0.892 | 0.342 |
| Tuned XGBoost @ 0.35 | 0.587 | 0.157 | **1.000** | 0.271 | 0.905 | **0.407** |
| Bootstrap average @ 0.45 | 0.702 | **0.205** | **1.000** | **0.340** | **0.911** | 0.379 |

Interpretation: tuning and bootstrapping recover the positive class, but precision remains too low and only eight positive holdout examples are available. Anna's Hummingbird remains retrospective/experimental rather than live.

---

## Decision

The experiment supports a species-specific challenger architecture rather than one universal model configuration.

Current live plan:

| Species | Reference models | Challenger |
|---|---|---|
| House Finch | Random Forest + XGBoost | none |
| Black Phoebe | Random Forest + XGBoost | tuned XGBoost |
| American Crow | Random Forest + XGBoost | 15-member balanced bootstrap XGBoost ensemble |
| Anna's Hummingbird | none | retrospective only |

Reference and challenger forecasts are stored under separate model labels in `bird_species_predictions`.

The next meaningful evidence is not another round of tuning against these same diagnostic windows. It is matched forward-validation from forecasts stored before their outcomes occur.
