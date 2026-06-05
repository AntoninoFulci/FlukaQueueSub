def parse_time_to_seconds(time_str: str) -> int:
    """Parse D-HH:MM:SS time string to seconds."""
    days, rest = time_str.split("-")
    h, m, s = rest.split(":")
    return int(days) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)
