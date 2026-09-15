# Species Prediction

BirdNET species prediction estimates whether an individual species will be detected during a future hourly period.

## Target

Binary presence:

- `1` — species detected
- `0` — species not detected

## Timing

Species models follow the same corrected v2 convention as the aggregate activity model:

**completed hour T → target hour T+2**

This avoids using an hour that is already partially underway.

## Data Model

`bird_species_hourly` provides a continuous hourly series for every species and station.

It includes zero-detection hours explicitly and is independent of weather data availability.

The design supports:

- multiple species
- multiple BirdNET stations
- shared ML code
- species selection by parameter
- future Grafana species filtering

## Validation

Models are evaluated with chronological walk-forward validation.

Training uses only labels that would have been available at the simulated prediction time.

Random train/test splitting is not used.

## Initial Models

- prevalence baseline
- persistence
- Random Forest
- XGBoost

## Metrics

Primary metrics:

- precision
- recall
- F1
- ROC-AUC
- PR-AUC

Accuracy is treated cautiously because species occurrence is often imbalanced.

## Current Status

Initial experiments with House Finch and Black Phoebe show that species-level prediction is feasible with the current dataset.

See:

`docs/experiments/2026-09-14-species-classification-v2.md`
