# BirdNET ML Experiments

## Goal

Predict next-hour BirdNET `activity_index` using only information available at the end of the current hour.

Primary metric: **MAE**  
Secondary metric: **RMSE**

Lower is better for both.

---

## Dataset

Initial experiments used roughly 17 days of hourly data from late August through September 2026.

The dataset continues to grow automatically, so exact row counts may change between runs.

Evaluation uses chronological splits only. No random train/test shuffling is used.

---

## 1. Persistence baseline

Prediction:

> Next-hour activity = current-hour activity

Initial 80/20 chronological test:

| Model | MAE | RMSE |
|---|---:|---:|
| Persistence | 4.234 | 7.272 |

This is the baseline that learned models need to beat.

---

## 2. Feature experiments

Using `HistGradientBoostingRegressor`.

| Features | MAE | RMSE |
|---|---:|---:|
| Time only | 4.386 | 6.314 |
| Time + weather | 5.631 | 7.939 |
| Time + recent activity | **3.801** | **5.905** |
| Time + weather + recent activity | 4.619 | 7.208 |

### Observation

Recent bird activity provided the strongest improvement.

Observed weather did not improve the one-hour prediction with the current amount of training data and generally made performance worse.

---

## 3. Model comparison

Winning feature set:

- hour of day
- hours from sunrise
- day/night
- current activity
- 1-hour activity lag
- 2-hour activity lag
- 3-hour activity lag
- 24-hour activity lag

Initial 80/20 chronological comparison:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | **3.764** | 5.916 |
| HistGradientBoosting | 3.801 | **5.905** |
| Poisson Regression | 4.699 | 6.138 |
| Persistence | 4.234 | 7.272 |

Random Forest and HistGradientBoosting performed similarly, with Random Forest slightly better on MAE.

---

## 4. Rolling validation — 48-hour windows

Expanding training window with three 48-hour future test periods.

Average results:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | **3.918** | **6.549** |
| HistGradientBoosting | 4.106 | 6.949 |
| Persistence | 4.528 | 8.548 |

Random Forest beat persistence on MAE in 2 of 3 windows.

---

## 5. Rolling validation — 24-hour windows

Seven expanding-window tests, each predicting the following 24 hours.

| Model | Average MAE | Average RMSE |
|---|---:|---:|
| Random Forest | **3.874** | **6.344** |
| HistGradientBoosting | 3.983 | 6.646 |
| Persistence | 4.274 | 7.885 |

Random Forest reduced average error compared with persistence by roughly:

- **9% MAE**
- **20% RMSE**

It beat persistence on MAE in 4 of the 7 individual daily windows.

This is encouraging, but the dataset is still small and these results should be treated as early evidence rather than a final model evaluation.

---

## 6. Random Forest feature importance

| Feature | Importance |
|---|---:|
| activity_index | 0.404 |
| hours_from_sunrise | 0.279 |
| hour_of_day | 0.117 |
| activity_lag_24h | 0.056 |
| activity_lag_1h | 0.055 |
| activity_lag_2h | 0.045 |
| activity_lag_3h | 0.040 |
| is_day | 0.005 |

The strongest signals are:

1. current bird activity
2. position relative to sunrise
3. time of day

`hours_from_sunrise` appears substantially more informative than the simple day/night flag.

---

## 7. Feature ablation

Random Forest evaluated using the same 24-hour rolling validation.

| Feature set | MAE | RMSE |
|---|---:|---:|
| Full feature set | **3.874** | **6.344** |
| Current activity + sunrise | 3.981 | 6.431 |
| Time only | 4.496 | 7.049 |
| Current activity only | 4.824 | 7.145 |
| Recent lags only | 5.210 | 7.415 |

The full feature set remains best.

Current activity plus sunrise timing captures most of the useful signal, but the additional lag and time features still provide a measurable improvement.

---

## Current conclusion

The strongest model so far is a **Random Forest using time, sunrise-relative timing, current activity, and recent activity history**.

The model appears to contain real predictive signal because it improves on persistence across multiple chronological future test windows.

Weather has not yet improved one-hour forecasts.

The dataset is still small. Model tuning should remain conservative until substantially more historical data has accumulated.
