"""Local player controller: input -> Combatant, camera and view-model."""

import random

from panda3d.core import Vec3

MOUSE_DEG_PER_PX = 0.075


class PlayerController:
    def __init__(self, app, match, c):
        self.app = app
        self.m = match
        self.c = c
        self.eye_z = 1.62
        self.crouch_toggle = False
        self.shake_amt = 0.0
        self.death_cam_target = None
        self.last_slot = -1

    def update(self, dt):
        app = self.app
        inp_mgr = app.input
        c = self.c
        m = self.m
        settings = app.storage.settings.data
        ctrl = settings["controls"]
        inp = c.input
        can_look = c.alive and not app.menus_open() and m.state != "ended"
        can_act = can_look and not m.frozen

        # --- look
        if can_look:
            sens = ctrl["sensitivity"] * MOUSE_DEG_PER_PX
            ws = c.weapon()
            if inp.ads and not ws.melee:
                zoom = ws.stats["zoom"]
                sens *= ctrl["ads_sensitivity"] * max(0.35, zoom)
            dx = inp_mgr.mouse_dx
            dy = inp_mgr.mouse_dy
            c.yaw -= dx * sens
            c.pitch -= dy * sens * (-1 if ctrl["invert_y"] else 1)
            c.pitch = max(-88.0, min(88.0, c.pitch))
            c.yaw %= 360.0

        # --- actions
        if can_act:
            mx = (1 if inp_mgr.down("right") else 0) - (1 if inp_mgr.down("left") else 0)
            my = (1 if inp_mgr.down("forward") else 0) - (1 if inp_mgr.down("back") else 0)
            inp.move_x = float(mx)
            inp.move_y = float(my)
            inp.jump = inp.jump or inp_mgr.pressed("jump")
            inp.sprint = inp_mgr.down("sprint")
            if ctrl["toggle_crouch"]:
                if inp_mgr.pressed("crouch"):
                    self.crouch_toggle = not self.crouch_toggle
                inp.crouch = self.crouch_toggle
            else:
                inp.crouch = inp_mgr.down("crouch")
            inp.fire = inp_mgr.down("fire")
            inp.fire_pressed = inp.fire_pressed or inp_mgr.pressed("fire")
            inp.ads = inp_mgr.down("ads") or bool(app.args.get("ads"))   # --ads test hook
            inp.reload = inp.reload or inp_mgr.pressed("reload")
            inp.melee = inp.melee or inp_mgr.pressed("melee")
            if inp_mgr.pressed("ability1"):
                inp.ability[0] = True
            if inp_mgr.pressed("ability2"):
                inp.ability[1] = True
            for i, a in enumerate(("weapon1", "weapon2", "weapon3")):
                if inp_mgr.pressed(a):
                    inp.switch_to = i
            inp.bomb = inp.bomb or inp_mgr.pressed("bomb")          # hotbar 4
            inp.drone = inp.drone or inp_mgr.pressed("drone")       # hotbar 5
            w = inp_mgr.consume_wheel()
            if w:
                inp.cycle = -1 if w > 0 else 1
        else:
            inp.clear()
            inp_mgr.consume_wheel()

    def update_camera(self, dt):
        """Place the world camera (called after the combatant moved)."""
        app = self.app
        c = self.c
        cam = app.camera
        settings = app.storage.settings.data
        if c.alive:
            target_eye = c.eye_height()
            self.eye_z += (target_eye - self.eye_z) * min(1.0, dt * 14)
            pos = c.body.pos + Vec3(0, 0, self.eye_z)
            cam.setPos(pos)
            cam.setHpr(c.yaw, c.pitch, 0)
            self.death_cam_target = None
        else:
            # death view: stay where you fell and face your killer
            k = c.last_attacker
            if k is not None and getattr(k, "alive", False):
                cam.lookAt(k.chest_pos())
            cur = cam.getPos()
            ground = c.body.pos.z + 2.4
            cam.setZ(cur.z + (ground - cur.z) * min(1.0, dt * 2))
        # screen shake (optional)
        shake = max(self.shake_amt, self.m.fx.shake * 0.5)
        if shake > 0.001 and settings["gameplay"]["screen_shake"]:
            cam.setHpr(cam.getH() + random.uniform(-1, 1) * shake * 2.0,
                       cam.getP() + random.uniform(-1, 1) * shake * 2.0,
                       random.uniform(-1, 1) * shake * 1.2)
        self.shake_amt = max(0.0, self.shake_amt - dt * 3.0)
        # FOV / ADS zoom
        fov = settings["video"]["fov"]
        ws = c.weapon()
        vm = self.m.viewmodel
        scope = self.app.scope
        zoom = 1.0
        aiming = c.alive and c.input.ads and not ws.melee
        scoped = aiming and ws.stats["scoped"]
        if aiming:
            if scoped and scope.ok:
                # real scope: the main view zooms only slightly; the magnified
                # image is rendered into the scope lens by the scope camera
                zoom = 1.0 - 0.12 * vm.ads_k
            else:
                zoom = 1.0 + (ws.stats["zoom"] - 1.0) * vm.ads_k
        app.set_fov(fov * zoom)
        look = scoped and scope.ok and vm.ads_k > 0.55
        scope.set_active(look, fov * ws.stats["zoom"] * 0.55)
        vm.set_scope_active(look)
        # without a scope buffer, fall back to the full-screen scope overlay
        vm.hidden = (not c.alive) or (scoped and not scope.ok and vm.ads_k > 0.85)

    def add_shake(self, amount):
        self.shake_amt = min(1.0, self.shake_amt + amount)
