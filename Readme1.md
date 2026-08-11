# Phase 1 — Battery SoH & Range Prediction Engine

## Status: Complete (baseline)

A working API that predicts Li-ion battery State of Health (SoH%) and estimated
usable range from telemetry, trained on real NASA degradation data.

---

## 1. Dataset

**Source:** NASA PCoE Battery Dataset (Prognostics Center of Excellence),
34 batteries, cycled to end-of-life under varying ambient temperatures
(4°C, 24°C, 43°C) and discharge protocols.

**After cleaning:** 32 batteries, 2,726 discharge-cycle rows.

### Known dataset limitations (documented honestly, not hidden)
- **2 batteries dropped entirely** (B0050, B0052) — the raw `.mat` parser
  crashed mid-file for both, leaving only 4-21 corrupted rows each.
- **18 rows dropped** where `Capacity_Ahr = 0` — physically impossible for
  a real discharge test; these are sensor/logging dropouts.
- **SoH baseline is NOT the first discharge reading.** Several batteries
  (e.g. B0033) show a real electrochemical "formation" ramp-up over their
  first several cycles, where measured capacity is artificially low while
  the electrode is still stabilizing. Using the first reading as "100%"
  produced nonsensical SoH values up to 2750%. Fixed by using each
  battery's **maximum observed capacity** as its baseline instead
  (standard convention in SoH literature).
- **No real Depth-of-Discharge variation exists in this dataset.** NASA's
  test protocol always discharges every cycle down to the same fixed
  2.7V cutoff — every cycle is effectively a ~100% depth discharge by
  design. A DoD feature was NOT included, since it would either be
  constant (useless) or fabricated. **This is a real gap vs. real-world
  EV telemetry**, where drivers rarely drain a pack to 0% daily —
  worth extending in a later phase with EV-specific data.
- **Lab cells, not EV packs.** These are single 18650-class lab cells
  cycled under controlled conditions, not full EV battery packs under
  real driving loads. Treat this as a methodology proof, not a
  production-ready EV model.

---

## 2. Features used

| Feature | Meaning |
|---|---|
| `Discharge_Index` | Cycle count — how many discharges this battery has been through |
| `Ambient_Temperature` | Room temperature during the test (°C) |
| `Max_Temp_Reached` | Peak internal temperature during that discharge |
| `Charge_Rate_Proxy` | Voltage-drop-rate based proxy for how hard the battery was drained (not true C-rate — no raw current in this summary data) |
| `Time_Since_Reset_Cycles` | How many cycles since the last impedance/reset check |
| `Internal_Resistance_Re` | Most recent measured internal resistance (ohms) — resistance climbs as batteries age |

**Target:** `SoH` (0.0-1.0, i.e. 0-100%)

---

## 3. Model

**Algorithm:** Random Forest Regressor (scikit-learn), 200 trees, max depth 10.

**Why Random Forest first:** per project plan, get a working baseline
before attempting ANFIS. No heavy tuning required, handles non-linear
feature interactions (e.g. temp × resistance) well out of the box.

**Train/test split:** by **Battery_ID**, not random rows — and
**stratified by ambient temperature group** (4°C / 24°C / 43°C), so
every temperature regime is represented in both train and test. This
tests genuine generalization to *unseen batteries*, not memorization
of a battery's own curve.

- Train: 26 batteries
- Test: 6 batteries (unseen during training)

---

## 4. Validation results

| Metric | Value |
|---|---|
| RMSE (aggregate, unseen batteries) | **12.06 percentage points of SoH** |
| MAE (aggregate, unseen batteries) | **7.08 percentage points of SoH** |

Within the brief's stated "±10% is fine" threshold for MAE; RMSE is
somewhat above it, pulled up by two harder batteries (see below).

### Per-battery breakdown (honesty over cherry-picking)

| Battery | Ambient Temp | RMSE | MAE |
|---|---|---|---|
| B0041 | 4°C (cold) | 6.4% | 2.7% |
| B0034 | 24°C | 7.1% | 5.5% |
| B0005 | 24°C | 9.4% | 7.2% |
| B0044 | 4°C (cold) | 13.7% | 5.7% |
| B0038 | 24-44°C | 18.4% | 11.8% |
| B0029 | 43°C (hot) | 23.3% | 13.7% |
| B0049 | 4°C (cold) | 19.5% | 17.4% |

**Honest takeaway:** the model performs well on room-temperature and
moderate conditions, but degrades on extreme-temperature batteries
(43°C hot, some 4°C cold) and batteries with fewer training examples
in that temperature regime. This is a real limitation of a small,
lab-controlled dataset, not something to paper over — flag it as a
target for improvement in a later phase (more data per temperature
group, or ANFIS's fuzzy-rule handling of "high temp + high cycles").

See `validation_plot.png` for the predicted-vs-actual scatter and
an example degradation curve (B0005, unseen during training).

---

## 5. API

**Endpoint:** `POST /predict/soh`

### Request
```json
{
  "discharge_index": 100,
  "ambient_temperature": 25,
  "max_temp_reached": 35,
  "charge_rate_proxy": 0.8,
  "time_since_reset_cycles": 5,
  "internal_resistance_re": 0.05,
  "rated_range_km": 300
}
```

### Response
```json
{
  "soh_percent": 84.24,
  "estimated_usable_range_km": 252.7,
  "model_error_margin_note": "Baseline model MAE ~7%, RMSE ~12% on unseen batteries (worse on extreme hot/cold conditions - see validation report)"
}
```

### Input validation
All fields are bounded to the actual range seen in training data.
Inputs outside these ranges return a `422` error rather than a silent,
unreliable extrapolated prediction (the model has never seen those
conditions, so a guess there isn't trustworthy):

| Field | Valid range |
|---|---|
| `discharge_index` | 1 - 250 |
| `ambient_temperature` | 0 - 50 °C |
| `max_temp_reached` | 0 - 80 °C |
| `charge_rate_proxy` | 0 - 30 |
| `time_since_reset_cycles` | 0 - 20 |
| `internal_resistance_re` | 0.01 - 0.3 ohms |
| `rated_range_km` | 0 - 1000 (exclusive of 0) |

**Range formula:** `usable_range_km = rated_range_km * (SoH / 100)` —
a simple, defensible heuristic. Not a second model. Deliberately kept
simple for Phase 1 per project plan.

### Other endpoints
- `GET /` — basic liveness message
- `GET /health` — confirms model is loaded and ready

---

## 6. How to run

```bash
pip install fastapi uvicorn scikit-learn pandas joblib

# Scripts run in order:
python3 01_clean_data.py            # -> battery_dataset_clean.csv
python3 02_feature_engineering.py   # -> battery_dataset_features.csv
python3 03_train_model.py           # -> soh_random_forest_model.pkl
python3 04_validate_plot.py         # -> validation_plot.png

# Then start the API:
uvicorn 05_api:app --reload --port 8000
# Interactive docs at http://127.0.0.1:8000/docs
```

---

## 7. What's explicitly OUT of scope for Phase 1 (by design)

Per the project plan, these are deferred to later phases, not oversights:
- ANFIS (fuzzy-rule hybrid model) — Phase 1 uses Random Forest baseline only
- Perfecting accuracy / closing the hot/cold error gap — Phase 4
- Real EV telemetry / varying depth-of-discharge — needs a different dataset
- CALCE or multi-chemistry generalization — optional Phase 2+ extension

**Phase 1 goal met:** working end-to-end pipeline, credible SoH/range
number, validated against real NASA degradation data, with error
margins and limitations documented honestly rather than hidden.