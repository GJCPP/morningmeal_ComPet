# core/config_manager.py
import os
import sys
import json
import uuid
import shutil
import hashlib
import tempfile

def get_bundle_dir():
    """PyInstaller 번들 내부 또는 소스 코드 루트 경로 반환"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        exe_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.exists(internal_dir):
            return internal_dir
        if sys.platform == 'darwin':
            res_dir = os.path.join(os.path.dirname(exe_dir), "Resources")
            if os.path.exists(res_dir):
                return res_dir
        return exe_dir
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUNDLE_DIR = get_bundle_dir()

# 사용자 데이터 저장소: morningmeal_ComPet
if sys.platform == 'darwin':
    USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/morningmeal_ComPet")
else:
    USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".morningmeal_ComPet")

CONFIG_PATH = os.path.join(USER_DATA_DIR, "config.json")
SKINS_DIR = os.path.join(USER_DATA_DIR, "skins")
USER_SOUNDS_DIR = os.path.join(USER_DATA_DIR, "sounds")
CRASH_LOG_PATH = os.path.join(USER_DATA_DIR, "crash_log.txt")

BUNDLE_SKINS_DIR = os.path.join(BUNDLE_DIR, "assets", "skins")
BUNDLE_SOUNDS_DIR = os.path.join(BUNDLE_DIR, "assets", "sounds")

DEFAULT_SKIN = "羿"
LEGACY_DEFAULT_IMAGES = {'tap_right.png': '09ae75f30cf8d47e028ed79322e32af5f5eb2da16abf5bff22e79d5c0afad797', 'idle.png': 'df1e6851a967ecfa7399ae83ad3423341dcf5c30603fe831704a731b00434cc8', 'tap_left.png': 'd1ff6db22f32ad8e7b678f9ccab05ebdad458d663114ec9899385e51aa2acc24'}

DEFAULT_CONFIG = {
    "settings": {
        "language": "auto",
        "dark_mode": False,
        "tray_mode": False,
        "click_through": False,
        "clamp_to_screen": True,
        "magnetic_snap": True,
        "snap_distance": 15
    },
    "sound": {
        "key_sound_enabled": True,
        "key_volume": 50,
        "key_sound_path": "",
        "click_sound_enabled": True,
        "click_volume": 50,
        "click_sound_path": ""
    },
    "groups": {},
    "timers": [
        {
            "id": str(uuid.uuid4()),
            "name": "작업 1",
            "group": "",
            "idle_timeout": 5,
            "elapsed_seconds": 0,
            "x": 200,
            "y": 300,
            "paused": False
        }
    ],
    "pets": []
}

class ConfigManager:
    def __init__(self):
        self._ensure_dirs()
        self.config = self.load_config()

    def _ensure_dirs(self):
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        os.makedirs(SKINS_DIR, exist_ok=True)
        os.makedirs(USER_SOUNDS_DIR, exist_ok=True)

        default_user_skin = os.path.join(SKINS_DIR, DEFAULT_SKIN)
        bundle_default_skin = os.path.join(BUNDLE_SKINS_DIR, DEFAULT_SKIN)

        if not os.path.exists(default_user_skin):
            if os.path.exists(bundle_default_skin):
                shutil.copytree(bundle_default_skin, default_user_skin)
            else:
                os.makedirs(default_user_skin, exist_ok=True)
                self.save_skin_config(DEFAULT_SKIN, {
                    "name": DEFAULT_SKIN,
                    "squash_depth": 0.20,
                    "enable_bounce": True,
                    "idle_image": "idle.png",
                    "tap_images": ["tap_left.png", "tap_right.png"],
                    "key_mappings": {}
                })

        # Retire only the unchanged original artwork, never a customized skin.
        legacy = os.path.join(SKINS_DIR, 'default')
        if os.path.isdir(legacy):
            names = set(os.listdir(legacy))
            pristine = names <= (set(LEGACY_DEFAULT_IMAGES) | {'config.json'})
            for name, digest in LEGACY_DEFAULT_IMAGES.items():
                path = os.path.join(legacy, name)
                if pristine and os.path.isfile(path):
                    with open(path, 'rb') as image:
                        pristine = hashlib.sha256(image.read()).hexdigest() == digest
                else:
                    pristine = False
            if pristine:
                try:
                    with open(os.path.join(legacy, 'config.json'), encoding='utf-8') as stream:
                        pristine = not json.load(stream).get('key_mappings')
                except (OSError, ValueError):
                    pristine = False
            if pristine:
                archive = os.path.join(USER_DATA_DIR, 'retired-skins')
                os.makedirs(archive, exist_ok=True)
                shutil.move(legacy, os.path.join(archive, 'default-' + uuid.uuid4().hex))

    def load_config(self):
        data = json.loads(json.dumps(DEFAULT_CONFIG))
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for k, v in loaded.items():
                        if isinstance(v, dict) and k in data and k != "groups":
                            data[k].update(v)
                        else:
                            data[k] = v
            except Exception as e:
                print(f"[ConfigManager] Load error: {e}")

        # 기본 펫 인스턴스가 없을 경우 1마리 기본 생성
        if not data.get("pets"):
            first_timer_id = data["timers"][0]["id"] if data.get("timers") else ""
            data["pets"].append({
                "id": str(uuid.uuid4()),
                "skin": DEFAULT_SKIN,
                "scale": 1.0,
                "x": 200,
                "y": 200,
                "bound_timer_id": first_timer_id
            })
        for pet in data.get('pets', []):
            if pet.get('skin', 'default') == 'default' and not os.path.isdir(os.path.join(SKINS_DIR, 'default')):
                pet['skin'] = DEFAULT_SKIN
        return data

    def save_config(self):
        try:
            history_module = sys.modules.get('core.timer_history')
            history = getattr(history_module, '_store', None)
            if history is not None:
                history.sync_timers(self.config.get('timers',[]))
                history.flush()
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=USER_DATA_DIR,
                                                 prefix='.config-', delete=False) as f:
                    temporary = f.name
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, CONFIG_PATH)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
        except Exception as e:
            print(f"[ConfigManager] Save error: {e}")

    def get_skin_config(self, skin_name):
        path = os.path.join(SKINS_DIR, skin_name, "config.json")
        conf = {
            "name": skin_name,
            "squash_depth": 0.20,
            "enable_bounce": True,
            "idle_image": "idle.png",
            "tap_images": ["tap_left.png", "tap_right.png"],
            "key_mappings": {}
        }
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conf.update(json.load(f))
            except Exception:
                pass
        return conf

    def save_skin_config(self, skin_name, data):
        target_dir = os.path.join(SKINS_DIR, skin_name)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, "config.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] Skin config save error for {skin_name}: {e}")

config_mgr = ConfigManager()