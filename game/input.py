"""Keyboard/mouse input with rebindable actions.

Actions are polled every frame (``down``/``pressed``), which is more robust
for an FPS than event callbacks: modifier keys never swallow other keys
because compound "shift-w" style events are disabled at startup.
"""

from panda3d.core import ButtonRegistry, ModifierButtons, WindowProperties

ALIASES = {"lshift": ("lshift", "shift"), "rshift": ("rshift", "shift"),
           "lcontrol": ("lcontrol", "control"), "rcontrol": ("rcontrol", "control"),
           "lalt": ("lalt", "alt"), "ralt": ("ralt", "alt")}

DISPLAY = {"mouse1": "LMB", "mouse2": "MMB", "mouse3": "RMB", "lshift": "L-SHIFT",
           "lcontrol": "L-CTRL", "space": "SPACE", "tab": "TAB", "lalt": "L-ALT",
           "mouse4": "MB4", "mouse5": "MB5", "wheel_up": "WHEEL UP", "wheel_down": "WHEEL DOWN"}


def key_label(name):
    return DISPLAY.get(name, name.upper())


class InputManager:
    def __init__(self, base, settings):
        self.base = base
        self.settings = settings
        self.reg = ButtonRegistry.ptr()
        self._handles = {}
        self.prev = {}
        self.now = {}
        self.wheel = 0
        self.captured = False
        self.capture_callback = None
        # plain key events only (no "shift-w")
        self.headless = base.mouseWatcherNode is None
        if not self.headless:
            base.mouseWatcherNode.setModifierButtons(ModifierButtons())
            base.buttonThrowers[0].node().setModifierButtons(ModifierButtons())
            base.buttonThrowers[0].node().setButtonDownEvent("raw-button-down")
        base.accept("raw-button-down", self._on_button)
        base.accept("wheel_up", self._wheel, [1])
        base.accept("wheel_down", self._wheel, [-1])
        self.bindings = settings["controls"]["bindings"]
        self.mouse_dx = 0.0
        self.mouse_dy = 0.0

    def _wheel(self, d):
        self.wheel += d

    def _on_button(self, name):
        if self.capture_callback is not None:
            cb = self.capture_callback
            self.capture_callback = None
            cb(name)

    def capture_next(self, callback):
        """Call ``callback(button_name)`` for the next pressed button (rebinding)."""
        self.capture_callback = callback

    def _handles_for(self, key):
        if key not in self._handles:
            names = ALIASES.get(key, (key,))
            hs = []
            for n in names:
                h = self.reg.findButton(n)
                if h is not None and h.getName() != "none":
                    hs.append(h)
            self._handles[key] = hs
        return self._handles[key]

    def key_down(self, key):
        mw = self.base.mouseWatcherNode
        if mw is None:
            return False
        for h in self._handles_for(key):
            if mw.isButtonDown(h):
                return True
        return False

    def poll(self):
        """Call once per frame before reading actions."""
        self.prev = self.now
        self.now = {a: self.key_down(k) for a, k in self.bindings.items()}
        if self.captured and self.base.win is not None:
            win = self.base.win
            md = win.getPointer(0)
            cx = win.getXSize() // 2
            cy = win.getYSize() // 2
            if md.getInWindow():
                self.mouse_dx = md.getX() - cx
                self.mouse_dy = md.getY() - cy
                win.movePointer(0, cx, cy)
            else:
                self.mouse_dx = self.mouse_dy = 0.0
        else:
            self.mouse_dx = self.mouse_dy = 0.0

    def consume_wheel(self):
        w = self.wheel
        self.wheel = 0
        return w

    def down(self, action):
        return self.now.get(action, False)

    def pressed(self, action):
        return self.now.get(action, False) and not self.prev.get(action, False)

    def set_captured(self, on):
        if on == self.captured or self.headless:
            return
        self.captured = on
        props = WindowProperties()
        props.setCursorHidden(on)
        props.setMouseMode(WindowProperties.M_confined if on else WindowProperties.M_absolute)
        self.base.win.requestProperties(props)
        if on and self.base.win is not None:
            win = self.base.win
            win.movePointer(0, win.getXSize() // 2, win.getYSize() // 2)
        self.mouse_dx = self.mouse_dy = 0.0
