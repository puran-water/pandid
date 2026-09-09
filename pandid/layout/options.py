"""Spacing and paper-width inputs to the standard constraint layout engine."""

from dataclasses import dataclass, fields
import math


@dataclass
class LayoutOptions:
    column_gap: float = 120.0
    row_gap: float = 70.0
    band_gap: float = 160.0
    band_width: float = 3200.0

    def validate(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                raise ValueError(f"layout_options.{field.name} must be positive and finite")


def for_units(units):
    first = next(iter(units), None)
    options = first.flowsheet.layout_options if first is not None and first.flowsheet else LayoutOptions()
    options.validate()
    return options
