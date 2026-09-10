"""Spacing and paper-width inputs to the standard constraint layout engine."""

from dataclasses import dataclass, fields
import math


@dataclass
class LayoutOptions:
    column_gap: float = 120.0
    row_gap: float = 70.0
    band_gap: float = 160.0
    band_width: float = 3200.0
    stream_spacing: float = 6.0
    control_passes: int = 6
    control_grid: float = 0.0
    parallel_trains: bool = False

    def validate(self):
        if type(self.control_passes) is not int or self.control_passes < 1:
            raise ValueError("layout_options.control_passes must be a positive integer")
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == 'parallel_trains':
                if type(value) is not bool:
                    raise ValueError('layout_options.parallel_trains must be boolean')
                continue
            if field.name == 'control_grid' and value == 0 and type(value) is not bool:
                continue
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                raise ValueError(f"layout_options.{field.name} must be positive and finite")


def for_units(units):
    first = next(iter(units), None)
    options = first.flowsheet.layout_options if first is not None and first.flowsheet else LayoutOptions()
    options.validate()
    return options
