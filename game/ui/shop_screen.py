"""The SHOP screen: buy weapons, melee weapons, abilities, attachments, weapon
upgrade tiers, match boosts and cosmetics with coins earned from kills."""

from neon_shared import weapons as W
from neon_shared.abilities import ABILITIES

from .. import i18n
from ..progression import shop as SH
from ..progression import skins as SK
from . import theme as T

TABS = ["weapons", "melee", "abilities", "attachments", "upgrades", "boosts", "cosmetics"]
BUY_COL = (0.35, 0.28, 0.05, 0.95)
ROW_H = 0.115


def build(menus, tab=None):
    """Called from Menus._build_shop."""
    ui = menus.ui
    app = menus.app
    prof = app.storage.profile
    pd = prof.data
    if tab:
        menus.shop_tab = tab
    tab = getattr(menus, "shop_tab", "weapons")
    menus._backdrop(False)
    menus._header("shop")
    ar = app.getAspectRatio()
    rtl = i18n.is_rtl()
    ui.label(menus.root, i18n.t("coins", n=pd["coins"]), (T.mx(ar - 0.1), 0.82), 0.06, T.GOLD,
             T.ui_align("right"), ui.dfont)
    ui.label(menus.root, i18n.t("lo_coins_hint"), (T.mx(ar - 0.1), 0.76), 0.028, T.GREY,
             T.ui_align("right"))
    # tabs
    tw = 2.9 / len(TABS)
    for i, t in enumerate(TABS):
        x = -1.45 + tw * (i + 0.5)
        if rtl:
            x = -x
        ui.button(menus.root, i18n.t("shop_" + t), (x, 0.66), lambda t=t: menus.show("shop", tab=t),
                  tw - 0.02, 0.075, 0.032,
                  color=(0.05, 0.35, 0.4, 0.95) if t == tab else None)
    rows = _rows(menus, tab, pd)
    sf = ui.scroll(menus.root, -1.45, 1.45, -0.8, 0.6, len(rows) * ROW_H + 0.05)
    cv = sf.getCanvas()
    y = 0.6 - ROW_H / 2 - 0.01
    for r in rows:
        _row(menus, cv, y, r)
        y -= ROW_H
    if not rows:
        ui.label(menus.root, i18n.t("shop_empty"), (0, 0.1), 0.04, T.GREY, "center")
    menus._back_button()


def _buy(menus, fn, *args):
    pd = menus.app.storage.profile.data
    if fn(pd, *args):
        menus.app.storage.profile.save()
        menus.app.audio.ui("coin")
    else:
        menus.toast(i18n.t("lk_not_enough"))
    menus.show("shop")


def _rows(menus, tab, pd):
    """Returns a list of row dicts: name, sub, desc, price, state, buy, extra, swatch."""
    out = []
    if tab in ("weapons", "melee"):
        table = W.RANGED if tab == "weapons" else W.MELEE
        for w in sorted(table, key=lambda w: SH.weapon_price(w["id"])):
            owned = SH.owns_weapon(pd, w["id"])
            s = W.weapon_stats(w["id"])
            if w["melee"]:
                desc = "%d dmg  %.1f swings/s  %.1f m reach  move %.2fx" % (
                    s["dmg"], s["rps"], s["range"], s["move"])
            else:
                desc = "%d%s dmg  %.1f/s  mag %d  DPS %d" % (
                    s["dmg"], (" x%d" % s["pellets"]) if s["pellets"] > 1 else "", s["rps"],
                    s["mag"], W.dps(s))
            out.append({"name": w["name"], "sub": w["cls"].upper(), "desc": desc,
                        "price": SH.weapon_price(w["id"]), "owned": owned,
                        "buy": (SH.buy_weapon, w["id"])})
    elif tab == "abilities":
        for a in sorted(ABILITIES, key=lambda a: SH.ability_price(a["id"])):
            out.append({"name": a["name"], "sub": i18n.t("cooldown", n=int(a["cooldown"])),
                        "desc": a["desc"], "price": SH.ability_price(a["id"]),
                        "owned": SH.owns_ability(pd, a["id"]),
                        "buy": (SH.buy_ability, a["id"])})
    elif tab == "attachments":
        for m in sorted(W.MODS, key=lambda m: (W.MOD_SLOTS.index(m["slot"]), m["price"])):
            fits = ", ".join(c.upper() for c in m["classes"])
            out.append({"name": m["name"], "sub": i18n.t("slot_" + m["slot"]),
                        "desc": m["desc"] + "   [" + fits + "]", "price": m["price"],
                        "owned": SH.owns_mod(pd, m["id"]), "buy": (SH.buy_mod, m["id"])})
    elif tab == "upgrades":
        for w in W.RANGED + W.MELEE:
            if not SH.owns_weapon(pd, w["id"]):
                continue
            t = SH.unlocked_tier(pd, w["id"])
            price = SH.next_tier_price(pd, w["id"])
            table = W.MELEE_TIERS if w["melee"] else W.TIERS
            nxt = table[t] if t < W.MAX_TIER else None
            out.append({"name": w["name"], "sub": i18n.t("shop_tier", n=t),
                        "desc": ("%s: %s" % (nxt["name"], nxt["desc"])) if nxt
                        else i18n.t("lo_max_tier"),
                        "price": price or 0, "owned": price is None,
                        "owned_label": i18n.t("lo_max_tier"),
                        "buy_label": i18n.t("shop_upgrade", n=t + 1, cost=price or 0),
                        "buy": (SH.buy_tier, w["id"]),
                        "edit": w["id"] if not w["melee"] else None})
    elif tab == "boosts":
        for b in SH.BOOSTS:
            left = pd["boosts"].get(b["id"], 0)
            out.append({"name": i18n.t("boost_" + b["id"]),
                        "sub": i18n.t("boost_left", n=left) if left else "",
                        "desc": i18n.t("boostd_" + b["id"], n=b["matches"]),
                        "price": b["price"], "owned": False, "stack": True,
                        "buy": (SH.buy_boost, b["id"])})
    elif tab == "cosmetics":
        for sk in SK.WEAPON_SKINS:
            if sk["source"] == "shop":
                out.append({"name": sk["name"], "sub": i18n.t("lk_weapon_skins"), "desc": "",
                            "price": sk["price"], "swatch": sk,
                            "owned": sk["id"] in pd["owned_weapon_skins"],
                            "buy": (SH.buy_skin, "owned_weapon_skins", sk["id"], sk["price"])})
        for sk in SK.CHAR_SKINS:
            if sk["source"] == "shop":
                out.append({"name": sk["name"], "sub": i18n.t("lk_char_skins"), "desc": "",
                            "price": sk["price"], "swatch": sk,
                            "owned": sk["id"] in pd["owned_char_skins"],
                            "buy": (SH.buy_skin, "owned_char_skins", sk["id"], sk["price"])})
    return out


def _row(menus, cv, y, r):
    ui = menus.ui
    pd = menus.app.storage.profile.data
    rtl = i18n.is_rtl()
    al = T.ui_align("left")
    T.card(cv, -1.43, 1.36, y - ROW_H / 2 + 0.006, y + ROW_H / 2 - 0.006,
           (0.03, 0.12, 0.14, 0.88) if r["owned"] else T.PANEL)
    x0 = -1.38 if not rtl else 1.31
    tx = x0
    sw = r.get("swatch")
    if sw:
        sx = -1.38 if not rtl else 1.25
        T.card(cv, sx, sx + 0.05, y - 0.03, y + 0.03, sw["body"] + (1,))
        T.card(cv, sx + 0.055, sx + 0.07, y - 0.03, y + 0.03, sw["accent"] + (1,))
        tx = x0 + (0.1 if not rtl else -0.1)
    ui.label(cv, r["name"].upper(), (tx, y + 0.008), 0.038, T.WHITE if r["owned"] else T.CYAN, al,
             ui.dfont)
    if r.get("sub"):
        ui.label(cv, r["sub"], (tx + (0.62 if not rtl else -0.62), y + 0.012), 0.028, T.GOLD, al)
    if r.get("desc"):
        ui.label(cv, r["desc"], (tx, y - 0.036), 0.027, T.GREY, al)
    bx = 1.12 if not rtl else -1.19
    if r.get("edit"):
        def edit(wid=r["edit"]):
            menus.gs_weapon = wid
            menus.gs_preview = {}
            menus.gs_return = "shop"
            menus.show("gunsmith")
        ui.button(cv, i18n.t("edit_weapon"), (bx - (0.42 if not rtl else -0.42), y), edit, 0.34,
                  0.07, 0.03, color=(0.05, 0.3, 0.35, 0.95))
    if r["owned"]:
        ui.label(cv, r.get("owned_label", i18n.t("shop_owned")), (bx, y - 0.012), 0.032,
                 T.GREEN, "center")
        return
    label = r.get("buy_label") or i18n.t("lo_buy", cost=r["price"])
    fn = r["buy"]
    ui.button(cv, label, (bx, y), lambda: _buy(menus, *fn), 0.4, 0.075, 0.03,
              color=BUY_COL if pd["coins"] >= r["price"] else None)
