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
    aligned_boundaries: bool = False
    instrument_clearance: float = 0.0
    stream_label_bands: int = 7
    strict_label_clearance: bool = False

    def validate(self):
        if type(self.control_passes) is not int or self.control_passes < 1:
            raise ValueError("layout_options.control_passes must be a positive integer")
        if type(self.stream_label_bands) is not int or self.stream_label_bands < 1:
            raise ValueError("layout_options.stream_label_bands must be a positive integer")
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in {'parallel_trains', 'aligned_boundaries', 'strict_label_clearance'}:
                if type(value) is not bool:
                    raise ValueError(f'layout_options.{field.name} must be boolean')
                continue
            if field.name in {'control_grid', 'instrument_clearance'} and value == 0 and type(value) is not bool:
                continue
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                raise ValueError(f"layout_options.{field.name} must be positive and finite")


def for_units(units):
    first = next(iter(units), None)
    options = first.flowsheet.layout_options if first is not None and first.flowsheet else LayoutOptions()
    options.validate()
    return options
