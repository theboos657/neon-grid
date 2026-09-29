"""Shared ground-based movement: walk, sprint, crouch, slide, jump, plus the
special cases (jump pads, gravity zones, jump jets, dash, stun)."""

import math

from panda3d.core import Vec3

from neon_shared.hitmath import CROUCH_HEIGHT, STAND_HEIGHT

WALK = 6.2
SPRINT = 9.3
CROUCH = 3.2
ACCEL_GROUND = 70.0
ACCEL_AIR = 14.0
FRICTION = 12.0
SLIDE_FRICTION = 1.6
SLIDE_BOOST = 12.5
SLIDE_TIME = 0.8
JUMP_V = 6.9
GRAVITY = 18.0
COYOTE = 0.12
MAX_SPEED = 45.0          # hard cap (dash)


def update(c, dt):
    m = c.match
    b = c.body
    inp = c.input
    now = m.time
    was_ground = b.on_ground
    if was_ground:
        c.air_time = 0.0
    else:
        c.air_time += dt

    hvel = Vec3(b.vel.x, b.vel.y, 0)
    hspeed = hvel.length()
    stunned = now < c.stun_until

    # --- wish direction in world space (inp.move is local x=right, y=forward)
    yaw = math.radians(c.yaw)
    fwd = Vec3(-math.sin(yaw), math.cos(yaw), 0)
    right = Vec3(math.cos(yaw), math.sin(yaw), 0)
    wish = right * inp.move_x + fwd * inp.move_y
    wl = wish.length()
    if wl > 1:
        wish /= wl
        wl = 1.0

    # --- crouch / slide
    if c.slide_cd > 0:
        c.slide_cd -= dt
    if inp.crouch and not c.crouching:
        if c.sprinting and b.on_ground and hspeed > 7.0 and c.slide_cd <= 0:
            c.sliding = SLIDE_TIME
            c.slide_cd = 1.1
            d = hvel / hspeed if hspeed > 0.1 else fwd
            boost = max(hspeed + 2.5, SLIDE_BOOST)
            b.vel.x = d.x * boost
            b.vel.y = d.y * boost
            m.on_slide(c)
        c.crouching = True
    elif not inp.crouch and c.crouching:
        head_room = m.coll.ceiling_height(b.pos.x, b.pos.y, b.radius * 0.75, b.pos.z + 0.6)
        if head_room >= b.pos.z + STAND_HEIGHT:
            c.crouching = False
            c.sliding = 0.0
    b.height = CROUCH_HEIGHT if c.crouching else STAND_HEIGHT

    # --- speed
    ws = c.weapon()
    mult = ws.stats["move"] if ws else 1.0
    if now < c.speed_until:
        mult *= 1.35
    if stunned:
        mult *= 0.35
    if inp.ads and ws and not ws.stats["melee"]:
        mult *= 0.72
    forward_ish = inp.move_y > 0.3
    c.sprinting = (inp.sprint and forward_ish and not c.crouching and not inp.ads
                   and not inp.fire and b.on_ground) or (c.sprinting and not b.on_ground
                                                       and inp.sprint)
    if c.crouching:
        top = CROUCH
    elif c.sprinting:
        top = SPRINT
    else:
        top = WALK
    top *= mult

    dashing = now < c.dash_until
    if dashing:
        pass  # dash owns velocity
    elif c.sliding > 0:
        c.sliding -= dt
        f = math.exp(-SLIDE_FRICTION * dt)
        b.vel.x *= f
        b.vel.y *= f
        # light steering
        b.vel.x += wish.x * 4.0 * dt
        b.vel.y += wish.y * 4.0 * dt
        if hspeed < CROUCH + 0.5 or not b.on_ground and c.air_time > 0.4:
            c.sliding = 0.0
    elif b.on_ground:
        target = wish * top
        # friction when no input, accelerate toward target otherwise
        if wl < 0.01:
            f = math.exp(-FRICTION * dt)
            b.vel.x *= f
            b.vel.y *= f
        else:
            dvx = target.x - b.vel.x
            dvy = target.y - b.vel.y
            dl = math.hypot(dvx, dvy)
            step = ACCEL_GROUND * dt
            if dl > step:
                dvx *= step / dl
                dvy *= step / dl
            b.vel.x += dvx
            b.vel.y += dvy
    elif c.launched <= 0:
        # air control: can steer but not exceed the larger of top speed / current speed
        b.vel.x += wish.x * ACCEL_AIR * dt
        b.vel.y += wish.y * ACCEL_AIR * dt
        nh = math.hypot(b.vel.x, b.vel.y)
        cap = max(top, hspeed)
        if nh > cap:
            b.vel.x *= cap / nh
            b.vel.y *= cap / nh
    if c.launched > 0:
        c.launched -= dt
        if b.on_ground and c.launched < 1.0:
            c.launched = 0.0

    # --- jump (with coyote time); slide-jumps keep their momentum
    if inp.jump and not stunned and (b.on_ground or c.air_time < COYOTE) and c.jump_lock <= 0:
        b.vel.z = JUMP_V
        b.on_ground = False
        c.air_time = COYOTE
        c.jump_lock = 0.2
        c.sliding = 0.0
        m.audio.play3d("jump", b.pos, 0.5, source=c)
    if c.jump_lock > 0:
        c.jump_lock -= dt

    # --- vertical forces
    g = GRAVITY
    if m.hazards and m.hazards.gravity_at(b.pos):
        g = GRAVITY * 0.12
        if b.vel.z < 4.5:
            b.vel.z += 11.0 * dt
    if now < c.jets_until:
        if b.vel.z < 3.0:
            b.vel.z += 26.0 * dt
        g *= 0.25
    if not b.on_ground or b.vel.z > 0:
        b.vel.z -= g * dt

    # clamp
    sp = b.vel.length()
    if sp > MAX_SPEED:
        b.vel *= MAX_SPEED / sp

    fall_speed = -b.vel.z
    m.coll.move(b, dt)
    if b.on_ground and not was_ground:
        c.on_land(fall_speed)
    if dashing and now + dt >= c.dash_until:
        # leaving a dash: keep a little extra momentum
        hv = Vec3(b.vel.x, b.vel.y, 0)
        if hv.length() > SPRINT + 2:
            hv.normalize()
            hv *= SPRINT + 2
            b.vel.x, b.vel.y = hv.x, hv.y

    # footsteps
    if b.on_ground and c.sliding <= 0:
        hs = math.hypot(b.vel.x, b.vel.y)
        if hs > 2.0:
            c.step_phase += hs * dt * (0.34 if not c.crouching else 0.25)
            if c.step_phase >= 1.0:
                c.step_phase -= 1.0
                if not c.crouching:
                    m.audio.play3d("step", b.pos, 0.28 if c.sprinting else 0.18, source=c)
