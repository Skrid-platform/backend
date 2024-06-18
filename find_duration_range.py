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

def find_duration_range_multiplicative_factor(duration, factor):
    if factor < 1:
        min_duration, max_duration = duration * factor, duration
    elif factor > 1:
        min_duration, max_duration = duration, duration * factor
    else:
        min_duration, max_duration = duration, duration
    
    return min_duration, max_duration

if __name__ == "__main__":
    # Example usage:
    duration = 0.25
    factor = 0.5
    print(find_duration_range_multiplicative_factor(duration, factor))
