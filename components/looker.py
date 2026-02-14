import system.lib.minescript as minescript
import random
import time

CONFIRM_YAW_PITCH = True # If it should manuallly correct at the end (If you need exact Yaw and Pitch)

def look(target_yaw, target_pitch, duration=0.4, steps=20):
    sy, sp = minescript.player_orientation()
    dy, dp = target_yaw - sy, target_pitch - sp

    for i in range(1, steps + 1):
        t = i / steps
        s = 1 - (1 - t) ** 3

        jy = (1 - t) * 0.6
        minescript.player_set_orientation(
            sy + dy * s + random.uniform(-jy, jy),
            sp + dp * s + random.uniform(-jy * 0.7, jy * 0.7)
        )
        time.sleep(duration / steps)

    minescript.player_set_orientation(
        target_yaw + random.uniform(-0.15, 0.15),
        target_pitch + random.uniform(-0.15, 0.15)
    )

    minescript.player_set_orientation(target_yaw, target_pitch)