import minescript as m
import time, os, traceback

# ================= CONFIG =================
BASE_DIR = os.path.dirname(__file__)
LOG_PATH = os.path.join(BASE_DIR, "Farm_BASE_log.txt")

PAUSE_KEY = 320
WARP_KEY = 330
SET_ORI_KEY = 260
END_KEY = 269  # End

# ================= STATE =================
paused = False
running = True
_last_key_seen = None

# ================= LOGGING =================
with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("=== FARM BASE LOG START ===\n")


def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def log_state(tag: str):
    try:
        x, y, z = m.player_position()
        yaw, pitch = m.player_orientation()
        log(f"[STATE {tag}] pos=({x:.3f},{y:.3f},{z:.3f}) ori=({yaw:.3f},{pitch:.3f}) paused={paused}")
    except Exception as e:
        log(f"STATE ERROR: {e}")

# ================= INPUT =================

def stop_inputs():
    for fn in (
        m.player_press_attack,
        m.player_press_forward,
        m.player_press_backward,
        m.player_press_left,
        m.player_press_right,
    ):
        try:
            fn(False)
        except Exception as e:
            log(f"stop_inputs error: {e}")

# ================= ACTIONS =================

def toggle_pause():
    global paused
    if paused:
        paused = False
        log("[PAUSE] RESUME")
        try:
            m.echo("[HyFarmer] Fortgesetzt")
        except Exception:
            pass
    else:
        paused = True
        stop_inputs()
        log("[PAUSE] PAUSED")
        try:
            m.echo("[HyFarmer] Pausiert")
        except Exception:
            pass


def do_warp():
    log("[WARP] /warp garden")
    try:
        m.echo("[HyFarmer] Warpe zu garden...")
    except Exception:
        pass
    m.execute("/warp garden")


def set_orientation():
    TARGET_YAW = -90.0
    TARGET_PITCH = -58.5
    log(f"[ORI] setting to fixed target ({TARGET_YAW}, {TARGET_PITCH})")
    try:
        m.echo("[HyFarmer] Orientierung auf Farm-Blick gesetzt")
    except Exception:
        pass
    m.player_set_orientation(TARGET_YAW, TARGET_PITCH)

# ---------- JOB KILL ----------

def kill_all_jobs():
    log("=== KILL_ALL START ===")
    try:
        m.echo("[HyFarmer] Beende alle Jobs...")
    except Exception:
        pass

    stop_inputs()

    while True:
        try:
            others = [j for j in m.job_info() if j.status == "RUNNING" and not j.self]
        except Exception:
            others = []

        if not others:
            break

        for j in others:
            log(f"kill job {j.job_id}")
            m.execute(fr"\killjob {j.job_id}")
        time.sleep(0.08)

    # zuletzt uns selbst
    try:
        me = next((j for j in m.job_info() if j.status == "RUNNING" and j.self), None)
        if me:
            log(f"self-kill {me.job_id}")
            m.execute(fr"\killjob {me.job_id}")
    except Exception as e:
        log(f"kill_all_jobs error: {e}")

    log("=== KILL_ALL DONE ===")


# ================= KEY LISTENER =================

def on_key(event):
    global _last_key_seen
    if event['action'] != 1:
        return
    k = event['key']
    log(f"[KEY] {k}")
    _last_key_seen = k

m._register_key_listener(on_key)

log("SCRIPT START")
m.echo("[HyFarmer] Base script gestartet. Numpad0 = Pause/Resume.")
log_state("START")

# ================= MAIN LOOP =================

while running:
    try:
        if _last_key_seen is not None:
            k = _last_key_seen
            _last_key_seen = None

            if k == PAUSE_KEY:
                toggle_pause()
                time.sleep(0.02)
                continue

            if k == WARP_KEY:
                do_warp()
                continue

            if k == SET_ORI_KEY:
                set_orientation()
                continue

            if k == END_KEY:
                kill_all_jobs()
                os._exit(0)


            if k == WARP_KEY:
                do_warp()
                continue
            if k == SET_ORI_KEY:
                set_orientation()
                continue

        if paused:
            time.sleep(0.05)
            continue

        log_state("TICK")
        time.sleep(0.05)

    except Exception as e:
        log(f"CRASH: {e}")
        log(traceback.format_exc())
        stop_inputs()
        time.sleep(1)