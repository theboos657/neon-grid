"""Story mode screens: the chapter list and the typewriter cutscenes."""

from .. import i18n
from ..story import campaign as C
from . import theme as T

TYPE_SPEED = 45.0          # characters per second


def build_menu(menus, sel=None):
    app = menus.app
    ui = menus.ui
    root = menus.root
    menus._backdrop(False)
    ar = app.getAspectRatio()
    done = C.progress(app)
    if sel is None:
        sel = min(done, len(C.CHAPTERS) - 1)
    T.text(root, i18n.visual(C.tx("title")), (0, 0.78), 0.11, (1.0, 0.35, 0.3, 1), "center",
           ui.dfont)
    T.text(root, i18n.visual(C.tx("subtitle")), (0, 0.69), 0.04, T.GREY, "center", ui.font)
    lx = T.mx(-ar + 0.62)
    for i, ch in enumerate(C.CHAPTERS):
        title = C.chapter_text(i)[0]
        locked = i > done
        mark = "  [x]" if i < done else ("" if not locked else "  [-]")
        ui.button(root, i18n.visual(title) + mark, (lx, 0.5 - i * 0.13),
                  lambda i=i: menus.show("story", sel=i), 0.95, 0.1, 0.042,
                  align=T.ui_align("left"), font=ui.dfont, enabled=not locked,
                  color=(0.3, 0.06, 0.06, 0.95) if i == sel else None)
    # selected chapter panel
    rx = T.mx(0.45)
    f = ui.frame(root, rx - 0.85, rx + 0.85, -0.62, 0.58)
    title, intro, _ = C.chapter_text(sel)
    ch = C.CHAPTERS[sel]
    T.text(f, i18n.visual(title), (rx, 0.46), 0.065, (1.0, 0.4, 0.35, 1), "center", ui.dfont)
    T.text(f, i18n.t("brief_map", map=i18n.raw("map_" + ch["map"])) + "   |   " +
           i18n.t("diff_" + ch["diff"]), (rx, 0.38), 0.036, T.GOLD, "center", ui.font)
    teaser = intro[0] + "\n\n" + C.tx("goal", boss=ch["boss"][0])
    if i18n.is_rtl():
        teaser = "\n".join(i18n.wrap(part, 50) if part else "" for part in teaser.split("\n"))
    ui.label(f, i18n.visual(teaser), (rx, 0.26), 0.036, T.WHITE, "center", wordwrap=40)
    label = C.tx("replay") if sel < done else C.tx("play")
    ui.button(root, i18n.visual(label), (rx, -0.52),
              lambda: menus.show("story_scene", chapter=sel, part="intro"), 0.7, 0.11, 0.055,
              font=ui.dfont, color=(0.45, 0.07, 0.07, 0.95))
    if sel < done:
        T.text(root, i18n.visual(C.tx("done")), (rx, -0.67), 0.034, T.GREEN, "center", ui.font)
    menus._back_button()


def build_scene(menus, chapter=0, part="intro"):
    """Black screen, chapter title, paragraphs typed out one by one."""
    app = menus.app
    ui = menus.ui
    root = menus.root
    ar = app.getAspectRatio()
    T.card(root, -ar, ar, -1, 1, (0, 0, 0, 0.97))
    title, intro, outro = C.chapter_text(chapter)
    paras = intro if part == "intro" else outro
    T.text(root, i18n.visual(title), (0, 0.62), 0.09, (1.0, 0.35, 0.3, 1), "center", ui.dfont)
    body = ui.label(root, "", (0, 0.3), 0.05, T.WHITE, "center", wordwrap=34)
    hint = T.text(root, "", (0, -0.8), 0.03, T.GREY, "center", ui.font)
    st = {"i": 0, "chars": 0.0, "done": False}

    def text_of(i):
        s = paras[i]
        if i18n.is_rtl():
            s = i18n.wrap(s, 44)
        return s

    def finish():
        if st["done"]:
            return
        st["done"] = True
        app.base.ignore("space")
        app.base.ignore("mouse1")
        if part == "intro":
            ch = C.CHAPTERS[chapter]
            app.start_match({"mode": "story", "chapter": chapter, "map": ch["map"],
                             "difficulty": ch["diff"], "lives": True, "lives_count": 3,
                             "chaos": False, "time_limit": 0, "score_limit": 0})
        else:
            menus.show("story", sel=min(chapter + 1, len(C.CHAPTERS) - 1))

    def advance():
        if st["done"] or menus.current != "story_scene":
            return
        full = text_of(st["i"])
        if st["chars"] < len(full):
            st["chars"] = len(full)          # first press finishes the paragraph
            return
        st["i"] += 1
        st["chars"] = 0.0
        if st["i"] >= len(paras):
            finish()

    def tick(dt):
        if st["done"] or menus.current != "story_scene":
            return
        full = text_of(st["i"])
        st["chars"] = min(len(full), st["chars"] + TYPE_SPEED * dt)
        shown = full[:int(st["chars"])]
        T.set_text(body, i18n.visual(shown))
        T.set_text(hint, i18n.visual(C.tx("next")) if st["chars"] >= len(full) else "")

    menus.scene_tick = tick
    app.base.accept("space", advance)
    app.base.accept("mouse1", advance)
    ui.button(root, i18n.visual(C.tx("skip")), (T.mx(ar - 0.3), -0.88), finish, 0.35, 0.07,
              0.034)
