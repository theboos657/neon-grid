"""Neon-styled DirectGUI widgets with RTL-aware layout helpers."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (DirectButton, DirectEntry, DirectFrame, DirectScrolledFrame,
                                  DirectSlider)
from panda3d.core import TextNode

from .. import i18n
from . import theme as T

BTN_COLORS = ((0.02, 0.07, 0.09, 0.85), (0.1, 0.6, 0.7, 0.95), (0.05, 0.25, 0.3, 0.95),
              (0.03, 0.04, 0.05, 0.6))


class UI:
    """Factory bound to the app (fonts, sounds)."""

    def __init__(self, app):
        self.app = app

    @property
    def font(self):
        return self.app.fonts.get("ui")

    @property
    def dfont(self):
        return self.app.fonts.get("display")

    def _hover(self, *_):
        self.app.audio.ui("ui_hover")

    def _wrap(self, cmd, sound="ui_click"):
        def run(*a):
            self.app.audio.ui(sound)
            if cmd:
                cmd(*a)
        return run

    # ------------------------------------------------------------------ widgets
    def frame(self, parent, x0, x1, y0, y1, color=T.PANEL, border=True):
        f = DirectFrame(parent=parent, frameColor=color, frameSize=(x0, x1, y0, y1))
        if border:
            DirectFrame(parent=f, frameColor=T.CYAN, frameSize=(x0, x1, y1 - 0.004, y1))
            DirectFrame(parent=f, frameColor=(0.1, 0.5, 0.6, 0.6), frameSize=(x0, x1, y0, y0 + 0.002))
        return f

    def label(self, parent, s, pos, scale=0.045, color=T.WHITE, align="left", font=None,
              wordwrap=None):
        return T.text(parent, s, pos, scale, color, align, font or self.font, wordwrap=wordwrap)

    def button(self, parent, s, pos, command=None, width=0.62, height=0.085, scale=0.048,
               align="center", enabled=True, color=None, sound="ui_click", font=None):
        hw = width / 2
        tx = 0.0
        ta = TextNode.ACenter
        if align == "left":
            tx = -hw + 0.03
            ta = TextNode.ALeft
        elif align == "right":
            tx = hw - 0.03
            ta = TextNode.ARight
        fc = BTN_COLORS if enabled else (BTN_COLORS[3],) * 4
        if color is not None:
            fc = (color, BTN_COLORS[1], BTN_COLORS[2], BTN_COLORS[3])
        b = DirectButton(parent=parent, text=s, text_font=font or self.font, text_scale=scale,
                         text_fg=T.WHITE if enabled else T.GREY, text_align=ta,
                         text_pos=(tx, -scale * 0.35), relief=DGG.FLAT,
                         frameColor=fc, frameSize=(-hw, hw, -height / 2, height / 2),
                         pos=(pos[0], 0, pos[1]), command=self._wrap(command, sound) if enabled else None,
                         pressEffect=1, rolloverSound=None, clickSound=None)
        if enabled:
            b.bind(DGG.ENTER, self._hover)
            # neon underline
            DirectFrame(parent=b, frameColor=(0.15, 0.9, 1.0, 0.8),
                        frameSize=(-hw, hw, -height / 2, -height / 2 + 0.004))
        else:
            b["state"] = DGG.DISABLED
        return b

    def selector(self, parent, label, options, index, pos, on_change, width=1.3,
                 label_w=0.55, scale=0.042):
        """Row: LABEL   < value >   (options = list of display strings)."""
        rtl = i18n.is_rtl()
        x, y = pos
        state = {"i": index}
        lx = x - width / 2 if not rtl else x + width / 2
        self.label(parent, label, (lx, y - 0.013), scale, T.GREY, "left" if not rtl else "right")
        cx = x + (label_w / 2) * (1 if not rtl else -1)
        vw = width - label_w - 0.02
        val = self.label(parent, options[index] if options else "", (cx, y - 0.013), scale,
                         T.WHITE, "center")

        def step(d):
            if not options:
                return
            state["i"] = (state["i"] + d) % len(options)
            T.set_text(val, options[state["i"]])
            on_change(state["i"])
        left = -1 if not rtl else 1
        self.button(parent, "<", (cx - vw / 2 + 0.03, y), lambda: step(-left if rtl else -1),
                    0.06, 0.06, scale)
        self.button(parent, ">", (cx + vw / 2 - 0.03, y), lambda: step(left if rtl else 1),
                    0.06, 0.06, scale)
        return state, val

    def toggle(self, parent, label, value, pos, on_change, width=1.3, label_w=0.55):
        opts = [i18n.t("off"), i18n.t("on")]
        return self.selector(parent, label, opts, 1 if value else 0, pos,
                             lambda i: on_change(bool(i)), width, label_w)

    def slider(self, parent, label, value, pos, on_change, lo=0.0, hi=1.0, width=1.3,
               label_w=0.55, fmt="{:.0%}"):
        rtl = i18n.is_rtl()
        x, y = pos
        lx = x - width / 2 if not rtl else x + width / 2
        self.label(parent, label, (lx, y - 0.013), 0.042, T.GREY, "left" if not rtl else "right")
        sw = width - label_w - 0.14
        cx = x + (label_w / 2 - 0.06) * (1 if not rtl else -1)
        vx = cx + (sw / 2 + 0.08) * (1 if not rtl else -1)
        val = self.label(parent, fmt.format(value), (vx, y - 0.013), 0.038, T.WHITE, "center")

        def changed():
            v = s["value"]
            T.set_text(val, fmt.format(v))
            on_change(v)
        s = DirectSlider(parent=parent, range=(lo, hi), value=value, pos=(cx, 0, y),
                         frameSize=(-sw / 2, sw / 2, -0.008, 0.008),
                         frameColor=(0.1, 0.3, 0.35, 0.9), thumb_relief=DGG.FLAT,
                         thumb_frameColor=T.CYAN, thumb_frameSize=(-0.012, 0.012, -0.03, 0.03),
                         command=changed)
        if rtl:
            s.setR(180)
        return s

    def entry(self, parent, label, value, pos, on_change, width=1.3, label_w=0.55, max_chars=16,
              upper=False):
        rtl = i18n.is_rtl()
        x, y = pos
        lx = x - width / 2 if not rtl else x + width / 2
        self.label(parent, label, (lx, y - 0.013), 0.042, T.GREY, "left" if not rtl else "right")
        ew = width - label_w
        cx = x + (label_w / 2) * (1 if not rtl else -1)
        scale = 0.042

        def changed(*_):
            txt = e.get()
            if upper and txt != txt.upper():
                e.enterText(txt.upper())
                txt = txt.upper()
            on_change(txt[:max_chars])
        e = DirectEntry(parent=parent, initialText=value, numLines=1, width=ew / scale - 1,
                        scale=scale, pos=(cx - ew / 2 + 0.02, 0, y - 0.013), text_fg=T.WHITE,
                        frameColor=(0.03, 0.1, 0.13, 0.9), relief=DGG.FLAT,
                        frameSize=(-0.4, ew / scale - 0.5, -0.5, 1.1), entryFont=self.font,
                        command=changed, focusOutCommand=changed, cursorKeys=1,
                        suppressKeys=0)
        e.bind(DGG.TYPE, changed)
        e.bind(DGG.ERASE, changed)
        return e

    def scroll(self, parent, x0, x1, y0, y1, canvas_h):
        sf = DirectScrolledFrame(parent=parent, frameSize=(x0, x1, y0, y1),
                                 canvasSize=(x0, x1 - 0.05, min(y0, y1 - canvas_h), y1),
                                 frameColor=(0, 0, 0, 0), scrollBarWidth=0.03,
                                 verticalScroll_frameColor=(0.05, 0.1, 0.12, 0.8),
                                 verticalScroll_thumb_frameColor=T.CYAN,
                                 verticalScroll_incButton_frameColor=(0.05, 0.3, 0.35, 1),
                                 verticalScroll_decButton_frameColor=(0.05, 0.3, 0.35, 1),
                                 horizontalScroll_frameColor=(0, 0, 0, 0),
                                 manageScrollBars=True, autoHideScrollBars=True)
        return sf

    def bar(self, parent, x, y, w, frac, color=T.CYAN, h=0.018):
        T.card(parent, x, x + w, y, y + h, (0.05, 0.12, 0.15, 0.9))
        c = T.card(parent, 0, w, y, y + h, color)
        c.setX(x)
        c.setSx(max(0.001, min(1.0, frac)))
        return c
