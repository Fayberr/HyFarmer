import system.lib.minescript as m

import time, os, traceback, random, winsound, mss, requests, pygetwindow as gw, tempfile, threading

from config import discord_webhook_url

# ================= CONFIG =================
BASE_DIR = os.path.dirname(__file__)
LOG_PATH = os.path.join(BASE_DIR, "FarmLog.txt")

PAUSE_KEY = 320
WARP_KEY = 330
SET_ORI_KEY = 260
END_KEY = 269

ROW_MIN = -238.68
ROW_MAX =  238.68
PUSH_MIN = 0.10
PUSH_MAX = 1.5

END_ROW_X = -55.3
END_ROW_Z = 238.68
END_TOL = 0.1 # Usually 0.1

END_HARD_WAIT = 2.0
END_EXTRA_MIN = 1.0
END_EXTRA_MAX = 2.0

WARP_WAIT = 1.2
POST_WARP_MIN = 0.75
POST_WARP_MAX = 1.0

LAST_POS = 0

FARM_ITEM = "diamond_axe"

webhook_alert = True

WARN_SOUND_PATH = r"C:\Users\derfa\AppData\Roaming\ModrinthApp\profiles\Skyblock 1.21.10 1.0.0\minescript\assets\AnvilLand.wav"

# ================= STATE =================
paused = True
running = True
_last_key_seen = None
attack_held = False
pause_script = False

STATE = "FARM_ROW"
row_push_until = 0.0
start_row_x = None


# ================= LOGGING ================
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
            f"state={STATE} paused={paused} attack_held={attack_held}"
        )
    except Exception as e:
        log(f"STATE ERROR: {e}")
# ================= Helper =================

def alert(alert_msg, sound, send_screenshot):

    log(f"[ALERT] {alert_msg}")

    m.echo(f"[ALERT] §c{alert_msg}")

    if sound == "default":
        play_sound(WARN_SOUND_PATH)

    elif sound == "beep":
        beep()

    elif sound == "None":
        pass

    else:
        log(f"[ERROR] Alert tried to play an invalid sound ({str(sound)})")

    if webhook_alert and discord_webhook_url:
        webhook(f"[ALERT] {alert_msg}", send_screenshot)


def play_sound(sound_path):
    try:
        winsound.PlaySound(
            fr"{sound_path}",
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    except Exception as e:
        m.echo(f"§c[ERROR] {e}§r")

def beep():
    winsound.Beep(1000, 300)

def player_items():
    items = m.player_hand_items()

    mainhand_item = items.main_hand
    offhand_item = items.off_hand

    return mainhand_item, offhand_item

def failsafe():
    ori = m.player_orientation()

    x, y, z = m.player_position()

    if not player_items()[0]['item'].split(":")[1] == FARM_ITEM:
        log("[FAILSAFE] Detected not holding Farming Item")
        return True, "Item not Farm Item", "default"

    if abs(ori[0] + 90.0) > 0.1 or abs(ori[1] + 58.5) > 0.1:
        log("[FAILSAFE] Detected wrong Orientation")
        return True, "Orientation not correct", "beep"

    if not (-90 <= x < -55) or not (66 <= y < 69) or not (-240 <= z < 240):
        log("[FAILSAFE] Detected wrong Coordinates (OUT OF FARM)")
        return True, "Coordinates outside of Farm", "default"

    if not is_valid_row_x(x) and (ROW_MIN + 1 < z < ROW_MAX - 1):
        log("[FAILSAFE] Detected invalid X ")
        return True, "Invalid X Coordinate", "beep"


    return False, "None", "None"

def webhook(content, send_screenshot=False):
    if not discord_webhook_url:
        return

    def worker():
        files = None

        if send_screenshot:
            wins = gw.getWindowsWithTitle("Minecraft")
            if wins:
                with mss.mss() as sct:
                    img = sct.grab((wins[0].left, wins[0].top, wins[0].right, wins[0].bottom))

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    mss.tools.to_png(img.rgb, img.size, output=f.name)
                    files = {"file": open(f.name, "rb")}

        requests.post(
            discord_webhook_url,
            files=files,
            data={"content": content} if files else None,
            json=None if files else {"content": content},
        )

    threading.Thread(target=worker, daemon=True).start()

def webhook_is_valid():
    if not discord_webhook_url:
        log("[WEBHOOK] Webhook url is None")
        return False

    elif discord_webhook_url == "":
        log('[WEBHOOK] Webhook url is ""')
        return False

    elif not discord_webhook_url.startswith("https://discordapp.com/api/webhooks/"):
        log('[WEBHOOK] Webhook url doesnt have the proper Format')
        return False

    else:
        log(f'[WEBHOOK] Webhook url is likely Valid: "{discord_webhook_url}"')
        return True


# ================= INPUT =================
def stop_inputs():
    global attack_held
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
    attack_held = False

def set_move(forward=False, left=False, right=False):
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

def ensure_attack():
    global attack_held
    if not attack_held:
        m.player_press_attack(True)
        attack_held = True
        log("[ATTACK] locked ON")

def toggle_pause():
    global paused, attack_held

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

    if not (-90 <= x < -55) or not (66 <= y < 69) or not (-240 <= z < 240):
        log(f"[PAUSE] Outside Farm")
        try:
            m.echo("[HyFarmer] §eError unpausing: Outside of Farm")
        except Exception:
            pass
        return

    if not is_valid_row_x(x):
        log(f"[PAUSE] invalid x={x:.3f}")
        try:
            m.echo("[HyFarmer] §eError unpausing: Invalid X coordinate")
        except Exception:
            pass
        return

    if abs(yaw + 90.0) > 0.5 or abs(pitch + 58.5) > 0.5:
        log(f"[PAUSE] Wrong orientation yaw={yaw:.2f} pitch={pitch:.2f}")
        try:
            m.echo("[HyFarmer] §eError unpausing: Wrong Orientation")
        except Exception:
            pass
        return

    if player_items()[0]['item'].split(":")[1] != FARM_ITEM:
        log(f"[PAUSE] Not holding Farm Item")
        try:
            m.echo("[HyFarmer] §eError unpausing: Not holding Farm Item")
        except Exception:
            pass
        return



    paused = False
    ensure_attack()
    log("[PAUSE] RESUME (attack locked)")
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
    stop_inputs()
    m.execute("/warp garden")

# ================= ORIENTATION =================
def set_orientation():
    TARGET_YAW = -90.0
    TARGET_PITCH = -58.5
    log(f"[ORI] setting to fixed target ({TARGET_YAW}, {TARGET_PITCH})")
    try:
        m.echo("[HyFarmer] Orientation set to farm view")
    except Exception:
        pass
    m.player_set_orientation(TARGET_YAW, TARGET_PITCH)

# ================= JOB CONTROL =================
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

# ================= LISTENER =================
def on_key(event):
    global _last_key_seen
    if event["action"] != 1:
        return
    k = event["key"]
    log(f"[KEY] {k}")
    _last_key_seen = k

def on_chat(event):
    global pause_script
    log(f"[Key] {event}")

    msg = event['message']

    if "Evacuating" in msg:
        log("[FAILSAFE] §eEvacuation detected, pausing...")
        m.echo("[HyFarmer] §eEvacuation detected, pausing...")
        pause_script = True
        return

    if "limbo" in msg:
        log("[FAILSAFE] §eLimbo detected, pausing...")
        m.echo("[HyFarmer] §eLimbo detected, pausing...")
        pause_script = True
        return



m._register_chat_message_listener(on_chat)
m._register_key_listener(on_key)

log("SCRIPT START")
m.echo("[HyFarmer] Script started in PAUSE mode. Press Numpad0 to start.")

if not webhook_is_valid():
    m.echo("[HyFarmer] §eThe configured Discord webhook is Invalid (See Reason in Log). Disabling...")
    discord_webhook_url = None
else:
    m.echo("[HyFarmer] §aVerified Discord webhook")

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

        ensure_attack()

        now = time.time()
        x, y, z = m.player_position()
        direction, snapped_x = get_direction(x)

        if start_row_x is None:
            start_row_x = snapped_x

        if pause_script:
            toggle_pause()
            pause_script = False
            continue

        failsafe_result = failsafe()


        if failsafe_result[0]:
            #m.echo(failsafe_result)
            alert(failsafe_result[1], failsafe_result[2], True)

        if STATE == "FARM_ROW":

            at_wall = (
                    (direction == "left" and z <= ROW_MIN) or
                    (direction == "right" and z >= ROW_MAX)
            )

            if LAST_POS != 0:

                if (LAST_POS == m.player_position()) and not at_wall:
                    alert("NO MOVEMENT DETECTED !!!!!!!!!!!!!!!!!!!!!!!!!", "default")
                else:
                    #m.echo(f"Last POS: {LAST_POS} Cur Pos: {m.player_position()}")
                    LAST_POS = m.player_position()

            else:
                LAST_POS = m.player_position()

            if start_row_x != snapped_x:
                start_row_x = snapped_x
                msg = "Left" if direction == "left" else "Right"
                log(f"[FARM] start row {snapped_x:.3f} direction={direction}")
                try:
                    m.echo(f"[HyFarmer] Farming {msg} Row")
                except Exception:
                    pass

            at_wall = (
                (direction == "left" and z <= ROW_MIN) or
                (direction == "right" and z >= ROW_MAX)
            )

            if at_wall and row_push_until == 0.0:
                push_time = random.uniform(PUSH_MIN, PUSH_MAX)
                row_push_until = now + push_time
                log(f"[ROW-PUSH] start until {row_push_until:.3f}")
                try:
                    m.echo(f"[HyFarmer] Extra push to the {direction} ({push_time:.1f}s)")
                except Exception:
                    pass

            if row_push_until != 0.0 and now < row_push_until:
                log(f"[ROW-PUSH] pushing {direction} z={z:.3f}")
                if direction == "left":
                    set_move(left=True)
                else:
                    set_move(right=True)
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
                set_move(left=True)

            elif direction == "right" and z < ROW_MAX:
                log(f"[MOVE] row right z={z:.3f}")
                set_move(right=True)

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

            if at_field_end(x, z):
                log("[END] reached final row -> waiting before warp")
                stop_inputs()

                wait_extra = random.uniform(END_EXTRA_MIN, END_EXTRA_MAX)
                total_wait = END_HARD_WAIT + wait_extra
                log(f"[END] waiting {total_wait:.2f}s before warp")

                try:
                    m.echo(f"[HyFarmer] Waiting at end ({total_wait:.1f}s)")
                except Exception:
                    pass

                time.sleep(total_wait)

                try:
                    m.echo("[HyFarmer] Warping now...")
                except Exception:
                    pass

                m.execute("/warp garden")
                time.sleep(WARP_WAIT)

                # >>> NEU: extra Wartezeit NACH dem Warp <<<
                post_wait = random.uniform(POST_WARP_MIN, POST_WARP_MAX)
                log(f"[WARP] post-wait {post_wait:.2f}s")
                try:
                    m.echo(f"[HyFarmer] Waiting after warp ({post_wait:.1f}s)")
                except Exception:
                    pass
                time.sleep(post_wait)

                ensure_attack()

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
                set_move(forward=True, left=True)
            else:
                set_move(forward=True, right=True)

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
