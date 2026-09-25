import math


def ceil_units(value: float) -> int:
    """Ceil for positive tile/panel counts with stable float edge handling."""
    return int(math.ceil(float(value) - 1e-9))
