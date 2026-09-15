# Machine Learning Methodology

This document describes the stable methodology used by the BirdNET monitoring project for experimental prediction.

It covers both:

- aggregate bird activity prediction
- species-presence prediction

Experiment-specific results belong in:

`docs/experiments/`

Operational instructions belong in:

`ml/README.md`

---

## Goals

The ML work has two current prediction targets.

### Aggregate activity

Predict future BirdNET activity using the project activity index.

### Species presence

Estimate the probability that an individual species will be detected during a future hourly period.

The purpose is not to maximize model complexity.

The priority is:

1. honest temporal validation
2. leakage prevention
3. strong baselines
4. reproducible experiments
5. forward validation using stored live predictions

---

## Prediction Timing

Current live and v2 retrospective models use:

**completed hour T → target hour T+2**

Example:

```text
22:00–23:00   completed input hour T
23:00–00:00   already underway
00:00–01:00   prediction target T+2
```

This avoids pretending to predict an hour that has already started.

A ten-minute grace period is used before considering the previous hour complete enough for prediction and scoring.

The grace period reduces ingestion-race risk but does not prove that every detection has arrived.

---

## Time Zone

The current deployment uses:

`America/Los_Angeles`

Several analytical views store local wall-clock hours as `timestamp without time zone`.

This is convenient for local analysis but has a known DST limitation: the repeated autumn hour cannot always be uniquely represented.

Future multi-station or stricter time-series work should prefer UTC instants together with explicit station/time-zone metadata.

---

# Aggregate Activity Prediction

## Activity Index

Raw detection count can be dominated by repeated calls from one bird.

The project therefore uses a capped activity measure:

```text
capped detections = sum(min(detections per species, 10))
activity index = species count + capped detections
```

This is a project-specific analytical metric, not a standard ecological index.

It reflects recorded BirdNET detections and therefore depends on:

- station uptime
- microphone conditions
- BirdNET configuration
- detection thresholds
- ingestion completeness

---

## Aggregate Dataset

The primary aggregate view is:

`database/views/bird_activity_hourly.sql`

It combines hourly BirdNET activity with weather observations.

Important limitation:

The view is currently weather-backed.

Hours without matching weather data can therefore disappear from the aggregate analytical timeline.

This limitation is one reason the species dataset uses an independent continuous hourly timeline.

---

## Aggregate Features

The current v2 activity model uses:

- `hour_of_day`
- `hours_from_sunrise`
- `is_day`
- current `activity_index`
- activity lag 1h
- activity lag 2h
- activity lag 3h
- activity lag 24h

Weather variables are available in the aggregate view but are not used by the current live Random Forest.

---

## Aggregate Models

Current comparison models include:

- persistence
- Random Forest
- XGBoost

The current live aggregate model remains:

`random_forest_v2_completed`

Random Forest configuration:

```text
n_estimators = 300
min_samples_leaf = 3
random_state = 42
```

XGBoost is retained as a challenger.

The current dataset showed only a very small aggregate XGBoost advantage, which was not large enough to justify replacing the live Random Forest.

See:

`docs/experiments/2026-09-14-activity-models.md`

---

# Species Presence Prediction

## Target

Species prediction is binary:

```text
1 = species detected during target hour
0 = species not detected during target hour
```

The models also produce probabilities.

For sparse species, probability output can be more useful than forcing a present/absent decision at a fixed threshold.

---

## Species Dataset

The species view is:

`database/views/bird_species_hourly.sql`

It creates a continuous hourly timeline for each station and species.

Unlike the aggregate activity view, it is independent of weather availability.

Important fields include:

- `station_id`
- `hour_local`
- `species`
- `species_latin`
- `detection_count`
- `present`
- `avg_confidence`
- `max_confidence`

Hours without detections are explicitly represented as:

```text
detection_count = 0
present = 0
```

This makes the dataset suitable for binary classification.

---

## Species Features

The current classifier uses:

- hour of day
- current species presence
- species presence lag 1h
- species presence lag 2h
- species presence lag 3h
- species presence lag 24h
- current species detection count
- total bird detections
- number of species detected

Weather and sunrise-related features are not yet part of the first species classifier.

---

## Species Models

Current species experiments compare:

- prevalence baseline
- persistence
- Random Forest
- XGBoost

Random Forest:

```text
n_estimators = 300
min_samples_leaf = 3
random_state = 42
```

XGBoost:

```text
n_estimators = 300
max_depth = 3
learning_rate = 0.03
subsample = 0.8
colsample_bytree = 0.8
objective = binary:logistic
tree_method = hist
```

The same generic species code can evaluate different species through a command-line parameter.

There is currently no universal best species model.

Performance depends strongly on species prevalence and behavior.

See:

`docs/experiments/2026-09-14-species-models.md`

---

# Validation

## Chronological Evaluation

Time-series prediction must preserve temporal order.

Random train/test shuffling is not used for the current v2 experiments.

The preferred method is chronological walk-forward validation.

At each simulated prediction time:

1. construct features using information available at that time
2. use only training targets that would already have completed
3. fit the model
4. predict the future target
5. advance through time
6. repeat

This more closely represents live operation than a random split.

---

## Leakage Prevention

A target must not become part of the training set before that target would have been observable in real time.

For the T → T+2 horizon:

```text
feature hour = T
target hour  = T+2
```

During walk-forward validation, training rows are included only when their target hour is already complete at the simulated issue time.

This rule is critical.

Without it, retrospective performance can look substantially better than a real live model.

---

## Baselines

Every model should be compared with a simple baseline.

### Persistence

For activity prediction:

```text
future activity = latest completed activity
```

For species prediction:

```text
future presence = current presence
```

### Prevalence

For species classification, historical prevalence provides another basic probability baseline.

A more complex model should provide meaningful improvement over these simple references.

---

# Metrics

## Regression

Aggregate activity experiments primarily use:

### MAE

Mean Absolute Error.

Easy to interpret and relatively robust to occasional large errors.

### RMSE

Root Mean Squared Error.

Penalizes large prediction errors more strongly.

Models should be compared on exactly the same forecast rows.

---

## Classification

Species experiments use:

- precision
- recall
- F1
- ROC-AUC
- PR-AUC

Accuracy alone is not sufficient because species occurrence is often imbalanced.

For sparse species, a model can achieve high accuracy simply by predicting absence most of the time.

PR-AUC becomes particularly useful as positive examples become rare.

---

# Probability Thresholds

The current binary species output uses a default threshold of:

```text
0.5
```

This is not assumed to be optimal.

The American Crow experiment already showed that a model can have useful ranking ability while performing poorly at the 0.5 threshold.

Future work should evaluate thresholds according to the intended use case.

Examples:

- maximize recall
- balance precision and recall
- minimize false alerts
- surface a ranked likelihood rather than a binary decision

---

# Live Prediction vs Retrospective Experiments

Retrospective experiments answer:

> Would this model have performed well if we had run it historically?

Live prediction answers:

> How well does the model perform when forecasts are actually issued before the outcome occurs?

These are not equivalent.

The project therefore stores live predictions before their target hour occurs and scores them later.

This provides true forward-validation evidence.

Historical experiments remain useful for model development, but long-term model trust should increasingly depend on stored live forecasts and outcomes.

---

# Training Strategy

Current live models are retrained from available historical data when predictions are generated.

There is no persisted model registry or automated champion/challenger deployment system.

This is intentional while the dataset remains relatively small.

Model complexity should increase only when the accumulated data justifies it.

---

# Data Quality Limitations

Prediction quality depends on the integrity of the underlying observations.

Current limitations include:

- the ingestion grace period does not prove completeness
- quiet hours cannot always be distinguished from station outages
- aggregate activity currently depends on weather-backed hourly coverage
- local wall-clock timestamps have DST ambiguity
- late-arriving detections can change historical reality after a forecast has already been scored
- the dataset currently covers only a short time period
- seasonal conclusions are therefore premature

These limitations should be considered when interpreting model performance.

---

# Reproducibility

Important experimental information should be recorded when a meaningful comparison is made.

At minimum:

- experiment date
- prediction horizon
- dataset source
- dataset start and cutoff
- number of usable rows
- validation method
- model parameters
- dependency versions where relevant
- metrics
- interpretation
- decision

Curated experiment results belong in:

`docs/experiments/`

Raw generated output does not need to be committed when the experiment can be reproduced from code and documented parameters.

---

# Current Experiment Records

Aggregate model comparison:

`docs/experiments/2026-09-14-activity-models.md`

Species model comparison:

`docs/experiments/2026-09-14-species-models.md`

---

# Guiding Principle

The raw historical dataset is the long-term asset.

Models can be replaced and retrained.

Preserve:

- detections
- timestamps
- species
- confidence
- station identity
- weather observations
- historical forecasts
- live model predictions
- scored outcomes

Build increasingly sophisticated models only when the accumulated data demonstrates that the additional complexity is useful.
