"""
module2/margin_calculator.py
============================
Module 2 — Stage 4: Range Sufficiency / Margin Calculator
EV Range Intelligence Project

PURPOSE:
  Compute available_range_km, range_margin_km, range_margin_percent,
  and trip_feasible_without_charging from Phase 1 + Phase 3 energy columns.

SIMULATION ASSUMPTION (documented explicitly):
  The available_range formula below is a LINEAR approximation.
  Real Li-ion batteries have a nonlinear SOC-to-voltage curve;
  the relationship between SOC% and usable range is not perfectly linear,
  especially at the tails (<20% and >90% SOC).
  This linear model is accepted as a first-order prototype approximation only.

EXACT FORMULAS (must not be silently changed):

  usable_soc_percent =
      max(0, initial_soc_percent - SAFETY_RESERVE_SOC_PCT)

  available_range_km =
      estimated_usable_range_km * usable_soc_percent / 100

  range_margin_km =
      available_range_km - effective_trip_demand_km

  range_margin_percent =
      (range_margin_km / effective_trip_demand_km) * 100
      (guarded against zero/near-zero denominator)

  trip_feasible_without_charging =
      available_range_km >= effective_trip_demand_km

  NOTE: The 15% SAFETY_RESERVE_SOC_PCT is applied ONCE HERE in the
        usable_soc calculation. It is NOT added again in downstream stages.
        The range_margin already accounts for the reserve because
        available_range already excludes the reserved 15% SOC.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from module2.config import SAFETY_RESERVE_SOC_PCT

logger = logging.getLogger(__name__)

# Denominator guard: values below this (km) are treated as zero
_EFFECTIVE_DEMAND_FLOOR = 1e-6


class RangeMarginCalculator:
    """
    Computes available range and range margin for each trip.

    Requires columns produced by TripEnergyDemandModel:
        effective_trip_demand_km

    Requires columns from Phase 1:
        initial_soc_percent, estimated_usable_range_km
    """

    def compute_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add range-margin columns to a copy of the Phase 2 DataFrame.

        Required input columns:
            initial_soc_percent
            estimated_usable_range_km
            effective_trip_demand_km

        Added output columns:
            usable_soc_percent          (15% reserve already deducted)
            available_range_km          (linear approximation — see module docstring)
            range_margin_km
            range_margin_percent
            trip_feasible_without_charging

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame that already contains Phase 1 + energy model columns.

        Returns
        -------
        pd.DataFrame
            Input DataFrame with 5 new columns appended.
        """
        self._validate_columns(df)
        result = df.copy()

        # ── Step 1: Usable SOC after safety reserve ──────────────────────────
        # Safety reserve applied ONCE here.
        result["usable_soc_percent"] = np.maximum(
            0.0,
            result["initial_soc_percent"] - SAFETY_RESERVE_SOC_PCT
        ).round(4)

        # ── Step 2: Available range (linear SOC approximation) ───────────────
        # ⚠️ SIMULATION ASSUMPTION: linear SOC-to-range mapping.
        result["available_range_km"] = (
            result["estimated_usable_range_km"]
            * result["usable_soc_percent"]
            / 100.0
        ).round(4)

        # ── Step 3: Range margin (km) ────────────────────────────────────────
        result["range_margin_km"] = (
            result["available_range_km"] - result["effective_trip_demand_km"]
        ).round(4)

        # ── Step 4: Range margin (%) — guarded denominator ───────────────────
        denom = result["effective_trip_demand_km"].where(
            result["effective_trip_demand_km"].abs() > _EFFECTIVE_DEMAND_FLOOR,
            other=np.nan
        )
        result["range_margin_percent"] = (
            result["range_margin_km"] / denom * 100.0
        ).round(2)

        # ── Step 5: Feasibility flag ─────────────────────────────────────────
        # NOTE: Named trip_feasible_without_charging (NOT charging_required).
        # The final charging_required decision is made by the FIS/recommendation
        # layer in Phase 3, which may incorporate additional fuzzy logic.
        result["trip_feasible_without_charging"] = (
            result["available_range_km"] >= result["effective_trip_demand_km"]
        )

        n_feasible   = result["trip_feasible_without_charging"].sum()
        n_infeasible = (~result["trip_feasible_without_charging"]).sum()
        logger.info(
            "Range margin complete: %d rows | "
            "feasible=%d (%.1f%%) | infeasible=%d (%.1f%%)",
            len(result),
            n_feasible,   100 * n_feasible   / len(result),
            n_infeasible, 100 * n_infeasible / len(result),
        )
        return result

    def compute_single(
        self,
        initial_soc_percent: float,
        estimated_usable_range_km: float,
        effective_trip_demand_km: float,
    ) -> dict:
        """
        Scalar computation for unit tests and single-trip API.

        Returns
        -------
        dict with keys:
            usable_soc_percent, available_range_km,
            range_margin_km, range_margin_percent,
            trip_feasible_without_charging
        """
        usable_soc = max(0.0, initial_soc_percent - SAFETY_RESERVE_SOC_PCT)
        available  = estimated_usable_range_km * usable_soc / 100.0
        margin_km  = available - effective_trip_demand_km

        if abs(effective_trip_demand_km) > _EFFECTIVE_DEMAND_FLOOR:
            margin_pct = (margin_km / effective_trip_demand_km) * 100.0
        else:
            margin_pct = float("nan")

        return {
            "usable_soc_percent":             round(usable_soc, 4),
            "available_range_km":             round(available, 4),
            "range_margin_km":                round(margin_km, 4),
            "range_margin_percent":           round(margin_pct, 2) if not np.isnan(margin_pct) else float("nan"),
            "trip_feasible_without_charging": available >= effective_trip_demand_km,
        }

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = {
            "initial_soc_percent",
            "estimated_usable_range_km",
            "effective_trip_demand_km",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
