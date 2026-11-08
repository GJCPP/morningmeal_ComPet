"""Session-only app-to-timer overrides; no URLs, events or persisted app history."""
from dataclasses import dataclass
import math


def app_identity(info):
    bundle = str(getattr(info,'bundle_id','') or '').strip().casefold()
    name = str(getattr(info,'app_name','') or '').strip()
    key = 'bundle:'+bundle if bundle else 'app:'+name.casefold().removesuffix('.exe').removesuffix('.app')
    return (key,name) if bundle or name else None


@dataclass(frozen=True)
class Override:
    timer_id: str
    wall_deadline: float | None
    mono_deadline: float | None

    def remaining(self, wall, mono):
        if self.wall_deadline is None:
            return None
        return max(0,math.ceil(min(self.wall_deadline-wall,self.mono_deadline-mono)))


class ManualOverrides:
    def __init__(self):
        self.entries = {}

    def assign(self, key, timer_id, minutes, wall, mono):
        seconds = None if minutes is None else minutes*60
        self.entries[key] = Override(timer_id,None if seconds is None else wall+seconds,
                                    None if seconds is None else mono+seconds)

    def get(self, key, valid_ids, wall, mono):
        for identity,entry in list(self.entries.items()):
            if entry.timer_id not in valid_ids or entry.remaining(wall,mono)==0:
                del self.entries[identity]
        return self.entries.get(key)

    def cancel(self,key):
        self.entries.pop(key,None)
