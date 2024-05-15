def find_duration_range(duration, max_distance):
    actual_duration = 1/duration
    actual_max_distance = max_distance/16

    actual_min_duration = max(actual_duration - actual_max_distance, 1/16)
    actual_max_duration = actual_duration + actual_max_distance

    min_duration = round(1/actual_min_duration)
    max_duration = round(1/actual_max_duration)

    return min_duration, max_duration


if __name__ == "__main__":
    # Example usage:
    duration = 4
    max_distance = 2  # maximum distance in terms of sixteenth notes
    print(find_duration_range(duration, max_distance))
