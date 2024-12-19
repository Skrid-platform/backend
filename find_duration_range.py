def find_duration_range(duration, max_distance):
    actual_duration = 1/duration

    actual_min_duration = max(actual_duration - max_distance, 1/16)
    actual_max_duration = actual_duration + max_distance

    min_duration = round(1/actual_min_duration)
    max_duration = round(1/actual_max_duration)

    return min_duration, max_duration

def find_duration_range_decimal(duration, max_distance):
    actual_duration = duration

    actual_min_duration = max(actual_duration - max_distance, 1/16)
    actual_max_duration = actual_duration + max_distance

    return actual_min_duration, actual_max_duration

def find_duration_range_multiplicative_factor_sym(duration, factor, alpha = 0.0):
    """
    Calculates the range of durations for a triangular membership function with a given factor and alpha cut.

    Parameters:
        duration (float): The base duration value.
        factor (float): The multiplicative factor for duration (compression/expansion).
        alpha (float): The alpha cut value (0 <= alpha <= 1).

    Returns:
        tuple: A tuple containing the minimum and maximum durations.
    """
    if not (0 <= alpha <= 1):
        raise ValueError("Alpha must be between 0 and 1.")

    # Compute the distances between the peak and bounds
    if factor < 1:
        low_distance = duration - (duration * factor)
        high_distance = (duration * (1 / factor)) - duration
    elif factor > 1:
        low_distance = duration - (duration * (1 / factor))
        high_distance = (duration * factor) - duration
    else:
        return duration, duration  # No range if factor == 1

    # Scale the distances by (1 - alpha)
    effective_low_distance = low_distance * (1 - alpha)
    effective_high_distance = high_distance * (1 - alpha)

    # Compute the effective bounds
    min_duration = duration - effective_low_distance
    max_duration = duration + effective_high_distance

    return min_duration, max_duration


if __name__ == "__main__":
    # Example usage:
    duration = 1.0
    factor = 2.0
    print(find_duration_range_multiplicative_factor_sym(duration, factor, 0.75))
