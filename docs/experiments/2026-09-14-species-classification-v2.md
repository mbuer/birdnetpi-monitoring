# Experiment: Species Classification — v2

**Date:** 2026-09-14  
**Status:** Completed  
**Prediction horizon:** T → T+2  
**Validation:** Chronological walk-forward

## Objective

Test whether individual bird species can be predicted for the next full future hour using the same leakage-safe timing convention as the aggregate activity model.

Initial species:

- House Finch
- Black Phoebe

The target is binary:

- `1` = species detected during the target hour
- `0` = species not detected

## Dataset

Source:

`bird_species_hourly`

The species view provides a continuous hourly timeline and explicitly represents hours with no detections.

It is independent of weather availability and retains `station_id`, allowing the same structure to support additional species and future BirdNET stations.

| Item | Value |
|---|---:|
| Raw hours | 471 |
| Valid feature rows | 445 |
| Walk-forward forecasts | 252 |
| Initial training rows | 192 |

## Features

The first classifier uses:

- `hour_of_day`
- current species presence
- species presence lag 1h
- species presence lag 2h
- species presence lag 3h
- species presence lag 24h
- current species detection count
- total bird detections
- number of species detected

Weather is not included in this first experiment.

## Models

### Prevalence

Uses historical species prevalence as the probability estimate.

### Persistence

Assumes the species presence state remains unchanged.

### Random Forest

- 300 trees
- `min_samples_leaf = 3`
- `random_state = 42`

### XGBoost

- 300 estimators
- `max_depth = 3`
- `learning_rate = 0.03`
- `subsample = 0.8`
- `colsample_bytree = 0.8`
- `objective = binary:logistic`
- `tree_method = hist`

XGBoost version: **3.4.1**

No hyperparameter tuning was performed.

---

## House Finch

Positive target hours:

**69 / 252 — 27.4%**

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| Persistence | 0.549 | 0.565 | 0.557 | 0.695 | 0.430 |
| Random Forest | **0.724** | 0.609 | 0.661 | **0.898** | **0.740** |
| XGBoost | 0.719 | **0.667** | **0.692** | 0.890 | 0.695 |

### Interpretation

Both ML models substantially outperform persistence.

Random Forest provides the strongest probability ranking, with the best ROC-AUC and PR-AUC.

XGBoost produces the best F1 score and recall, identifying more positive House Finch hours at the default 0.5 threshold.

House Finch prediction is already viable with the current dataset.

---

## Black Phoebe

Positive target hours:

**38 / 252 — 15.1%**

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| Persistence | 0.395 | 0.395 | 0.395 | 0.644 | 0.247 |
| Random Forest | 0.364 | 0.421 | 0.390 | 0.835 | 0.412 |
| XGBoost | **0.411** | **0.605** | **0.489** | **0.841** | **0.438** |

### Interpretation

Black Phoebe is more difficult to predict because positive hours are less common.

Despite the smaller positive class, both ML models learn useful structure.

XGBoost performs best across the principal classification metrics and improves recall substantially compared with Random Forest and persistence.

---

## Species Comparison

| Species | Positive Rate | Best F1 | Best ROC-AUC | Best PR-AUC |
|---|---:|---|---|---|
| House Finch | 27.4% | XGBoost — 0.692 | RF — 0.898 | RF — 0.740 |
| Black Phoebe | 15.1% | XGBoost — 0.489 | XGBoost — 0.841 | XGBoost — 0.438 |

## Conclusions

Species-level prediction is already useful with the current dataset.

The first two experiments show that:

- species presence contains predictable temporal structure
- ML clearly outperforms persistence
- model performance differs by species
- one model should not automatically be assumed best for every species
- XGBoost currently provides stronger threshold-based classification
- Random Forest remains particularly strong for House Finch probability ranking

No universal species model is promoted yet.

## Next Steps

1. Test American Crow as a more sparsely observed species.
2. Determine where prediction quality begins to degrade as positive examples decrease.
3. Evaluate probability thresholds instead of assuming `0.5`.
4. Add sunrise/daylight features.
5. Later test weather features.
6. Continue accumulating data and repeat the same experiments.

## Reproducibility

Species dataset:

`database/views/bird_species_hourly.sql`

Experiment script:

`ml/src/compare_species_models.py`

Example:

`--species "House Finch"`

The same script supports any species present in the database.
