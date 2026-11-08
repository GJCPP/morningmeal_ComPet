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


def has_fallback_timer(config):
    return any(timer.get('is_fallback', False) for timer in config.get('timers', []))


def matching_timer_ids(timers, groups, app_names, title=''):
    """Return all ordinary matches in list order, or the one fallback timer."""
    app_names = tuple(app_names)
    if not any(str(name).strip() for name in app_names if name) and not (title or '').strip():
        return []
    matches = [timer['id'] for timer in timers
               if not timer.get('is_fallback', False) and match_score(timer, groups, app_names, title)]
    if matches:
        return matches
    fallback = next((timer['id'] for timer in timers if timer.get('is_fallback', False)), None)
    return [fallback] if fallback is not None else []


def select_timer(timers, groups, app_names, title='', recent_id=None):
    # Display priority is list order; recent_id remains accepted for old callers.
    matches = matching_timer_ids(timers, groups, app_names, title)
    return matches[0] if matches else None


def timer_reason(timer, idle_seconds, allowed):
    if not allowed:
        return 'permission'
    if timer.get('paused', False):
        return 'paused'
    if not math.isfinite(idle_seconds) or idle_seconds > timer.get('idle_timeout', 5):
        return 'idle'
    return 'counting'


class TimerSession:
    def __init__(self, recent_id=None):
        self.display_id = recent_id
        self.matched_id = None
        self.matched_ids = []
        self.counting_ids = set()
        self.reason = 'unmatched'
        self.last_step = None
        self.fractions = {}
        self.credited_intervals = {}

    def step(self, config, app_names, title, idle_seconds, now, allowed=True, available=True, update_display=True, override_timer_id=None):
        timers = config.get('timers', [])
        by_id = {timer['id']: timer for timer in timers}
        previously_counting = self.counting_ids
        matches = matching_timer_ids(timers, config.get('groups', {}), app_names, title) if available else []
        if available and override_timer_id in by_id and (any(app_names) or title):
            matches = [override_timer_id]
        self.matched_ids = matches
        self.matched_id = matches[0] if matches else None
        self.counting_ids = {timer_id for timer_id in matches
                             if timer_reason(by_id[timer_id], idle_seconds, allowed) == 'counting'}
        if matches:
            self.display_id = matches[0]
        elif self.display_id not in by_id:
            recent = config.get('settings', {}).get('recent_timer_id')
            self.display_id = recent if recent in by_id else next(iter(by_id), None)
        if not available:
            self.reason = 'unavailable'
        elif not matches:
            self.reason = 'unmatched'
        else:
            self.reason = timer_reason(by_id[matches[0]], idle_seconds, allowed)
        delta = 0 if self.last_step is None else max(0, now - self.last_step)
        self.last_step = now
        updated = {}
        self.credited_intervals = {}
        # Each timer accrues only intervals active at both ends. Shared matches
        # count independently, without charging a newly selected task backwards.
        if delta <= 2:
            for timer_id in matches:
                if timer_id not in previously_counting or timer_id not in self.counting_ids:
                    continue
                self.credited_intervals[timer_id] = delta
                if not update_display:
                    # History owns display baselines and fractional time. Do not
                    # speculatively change its shared configuration mirror.
                    continue
                total = self.fractions.get(timer_id, 0) + delta
                seconds = int(total + 1e-9)
                self.fractions[timer_id] = total - seconds
                if seconds:
                    timer = by_id[timer_id]
                    timer['elapsed_seconds'] = timer.get('elapsed_seconds', 0) + seconds
                    updated[timer_id] = timer['elapsed_seconds']
        return updated
