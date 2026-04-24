"""System-level simulation models."""

try:
    from app.core.models.quarter_car_model import QuarterCarModel, QuarterCarParameters, QuarterCarState
except ModuleNotFoundError:
    # The legacy numeric quarter-car model depends on optional runtime deps.
    QuarterCarModel = None
    QuarterCarParameters = None
    QuarterCarState = None

__all__ = ["QuarterCarModel", "QuarterCarParameters", "QuarterCarState"]
