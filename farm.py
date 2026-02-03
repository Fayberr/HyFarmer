import minescript as m
import time, os, traceback, random

# ================= CONFIG =================
BASE_DIR = os.path.dirname(__file__)
LOG_PATH = os.path.join(BASE_DIR, "Farm_BASE_log.txt")

PAUSE_KEY = 320
WARP_KEY = 330
SET_ORI_KEY = 260
END_KEY = 269

ROW_MIN = -238.68
ROW_MAX =  238.68
PUSH_MIN = 0.25
PUSH_MAX = 2.5

END_ROW_X = -55.3
END_ROW_Z = 238.68
END_TOL = 0.1        # Toleranz, weil Koordinaten nie perfekt sind
WARP_WAIT = 1.2

# ================= STATE =================
paused = True
running = True
_last_key_seen = None

STATE = "FARM_ROW"
row_push_until = 0.0
start_row_x = None

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
        log(
            f"[STATE {tag}] "
            f"pos=({x:.3f},{y:.3f},{z:.3f}) "
            f"ori=({yaw:.3f},{pitch:.3f}) "
            f"state={STATE} paused={paused}"
        )
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

def set_move(attack=False, forward=False, left=False, right=False):
    m.player_press_attack(attack)
    m.player_press_forward(forward)
    m.player_press_left(left)
    m.player_press_right(right)

# ================= DIRECTION =================
def get_direction(x: float):
    row_index = round((x + 88.3) / 3)
    snapped_x = -88.3 + row_index * 3
    direction = "left" if row_index % 2 == 0 else "right"
    log(
        f"[DIR] x={x:.3f} "
        f"snapped_x={snapped_x:.3f} "
        f"row_index={row_index} -> {direction}"
    )
    return direction, snapped_x

def at_field_end(x, z) -> bool:
    return abs(x - END_ROW_X) < END_TOL and abs(z - END_ROW_Z) < END_TOL

# ================= ACTIONS =================
def is_valid_row_x(x: float) -> bool:
    row_index = round((x + 88.3) / 3)
    snapped_x = -88.3 + row_index * 3
    return abs(x - snapped_x) < 0.05

def toggle_pause():
    global paused

    if not paused:
        paused = True
        stop_inputs()
        log("[PAUSE] PAUSED")
        try:
            m.echo("[HyFarmer] Paused")
        except Exception:
            pass
        return

    try:
        x, y, z = m.player_position()
        yaw, pitch = m.player_orientation()
    except Exception as e:
        log(f"[PAUSE] ERROR reading state: {e}")
        return

    if not is_valid_row_x(x):
        log(f"[PAUSE] invalid x={x:.3f}")
        try:
            m.echo("[HyFarmer] Error unpausing: Invalid X coordinate")
        except Exception:
            pass
        return

    if abs(yaw + 90.0) > 0.5 or abs(pitch + 58.5) > 0.5:
        log(f"[PAUSE] wrong orientation yaw={yaw:.2f} pitch={pitch:.2f}")
        try:
            m.echo("[HyFarmer] Error unpausing: Wrong Orientation")
        except Exception:
            pass
        return

    paused = False
    log("[PAUSE] RESUME")
    try:
        m.echo("[HyFarmer] Resumed")
    except Exception:
        pass

def do_warp():
    log("[WARP] /warp garden")
    try:
        m.echo("[HyFarmer] Warping to garden...")
    except Exception:
        pass
    m.execute("/warp garden")

def set_orientation():
    TARGET_YAW = -90.0
    TARGET_PITCH = -58.5
    log(f"[ORI] setting to fixed target ({TARGET_YAW}, {TARGET_PITCH})")
    try:
        m.echo("[HyFarmer] Orientation set to farm view")
    except Exception:
        pass
    m.player_set_orientation(TARGET_YAW, TARGET_PITCH)

def kill_all_jobs():
    log("=== KILL_ALL START ===")
    try:
        m.echo("[HyFarmer] Stopping all jobs...")
    except Exception:
        pass

    stop_inputs()

    while True:
        try:
            others = [j for j in m.job_info()
                       if j.status == "RUNNING" and not j.self]
        except Exception:
            others = []

        if not others:
            break

        for j in others:
            log(f"kill job {j.job_id}")
            m.execute(fr"\killjob {j.job_id}")
        time.sleep(0.08)

    try:
        me = next(
            (j for j in m.job_info()
             if j.status == "RUNNING" and j.self),
            None
        )
        if me:
            log(f"self-kill {me.job_id}")
            m.execute(fr"\killjob {me.job_id}")
    except Exception as e:
        log(f"kill_all_jobs error: {e}")

    log("=== KILL_ALL DONE ===")

# ================= KEY LISTENER =================
def on_key(event):
    global _last_key_seen
    if event["action"] != 1:
        return
    k = event["key"]
    log(f"[KEY] {k}")
    _last_key_seen = k

m._register_key_listener(on_key)

log("SCRIPT START")
m.echo("[HyFarmer] Script started in PAUSE mode. Press Numpad0 to start.")
log_state("START")

# ================= MAIN LOOP =================
while running:
    try:
        if _last_key_seen is not None:
            k = _last_key_seen
            _last_key_seen = None

            if k == PAUSE_KEY:
                toggle_pause()
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

        if paused:
            time.sleep(0.05)
            continue

        now = time.time()
        x, y, z = m.player_position()
        direction, snapped_x = get_direction(x)

        if start_row_x is None:
            start_row_x = snapped_x

        if STATE == "FARM_ROW":

            if start_row_x != snapped_x:
                start_row_x = snapped_x
                msg = "Left" if direction == "left" else "Right"
                log(f"[FARM] start row {snapped_x:.3f} direction={direction}")
                try:
                    m.echo(f"[HyFarmer] Farming {msg} Row")
                except Exception:
                    pass

            m.player_press_attack(True)

            at_wall = (
                (direction == "left" and z <= ROW_MIN) or
                (direction == "right" and z >= ROW_MAX)
            )

            if at_wall and row_push_until == 0.0:
                row_push_until = now + random.uniform(PUSH_MIN, PUSH_MAX)
                log(f"[ROW-PUSH] start until {row_push_until:.3f}")
                try:
                    m.echo(f"[HyFarmer] Extra push to the {direction}")
                except Exception:
                    pass

            if row_push_until != 0.0 and now < row_push_until:
                log(f"[ROW-PUSH] pushing {direction} z={z:.3f}")
                if direction == "left":
                    set_move(attack=True, left=True)
                else:
                    set_move(attack=True, right=True)
                continue

            if row_push_until != 0.0 and now >= row_push_until:
                log("[ROW-PUSH] window ended -> MOVE_FORWARD")
                row_push_until = 0.0
                STATE = "MOVE_FORWARD"
                try:
                    m.echo("[HyFarmer] Moving to next row")
                except Exception:
                    pass
                continue

            if direction == "left" and z > ROW_MIN:
                log(f"[MOVE] row left z={z:.3f}")
                set_move(attack=True, left=True)

            elif direction == "right" and z < ROW_MAX:
                log(f"[MOVE] row right z={z:.3f}")
                set_move(attack=True, right=True)

            else:
                log("[EDGE] no push -> MOVE_FORWARD")
                STATE = "MOVE_FORWARD"
                try:
                    m.echo("[HyFarmer] Moving to next row")
                except Exception:
                    pass
                continue

        elif STATE == "MOVE_FORWARD":

            target_row_x = start_row_x + 3

            # ===== FELD-ENDE HANDLER =====
            if at_field_end(x, z):
                log("[END] reached final row -> warping")
                stop_inputs()

                try:
                    m.echo("[HyFarmer] End of field reached, warping...")
                except Exception:
                    pass

                m.execute("/warp garden")
                time.sleep(WARP_WAIT)

                # nach Warp neu orientieren und neu evaluieren
                x, y, z = m.player_position()
                direction, snapped_x = get_direction(x)

                start_row_x = snapped_x
                STATE = "FARM_ROW"
                row_push_until = 0.0

                try:
                    m.echo("[HyFarmer] Resuming farming after warp")
                except Exception:
                    pass

                continue

            next_direction, target_snap = get_direction(target_row_x)

            log(
                f"[MOVE-FWD] from {start_row_x:.3f} "
                f"-> {target_snap:.3f} via {next_direction}"
            )

            if next_direction == "left":
                set_move(attack=True, forward=True, left=True)
            else:
                set_move(attack=True, forward=True, right=True)

            if abs(x - target_snap) < 0.05:
                log(f"[MOVE-FWD] reached next row {x:.3f}")
                set_move()
                STATE = "FARM_ROW"
                continue

        log_state("TICK")
        time.sleep(0.05)

    except Exception as e:
        log(f"CRASH: {e}")
        log(traceback.format_exc())
        stop_inputs()
        time.sleep(1)