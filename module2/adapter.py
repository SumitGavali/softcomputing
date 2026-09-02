"""
module2/adapter.py
==================
Module 2 — Stage 1: Module 1 Output Adapter
EV Range Intelligence Project

PURPOSE:
  Single interface between Module 2 and the frozen Module 1 model.
  Module 1's api.py, model, preprocessing, and datasets are NEVER modified.

TWO OPERATION MODES:
  BATCH  — loads soh_random_forest_model.pkl directly (used for synthetic generation).
            No HTTP calls. Model loaded once at adapter construction.
  SINGLE — calls the live Module 1 REST API for real-time single-trip inference.
            Uses the exact /predict/soh POST contract from api.py.

FROZEN MODULE 1 CONTRACT (from api.py):
  - Endpoint  : POST /predict/soh
  - Input     : BatteryTelemetry JSON (6 telemetry fields + rated_range_km)
  - Output    : { soh_percent, estimated_usable_range_km, model_error_margin_note }
  - SoH logic : predicted_soh = model.predict(row)[0]   (0.0–1.0 float)
                soh_percent   = round(predicted_soh * 100, 2)
                usable_range  = round(rated_range_km * predicted_soh, 1)
"""

from __future__ import annotations

import os
import logging
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
import requests

from module2.config import (
    M1_MODEL_PATH,
    M1_FEATURE_COLUMNS,
    RATED_RANGE_KM,
)
from module2.schemas import BatteryTelemetryM1, Module1Output

logger = logging.getLogger(__name__)


class Module1Adapter:
    """
    Wraps the frozen Module 1 Random Forest model.

    The adapter is the ONLY point in Module 2 that touches the Module 1 model.
    It enforces that:
      1. The feature DataFrame column names and order exactly match training.
      2. The SoH-to-range conversion formula matches api.py exactly.
      3. Module 1 files are opened read-only and never written to.
    """

    def __init__(self, api_base_url: str = "http://127.0.0.1:8000"):
        """
        Load the frozen Module 1 model once at construction time.

        Parameters
        ----------
        api_base_url : str
            Base URL of the running Module 1 FastAPI server.
            Only used in single/real-time mode.
        """
        if not os.path.isfile(M1_MODEL_PATH):
            raise FileNotFoundError(
                f"Frozen Module 1 model not found at: {M1_MODEL_PATH}\n"
                "Ensure you are running from the project root (cp/) directory."
            )

        # Load model READ-ONLY. joblib.load does not write to the pkl file.
        logger.info("Loading frozen Module 1 model from: %s", M1_MODEL_PATH)
        self._model = joblib.load(M1_MODEL_PATH)
        logger.info("Model loaded: %s", type(self._model).__name__)

        self._api_base_url = api_base_url.rstrip("/")
        self._feature_columns = M1_FEATURE_COLUMNS  # immutable reference

    # ─────────────────────────────────────────────────────────────────────────
    # BATCH MODE — for synthetic trip generation (no HTTP)
    # ─────────────────────────────────────────────────────────────────────────

    def predict_batch(
        self,
        telemetry_df: pd.DataFrame,
        rated_range_km: float = RATED_RANGE_KM,
    ) -> pd.DataFrame:
        """
        Batch-predict SoH and usable range for many telemetry rows.

        Parameters
        ----------
        telemetry_df : pd.DataFrame
            Must contain exactly the columns in M1_FEATURE_COLUMNS,
            in any order (this method reorders internally for safety).
        rated_range_km : float
            Vehicle rated range used in the range formula.
            Default: RATED_RANGE_KM from config (200.0 km).

        Returns
        -------
        pd.DataFrame
            Original DataFrame with two new columns appended:
                soh_percent              (0–100, rounded to 2 dp)
                estimated_usable_range_km (km, rounded to 1 dp)

        Raises
        ------
        ValueError
            If any required feature column is missing.
        """
        # Validate columns
        missing = set(self._feature_columns) - set(telemetry_df.columns)
        if missing:
            raise ValueError(
                f"Missing required Module 1 feature columns: {missing}"
            )

        # Reorder to exact training column order (critical for tree models)
        X = telemetry_df[self._feature_columns].copy()

        # Predict — model returns array of floats in [0, 1]
        raw_predictions: np.ndarray = self._model.predict(X)

        # Apply Module 1's exact conversion formula (from api.py lines 69-74)
        result = telemetry_df.copy()
        result["soh_percent"] = (raw_predictions * 100).round(2)
        result["estimated_usable_range_km"] = (
            rated_range_km * raw_predictions
        ).round(1)

        logger.info(
            "Batch prediction complete: %d rows | SoH range [%.2f, %.2f]%%",
            len(result),
            result["soh_percent"].min(),
            result["soh_percent"].max(),
        )
        return result

    def predict_single_direct(
        self,
        telemetry: BatteryTelemetryM1,
        rated_range_km: float = RATED_RANGE_KM,
    ) -> Module1Output:
        """
        Single-record prediction using the locally loaded model.
        Equivalent to what /predict/soh does, without an HTTP round-trip.
        Used when the Module 1 API server is not running.

        Parameters
        ----------
        telemetry : BatteryTelemetryM1
            Validated telemetry input.
        rated_range_km : float
            Vehicle rated range.

        Returns
        -------
        Module1Output
        """
        # Build a single-row DataFrame matching exact column order (mirrors api.py)
        input_row = pd.DataFrame([{
            "Discharge_Index":          telemetry.discharge_index,
            "Ambient_Temperature":      telemetry.ambient_temperature,
            "Max_Temp_Reached":         telemetry.max_temp_reached,
            "Charge_Rate_Proxy":        telemetry.charge_rate_proxy,
            "Time_Since_Reset_Cycles":  telemetry.time_since_reset_cycles,
            "Internal_Resistance_Re":   telemetry.internal_resistance_re,
        }])

        # Column order re-check (single row, but still enforced)
        input_row = input_row[self._feature_columns]

        raw_soh: float = self._model.predict(input_row)[0]
        soh_percent = round(raw_soh * 100, 2)
        usable_range = round(rated_range_km * raw_soh, 1)

        return Module1Output(
            soh_percent=soh_percent,
            estimated_usable_range_km=usable_range,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SINGLE / REAL-TIME MODE — calls the live Module 1 REST API
    # ─────────────────────────────────────────────────────────────────────────

    def predict_single_via_api(
        self,
        telemetry: BatteryTelemetryM1,
        rated_range_km: float = RATED_RANGE_KM,
        timeout: float = 5.0,
    ) -> Module1Output:
        """
        Real-time single-trip inference via the running Module 1 API.

        Calls POST /predict/soh exactly as documented in api.py.
        The endpoint and request schema are sourced from api.py, NOT assumed.

        Parameters
        ----------
        telemetry : BatteryTelemetryM1
            Validated telemetry input.
        rated_range_km : float
            Forwarded as the rated_range_km field.
        timeout : float
            HTTP request timeout in seconds.

        Returns
        -------
        Module1Output

        Raises
        ------
        requests.HTTPError
            If the Module 1 API returns a non-200 status.
        requests.ConnectionError
            If the Module 1 API server is not running.
        """
        url = f"{self._api_base_url}/predict/soh"  # POST endpoint from api.py

        payload = {
            "discharge_index":          telemetry.discharge_index,
            "ambient_temperature":      telemetry.ambient_temperature,
            "max_temp_reached":         telemetry.max_temp_reached,
            "charge_rate_proxy":        telemetry.charge_rate_proxy,
            "time_since_reset_cycles":  telemetry.time_since_reset_cycles,
            "internal_resistance_re":   telemetry.internal_resistance_re,
            "rated_range_km":           rated_range_km,
        }

        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        return Module1Output(
            soh_percent=data["soh_percent"],
            estimated_usable_range_km=data["estimated_usable_range_km"],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # INTEGRITY CHECK
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def model_type(self) -> str:
        """Return the class name of the loaded Module 1 model."""
        return type(self._model).__name__

    def verify_module1_files_unmodified(self) -> dict:
        """
        Return file metadata for the frozen Module 1 model pkl.
        Used in post-generation verification reports.
        """
        stat = os.stat(M1_MODEL_PATH)
        return {
            "path": M1_MODEL_PATH,
            "size_bytes": stat.st_size,
            "last_modified_timestamp": stat.st_mtime,
        }
