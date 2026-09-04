"""
module2/synthetic_data.py
=========================
Module 2 — Stage 2: Synthetic Trip Generator
EV Range Intelligence Project

PURPOSE:
  Generate a synthetic fleet-trip dataset for Module 2 training/evaluation.

SoH GROUNDING (Correction 3 — CRITICAL):
  SoH is NEVER independently randomized (e.g. random.uniform(50, 100)).
  Instead:
    1. Load test_predictions.csv (Module 1 validation output — read-only).
    2. Sample rows to obtain real battery telemetry distributions.
    3. Pass sampled telemetry through the frozen Module 1 model.
    4. The resulting SoH values come from the model, grounded in real data.

SIMULATION ASSUMPTIONS documented in config.py.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import List, Optional

import numpy as np
import pandas as pd

from module2.adapter import Module1Adapter
from module2.config import (
    # Vehicle spec
    VEHICLE_ID,
    BATTERY_CAPACITY_KWH,
    RATED_RANGE_KM,
    # Distributions
    SOC_BANDS,
    TRIP_DISTANCE_BANDS,
    TEMP_BANDS,
    TERRAIN_MULTIPLIERS,
    TERRAIN_PROBABILITIES,
    # Load
    MIN_LOAD_KG,
    MAX_LOAD_KG,
    # Geography
    LAT_MIN, LAT_MAX,
    LON_MIN, LON_MAX,
    # Module 1 paths
    M1_PREDICTIONS_PATH,
    M1_TELEMETRY_SOURCE_COLUMNS,
)

logger = logging.getLogger(__name__)


class SyntheticTripGenerator:
    """
    Generates a synthetic EV fleet trip dataset grounded in Module 1 outputs.

    Parameters
    ----------
    adapter : Module1Adapter
        Pre-constructed Module 1 adapter (model already loaded).
    seed : int
        Random seed for reproducibility.
    """

    def __init__(self, adapter: Module1Adapter, seed: int = 42):
        self._adapter = adapter
        self._rng = np.random.default_rng(seed)
        self._m1_telemetry: Optional[pd.DataFrame] = None
        self._load_m1_telemetry()

    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE — Load Module 1 telemetry source (read-only)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_m1_telemetry(self) -> None:
        """
        Load test_predictions.csv and extract the telemetry columns.
        This file is read-only. It is NEVER modified by this code.
        """
        if not os.path.isfile(M1_PREDICTIONS_PATH):
            raise FileNotFoundError(
                f"Module 1 predictions file not found: {M1_PREDICTIONS_PATH}"
            )

        df = pd.read_csv(M1_PREDICTIONS_PATH)

        # Verify all required telemetry columns exist
        missing = set(M1_TELEMETRY_SOURCE_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(
                f"test_predictions.csv is missing columns: {missing}"
            )

        # Keep only telemetry + Battery_ID for traceability
        cols_to_keep = ["Battery_ID"] + M1_TELEMETRY_SOURCE_COLUMNS
        self._m1_telemetry = df[cols_to_keep].copy()

        logger.info(
            "Loaded Module 1 telemetry source: %d rows from %d batteries | path=%s",
            len(self._m1_telemetry),
            self._m1_telemetry["Battery_ID"].nunique(),
            M1_PREDICTIONS_PATH,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE — Sampling helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _sample_band(self, bands: list, n: int) -> np.ndarray:
        """
        Sample n values from a banded distribution.
        Each band has keys: min, max, prob.
        Band is chosen by weighted probability; value is uniform within band.
        """
        labels = [b["label"] for b in bands]
        probs  = np.array([b["prob"] for b in bands], dtype=float)
        probs /= probs.sum()  # normalise in case of floating-point drift

        chosen_bands = self._rng.choice(len(bands), size=n, p=probs)
        values = np.array([
            self._rng.uniform(bands[i]["min"], bands[i]["max"])
            for i in chosen_bands
        ])
        return values

    def _sample_terrain(self, n: int) -> List[str]:
        """Sample terrain labels weighted by TERRAIN_PROBABILITIES."""
        terrains = list(TERRAIN_PROBABILITIES.keys())
        probs    = np.array(list(TERRAIN_PROBABILITIES.values()), dtype=float)
        probs   /= probs.sum()
        indices  = self._rng.choice(len(terrains), size=n, p=probs)
        return [terrains[i] for i in indices]

    def _sample_coordinates(self, n: int) -> tuple[np.ndarray, np.ndarray, list, list]:
        """Sample synthetic (lat, lon) strictly snapped to Pune commercial delivery road corridors."""
        try:
            from module3.pune_road_network import sample_road_network_coordinates
            seed = int(self._rng.integers(0, 100000))
            lats, lons, corridors, zones = sample_road_network_coordinates(n, seed=seed)
            return lats, lons, corridors, zones
        except Exception:
            lats = self._rng.uniform(LAT_MIN, LAT_MAX, size=n)
            lons = self._rng.uniform(LON_MIN, LON_MAX, size=n)
            corridors = ["General Urban Road"] * n
            zones = ["Pune Urban"] * n
            return lats, lons, corridors, zones

    def _sample_m1_telemetry_rows(self, n: int) -> pd.DataFrame:
        """
        Sample n rows (with replacement) from the Module 1 test_predictions.csv
        telemetry pool.

        Returns a DataFrame with Battery_ID + M1_TELEMETRY_SOURCE_COLUMNS.
        Row order is randomised; original file is not modified.
        """
        indices = self._rng.integers(0, len(self._m1_telemetry), size=n)
        sampled = self._m1_telemetry.iloc[indices].reset_index(drop=True)
        return sampled

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC — Main generation method
    # ─────────────────────────────────────────────────────────────────────────

    def generate(self, num_trips: int = 5000) -> pd.DataFrame:
        """
        Generate a synthetic fleet-trip dataset.

        Parameters
        ----------
        num_trips : int
            Number of trips to generate.

        Returns
        -------
        pd.DataFrame
            One row per trip. Phase 1 columns:
                trip_id, vehicle_id, latitude, longitude,
                soh_percent, estimated_usable_range_km,
                initial_soc_percent, trip_distance_km,
                ambient_temperature_c, terrain, load_kg,
                battery_capacity_kwh, rated_range_km,
                source_battery_id, discharge_index,
                telemetry_ambient_temp, max_temp_reached,
                charge_rate_proxy, time_since_reset_cycles,
                internal_resistance_re

        Notes
        -----
        SoH values are produced by the frozen Module 1 model applied to
        sampled rows from test_predictions.csv. No SoH values are fabricated.
        """
        logger.info("Starting synthetic trip generation: %d trips", num_trips)

        # ── Step 1: Sample battery telemetry from Module 1 test_predictions.csv ──
        logger.info("Step 1: Sampling %d telemetry rows from test_predictions.csv ...", num_trips)
        telemetry_rows = self._sample_m1_telemetry_rows(num_trips)

        # ── Step 2: Run frozen Module 1 model batch prediction ──
        logger.info("Step 2: Running frozen Module 1 model batch prediction ...")
        predictions = self._adapter.predict_batch(
            telemetry_df=telemetry_rows[M1_TELEMETRY_SOURCE_COLUMNS],
            rated_range_km=RATED_RANGE_KM,
        )

        # ── Step 3: Sample trip context variables ──
        logger.info("Step 3: Sampling trip context variables ...")

        initial_soc     = self._sample_band(SOC_BANDS,           num_trips)
        trip_distance   = self._sample_band(TRIP_DISTANCE_BANDS,  num_trips)
        ambient_temp    = self._sample_band(TEMP_BANDS,           num_trips)
        terrain         = self._sample_terrain(num_trips)
        load_kg         = self._rng.uniform(MIN_LOAD_KG, MAX_LOAD_KG, size=num_trips)
        lats, lons, corridors, zones = self._sample_coordinates(num_trips)
        trip_ids        = [str(uuid.uuid4()) for _ in range(num_trips)]

        # ── Step 4: Assemble the Phase 1 dataset ──
        logger.info("Step 4: Assembling dataset ...")

        df = pd.DataFrame({
            # Identity
            "trip_id":                   trip_ids,
            "vehicle_id":                VEHICLE_ID,

            # Geography (Pune road network corridors)
            "latitude":                  lats.round(6),
            "longitude":                 lons.round(6),
            "delivery_corridor":         corridors,
            "zone":                      zones,

            # Module 1 outputs (grounded in test_predictions.csv telemetry)
            "soh_percent":               predictions["soh_percent"].values,
            "estimated_usable_range_km": predictions["estimated_usable_range_km"].values,

            # Trip context (randomly generated per config distributions)
            "initial_soc_percent":       initial_soc.round(2),
            "trip_distance_km":          trip_distance.round(2),
            "ambient_temperature_c":     ambient_temp.round(2),
            "terrain":                   terrain,
            "load_kg":                   load_kg.round(1),

            # Vehicle spec (fixed from config — NOT randomized)
            "battery_capacity_kwh":      BATTERY_CAPACITY_KWH,
            "rated_range_km":            RATED_RANGE_KM,

            # Telemetry provenance (for SoH grounding audit)
            "source_battery_id":         telemetry_rows["Battery_ID"].values,
            "discharge_index":           telemetry_rows["Discharge_Index"].values,
            "telemetry_ambient_temp":    telemetry_rows["Ambient_Temperature"].values,
            "max_temp_reached":          telemetry_rows["Max_Temp_Reached"].values,
            "charge_rate_proxy":         telemetry_rows["Charge_Rate_Proxy"].values,
            "time_since_reset_cycles":   telemetry_rows["Time_Since_Reset_Cycles"].values,
            "internal_resistance_re":    telemetry_rows["Internal_Resistance_Re"].values,
        })

        logger.info(
            "Generation complete: %d trips | SoH [%.2f%%, %.2f%%] | "
            "Range [%.1f, %.1f] km",
            len(df),
            df["soh_percent"].min(), df["soh_percent"].max(),
            df["estimated_usable_range_km"].min(), df["estimated_usable_range_km"].max(),
        )

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC — SoH distribution report from source data
    # ─────────────────────────────────────────────────────────────────────────

    def soh_source_distribution(self) -> dict:
        """
        Report the SoH distribution from test_predictions.csv (Predicted_SoH column).
        Used to decide if FIS membership functions need calibration.

        Returns
        -------
        dict with: min, max, mean, median, p25, p75, count
        """
        if "Predicted_SoH" not in pd.read_csv(M1_PREDICTIONS_PATH).columns:
            # Fall back to SoH column if Predicted_SoH not present
            col = "SoH"
        else:
            col = "Predicted_SoH"

        df = pd.read_csv(M1_PREDICTIONS_PATH)[col] * 100  # convert 0-1 -> percent

        return {
            "source_column":  col,
            "count":          int(df.count()),
            "min_pct":        round(float(df.min()), 2),
            "max_pct":        round(float(df.max()), 2),
            "mean_pct":       round(float(df.mean()), 2),
            "median_pct":     round(float(df.median()), 2),
            "p25_pct":        round(float(df.quantile(0.25)), 2),
            "p75_pct":        round(float(df.quantile(0.75)), 2),
        }
