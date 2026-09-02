"""
module2/energy_model.py
=======================
Module 2 — Stage 3: Trip Energy Demand Model
EV Range Intelligence Project

PURPOSE:
  Apply terrain, temperature, and load multipliers to base trip energy
  to compute trip_energy_demand_kwh and effective_trip_demand_km.

IMPORTANT — Single-application rule:
  - Temperature multiplier is applied HERE and NEVER in the FIS.
  - Terrain multiplier is applied HERE and NEVER in the FIS.
  - Load multiplier is applied HERE and NEVER in the FIS.
  - Safety buffer (x1.10) is applied HERE and NEVER again downstream.

EXACT FORMULA (documented, must not be silently changed):

  base_energy_kwh = trip_distance_km * BASE_ENERGY_KWH_PER_KM

  trip_energy_demand_kwh =
      base_energy_kwh
      * terrain_multiplier
      * temperature_multiplier
      * load_multiplier
      * SAFETY_BUFFER_FACTOR                   # applied exactly once (1.10)

  effective_trip_demand_km =
      trip_energy_demand_kwh / BASE_ENERGY_KWH_PER_KM

  Unit check:
      [kWh] / [kWh/km] = [km]  ✓
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from module2.config import (
    BASE_ENERGY_KWH_PER_KM,
    TERRAIN_MULTIPLIERS,
    TEMP_BREAKPOINTS,
    REFERENCE_LOAD_KG,
    LOAD_PENALTY_FRACTION_PER_KG,
    SAFETY_BUFFER_FACTOR,
)

logger = logging.getLogger(__name__)


class TripEnergyDemandModel:
    """
    Computes trip energy demand and effective trip demand (in km).

    All environmental and load factors are resolved here.
    The Fuzzy Inference System receives only the computed outputs
    (effective_trip_demand_km, range_margin_km), not these raw factors.
    """

    # Unpack the breakpoints into separate x, y arrays for np.interp
    _TEMP_X = np.array([bp[0] for bp in TEMP_BREAKPOINTS], dtype=float)
    _TEMP_Y = np.array([bp[1] for bp in TEMP_BREAKPOINTS], dtype=float)

    # ─────────────────────────────────────────────────────────────────────────
    # Public: vectorised batch computation (operates on a DataFrame)
    # ─────────────────────────────────────────────────────────────────────────

    def compute_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add energy-demand columns to a copy of the Phase 1 DataFrame.

        Required input columns:
            trip_distance_km, ambient_temperature_c, terrain, load_kg

        Added output columns:
            base_energy_demand_kwh
            terrain_multiplier
            temperature_multiplier
            load_multiplier
            trip_energy_demand_kwh
            effective_trip_demand_km

        Parameters
        ----------
        df : pd.DataFrame
            Phase 1 trip dataset (phase1_trips.csv).

        Returns
        -------
        pd.DataFrame
            Input DataFrame with 6 new columns appended.
        """
        self._validate_columns(df)

        result = df.copy()

        # ── Step 1: Base energy ──────────────────────────────────────────────
        result["base_energy_demand_kwh"] = (
            result["trip_distance_km"] * BASE_ENERGY_KWH_PER_KM
        )

        # ── Step 2: Terrain multiplier ───────────────────────────────────────
        result["terrain_multiplier"] = result["terrain"].map(TERRAIN_MULTIPLIERS)
        unknown_terrain = result["terrain_multiplier"].isna().sum()
        if unknown_terrain > 0:
            bad = result.loc[result["terrain_multiplier"].isna(), "terrain"].unique()
            raise ValueError(
                f"{unknown_terrain} rows contain unknown terrain labels: {bad}. "
                f"Valid labels: {list(TERRAIN_MULTIPLIERS.keys())}"
            )

        # ── Step 3: Temperature multiplier (piecewise linear) ────────────────
        result["temperature_multiplier"] = self._temperature_multiplier_vectorised(
            result["ambient_temperature_c"].values
        )

        # ── Step 4: Load multiplier ──────────────────────────────────────────
        result["load_multiplier"] = self._load_multiplier_vectorised(
            result["load_kg"].values
        )

        # ── Step 5: Final trip energy demand (safety buffer applied ONCE) ────
        result["trip_energy_demand_kwh"] = (
            result["base_energy_demand_kwh"]
            * result["terrain_multiplier"]
            * result["temperature_multiplier"]
            * result["load_multiplier"]
            * SAFETY_BUFFER_FACTOR
        ).round(4)

        # ── Step 6: Effective trip demand in km ──────────────────────────────
        # effective_trip_demand_km = trip_energy_demand_kwh / BASE_ENERGY_KWH_PER_KM
        # Unit: [kWh] / [kWh/km] = [km]
        result["effective_trip_demand_km"] = (
            result["trip_energy_demand_kwh"] / BASE_ENERGY_KWH_PER_KM
        ).round(4)

        logger.info(
            "Energy model complete: %d rows | energy [%.3f, %.3f] kWh | "
            "effective demand [%.2f, %.2f] km",
            len(result),
            result["trip_energy_demand_kwh"].min(),
            result["trip_energy_demand_kwh"].max(),
            result["effective_trip_demand_km"].min(),
            result["effective_trip_demand_km"].max(),
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Public: scalar computation (for unit tests and single-trip API)
    # ─────────────────────────────────────────────────────────────────────────

    def compute_single(
        self,
        trip_distance_km: float,
        ambient_temperature_c: float,
        terrain: str,
        load_kg: float,
    ) -> dict:
        """
        Compute energy demand for a single trip.

        Returns
        -------
        dict with keys:
            base_energy_demand_kwh, terrain_multiplier,
            temperature_multiplier, load_multiplier,
            trip_energy_demand_kwh, effective_trip_demand_km
        """
        if terrain not in TERRAIN_MULTIPLIERS:
            raise ValueError(
                f"Unknown terrain '{terrain}'. "
                f"Valid: {list(TERRAIN_MULTIPLIERS.keys())}"
            )

        base_energy = trip_distance_km * BASE_ENERGY_KWH_PER_KM
        t_mult      = float(TERRAIN_MULTIPLIERS[terrain])
        temp_mult   = float(np.interp(ambient_temperature_c, self._TEMP_X, self._TEMP_Y))
        load_mult   = self._load_multiplier_scalar(load_kg)

        trip_energy = base_energy * t_mult * temp_mult * load_mult * SAFETY_BUFFER_FACTOR
        effective_km = trip_energy / BASE_ENERGY_KWH_PER_KM

        return {
            "base_energy_demand_kwh":   round(base_energy, 6),
            "terrain_multiplier":        round(t_mult, 6),
            "temperature_multiplier":    round(temp_mult, 6),
            "load_multiplier":           round(load_mult, 6),
            "trip_energy_demand_kwh":    round(trip_energy, 6),
            "effective_trip_demand_km":  round(effective_km, 6),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _temperature_multiplier_vectorised(cls, temps: np.ndarray) -> np.ndarray:
        """
        Piecewise-linear temperature multiplier using TEMP_BREAKPOINTS.
        np.interp clips out-of-range values to the boundary values automatically,
        which matches the "cap at 1.15 below 12°C and above 42°C" design.
        """
        return np.interp(temps, cls._TEMP_X, cls._TEMP_Y).round(6)

    @classmethod
    def _load_multiplier_vectorised(cls, loads: np.ndarray) -> np.ndarray:
        """
        load_multiplier = 1.0 + (load_kg - REFERENCE_LOAD_KG) * PENALTY
        Values below reference produce multiplier < 1.0 (lighter vehicle uses less energy).
        Values are not floored — the minimum at min_load (70 kg) is:
          1.0 + (70-150)*0.0015 = 0.88, which is physically valid.
        """
        return (1.0 + (loads - REFERENCE_LOAD_KG) * LOAD_PENALTY_FRACTION_PER_KG).round(6)

    @staticmethod
    def _load_multiplier_scalar(load_kg: float) -> float:
        return round(
            1.0 + (load_kg - REFERENCE_LOAD_KG) * LOAD_PENALTY_FRACTION_PER_KG, 6
        )

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = {"trip_distance_km", "ambient_temperature_c", "terrain", "load_kg"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
