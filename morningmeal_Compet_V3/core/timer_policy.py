"""Pure timer selection, accounting and shared pet association policy."""
import math


def associated_ids(pet, timers):
    valid = [timer['id'] for timer in timers]
    if pet.get('follow_current_timer', False):
        return valid
    values = pet.get('bound_timer_ids')
    if values is None:
        values = [pet.get('bound_timer_id', '')]
    return list(dict.fromkeys(value for value in values if value in valid))


def migrate_preferences(config):
    changed = False
    settings = config.setdefault('settings', {})
    timers, pets = config.get('timers', []), config.get('pets', [])
    valid = [timer['id'] for timer in timers]
    if settings.get('timer_display_mode') != 'current_or_recent':
        settings['timer_display_mode'] = 'current_or_recent'
        changed = True
    for pet in pets:
        if 'bound_timer_ids' not in pet:
            legacy = pet.get('bound_timer_id', '')
            follow = len(pets) == 1 and legacy in valid
            pet['follow_current_timer'] = follow
            pet['bound_timer_ids'] = valid[:] if follow else [legacy] if legacy in valid else []
            changed = True
        ids = associated_ids(pet, timers)
        if pet.get('bound_timer_ids') != ids:
            pet['bound_timer_ids'] = ids
            changed = True
    if settings.get('recent_timer_id') not in valid:
        legacy = next((pet.get('bound_timer_id') for pet in pets if pet.get('bound_timer_id') in valid), None)
        settings['recent_timer_id'] = legacy or (valid[0] if valid else None)
        changed = True
    return changed


def match_score(timer, groups, app_names, title=''):
    names = [str(name).strip().casefold() for name in app_names if name]
    names += [name.removesuffix('.app').removesuffix('.exe') for name in names]
    title = (title or '').strip().casefold()
    score = 0
    for keyword in groups.get(timer.get('group', ''), []):
        if not isinstance(keyword, str) or not keyword.strip():
            continue
        keyword = keyword.strip().casefold()
        if keyword in names:
            score = max(score, 100)
        elif any(keyword in name for name in names):
            score = max(score, 60)
        elif title and keyword in title:
            score = max(score, 20)
        elif any(len(name) >= 3 and name in keyword for name in names):
            score = max(score, 30)
    return score


def select_timer(timers, groups, app_names, title='', recent_id=None):
    candidates = [(match_score(timer, groups, app_names, title), timer['id']) for timer in timers]
    best = max((score for score, _ in candidates), default=0)
    if best == 0:
        return None
    ids = [timer_id for score, timer_id in candidates if score == best]
    return recent_id if recent_id in ids else ids[0]


class TimerSession:
    def __init__(self, recent_id=None):
        self.display_id = recent_id
        self.matched_id = None
        self.reason = 'unmatched'
        self.last_step = None
        self.fractions = {}

    def step(self, config, app_names, title, idle_seconds, now, allowed=True, available=True):
        timers = config.get('timers', [])
        by_id = {timer['id']: timer for timer in timers}
        previous = (self.matched_id, self.reason)
        matched = select_timer(timers, config.get('groups', {}), app_names, title, self.display_id) if available else None
        self.matched_id = matched
        if matched:
            self.display_id = matched
        elif self.display_id not in by_id:
            recent = config.get('settings', {}).get('recent_timer_id')
            self.display_id = recent if recent in by_id else next(iter(by_id), None)
        if not available:
            self.reason = 'unavailable'
        elif not matched:
            self.reason = 'unmatched'
        elif not allowed:
            self.reason = 'permission'
        elif by_id[matched].get('paused', False):
            self.reason = 'paused'
        elif not math.isfinite(idle_seconds) or idle_seconds > by_id[matched].get('idle_timeout', 5):
            self.reason = 'idle'
        else:
            self.reason = 'counting'
        delta = 0 if self.last_step is None else max(0, now - self.last_step)
        self.last_step = now
        updated = {}
        # Never charge a previous application's interval to a new application.
        if delta <= 2 and previous == (matched, 'counting') and self.reason == 'counting':
            total = self.fractions.get(matched, 0) + delta
            seconds = int(total + 1e-9)
            self.fractions[matched] = total - seconds
            if seconds:
                timer = by_id[matched]
                timer['elapsed_seconds'] = timer.get('elapsed_seconds', 0) + seconds
                updated[matched] = timer['elapsed_seconds']
        return updated
