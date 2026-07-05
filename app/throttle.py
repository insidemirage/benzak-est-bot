def get_retry_after(
    last_check_at: dict[int, float],
    user_id: int,
    now: float,
    throttle_seconds: int,
) -> int:
    previous_check_at = last_check_at.get(user_id)
    if previous_check_at is None:
        return 0

    elapsed = now - previous_check_at
    if elapsed >= throttle_seconds:
        return 0

    return int(throttle_seconds - elapsed) + 1
