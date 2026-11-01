"""Geometry for timer/pet docking, using (x, y, width, height) rectangles."""
DOCK_OVERLAP = 4


def timer_position_below_pet(pet_rect, timer_size):
    x, y, width, height = pet_rect
    return int(x + (width - timer_size[0]) / 2), y + height - DOCK_OVERLAP


def docking_score(pet_rect, timer_rect, distance):
    """Accept a pet's bottom anchor near a timer's top, regardless of pet height."""
    px, py, pw, ph = pet_rect
    tx, ty, tw, _ = timer_rect
    dx = abs((px + pw / 2) - (tx + tw / 2))
    dy = abs(py + ph - DOCK_OVERLAP - ty)
    if dy <= distance and dx <= tw / 2 + distance:
        return dx + dy
    return None


def snap_timer_rect(moving, others, distance):
    """Snap to nearby timer edges only when their other axis also overlaps."""
    x, y, width, height = moving
    candidates_x, candidates_y = [], []
    for ox, oy, ow, oh in others:
        if y <= oy + oh + distance and y + height >= oy - distance:
            candidates_x.extend((ox - x - width, ox + ow - x, ox - x, ox + ow - x - width))
        if x <= ox + ow + distance and x + width >= ox - distance:
            candidates_y.extend((oy - y - height, oy + oh - y, oy - y, oy + oh - y - height))
    near_x = [delta for delta in candidates_x if abs(delta) <= distance]
    near_y = [delta for delta in candidates_y if abs(delta) <= distance]
    return (x + (min(near_x, key=abs) if near_x else 0),
            y + (min(near_y, key=abs) if near_y else 0))
