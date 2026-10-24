"""Shared long-position stop update validation."""
import math


def validate_stop_update(current_stop, new_stop):
    """Accept unchanged or tighter stops; reject widening and invalid values."""
    try:
        current, proposed = float(current_stop), float(new_stop)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid stop") from exc
    if not math.isfinite(proposed) or proposed <= 0:
        raise ValueError("Invalid stop")
    if not math.isfinite(current) or current <= 0:
        raise ValueError("Invalid stop")
    if proposed < current:
        raise ValueError("STOP_WIDENING_FORBIDDEN")
    return proposed
