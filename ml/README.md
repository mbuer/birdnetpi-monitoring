# BirdNET ML

Machine-learning experiments for predicting BirdNET activity from historical detections, time, weather, and eventually weather forecasts.

This lives inside the larger `birdnetpi-monitoring` project.

The first goal is simple:

> Predict the BirdNET activity index for the next hour.

The important part is not choosing an algorithm early. The project should first define the prediction problem clearly, build honest baselines, avoid data leakage, and then compare a few sensible models on future unseen data.

---

## Current Dataset

The initial dataset comes from the PostgreSQL view:

    bird_activity_hourly

It combines hourly BirdNET activity with weather observations.

Current snapshot:

    observations      405 hourly rows
    period            2026-08-27 to 2026-09-13
    active hours      195
    average activity  6.15
    maximum activity  49

The weather fields currently have no missing values.

This is enough to build and validate the ML pipeline, but not enough to make strong claims about seasonal bird behavior. The dataset currently covers only about 17 days.

---

## Activity Index

Raw detection count can be misleading because one persistent bird can generate many detections.

The current activity index therefore combines species diversity with capped detection volume:

    capped detections =
        sum(min(species detections, 10))

    activity index =
        species count + capped detections

This makes repeated calls from one species less dominant.

It is a practical project metric, not an established ecological measure, and can be revisited later if another target proves more useful.

---

## Prediction Features

The first models will use information such as:

    hour of day
    hours from sunrise
    day / night
    temperature
    humidity
    wind
    cloud cover
    precipitation

Recent BirdNET activity will also be tested through lag features such as:

    activity 1 hour ago
    activity 2 hours ago
    activity 3 hours ago
    activity 24 hours ago

`hours_from_sunrise` is particularly useful because bird activity follows the solar day more naturally than a fixed clock time.

---

## Avoiding Data Leakage

For a prediction made at 14:00 for activity at 15:00, the model may only use information that was available by 14:00.

It must never use:

- detections from 15:00
- the 15:00 activity index
- future weather observations
- features calculated using future data

This sounds obvious, but leakage can make a bad model look extremely accurate.

The historical evaluation should reproduce the same information limits that the live model will face.

---

## Weather Observations vs Forecasts

Historical weather observations are useful for understanding relationships between weather and bird activity.

But a real future prediction cannot use weather that has not happened yet.

The project already stores historical weather forecast snapshots using:

    forecast_created_at
    forecast_for

That means later prediction experiments can use the weather forecast that genuinely existed at prediction time instead of accidentally using future observed conditions.

This will become important for forecasts beyond the next hour.

---

## How the ML Approach Is Chosen

The algorithm is deliberately not selected in advance.

The process is:

    establish a simple baseline
            |
            v
    build features
            |
            v
    split data chronologically
            |
            v
    train several reasonable models
            |
            v
    test them on future unseen data
            |
            v
    inspect where they fail
            |
            v
    keep the simplest model that performs well

The first baseline will be:

    next hour activity = current hour activity

A second baseline can use historical activity around the same time of day.

Any ML model should meaningfully outperform these before it is considered useful.

---

## Candidate Models

The first comparison will stay intentionally small.

### Simple regression

Useful as an interpretable reference point.

A Poisson-style model is also worth testing because the target is non-negative and count-like, although the activity index does not necessarily follow a true Poisson distribution.

### Random Forest

A good early nonlinear model for structured data.

It can capture interactions between weather, time, and recent activity without requiring much preprocessing.

### Histogram Gradient Boosting

Another strong candidate for tabular data and nonlinear relationships.

It may outperform simpler approaches, but additional complexity only matters if the test results justify it.

Deep neural networks, LSTMs, Transformers, and large forecasting frameworks are not useful at the current dataset size.

---

## Time-Series Evaluation

The data must not be randomly shuffled.

In reality the system always learns from the past and predicts the future, so evaluation should do the same.

Initially:

    older data     -> training
    newest data    -> testing

As more history becomes available, this can become rolling time-series validation.

The main metrics will be:

    MAE   Mean Absolute Error
    RMSE  Root Mean Squared Error

MAE gives an intuitive average prediction error.

RMSE helps expose models that occasionally make very large mistakes.

Both should always be compared with the baseline.

---

## Zero-Activity Hours

Slightly more than half of the current hours contain no detected bird activity.

The first regression models will simply learn from this distribution.

If they struggle, a later experiment may separate the problem into:

    1. will there be bird activity?
    2. if yes, how much?

There is no reason to add that complexity unless the results show that it helps.

---

## What We Want to Learn

The model score is only part of the project.

The experiments should also help answer questions such as:

- Does weather improve predictions beyond time of day?
- Is activity relative to sunrise more useful than clock time?
- How important is recent bird activity?
- Does yesterday's activity help predict today?
- Does wind suppress detected activity?
- Are large activity bursts predictable?
- Which features stop being useful as the prediction horizon increases?

These questions are more interesting than simply declaring one algorithm the winner.

---

## Experiment Plan

The initial sequence is:

    0. persistence baseline
    1. time features only
    2. time + weather
    3. time + recent activity
    4. combined model
    5. forecast-aware models

Each experiment should record:

    training period
    test period
    features
    model
    MAE
    RMSE
    baseline comparison
    main observation

Results can live under:

    ml/reports/

---

## Repository Structure

```text
ml/
├── README.md
├── requirements.txt
├── src/
│   ├── data.py
│   ├── features.py
│   ├── train.py
│   └── evaluate.py
├── models/
└── reports/
```

The Python environment lives at:

    /opt/birdnetpi-monitoring/.venv

Dependencies are recorded in:

    ml/requirements.txt

The virtual environment itself is not committed.

---

## Current Status

Completed:

- PostgreSQL detection history
- weather observation history
- historical weather forecasts
- hourly BirdNET/weather view
- initial activity index
- data quality check
- Python ML environment
- ML repository structure

Next:

- add `bird_activity_hourly` to version-controlled database configuration
- create the dataset loader
- generate lag features
- implement the baseline
- create the chronological train/test split
- compare the first models
- record the results

---

## Guiding Principle

The goal is not to build the most complicated model.

The goal is to build the simplest model that reliably predicts future activity better than straightforward baselines.

If the data eventually justifies more complexity, we can add it then.
