"""Localisation: English and Hebrew, with right-to-left support.

Panda3D's text renderer draws glyphs strictly left-to-right, so Hebrew text is
converted to *visual order* here with a small bidi implementation that keeps
Latin words and numbers readable inside Hebrew sentences.  UI code calls
``t(key)`` for display strings and ``is_rtl()`` to mirror layout/alignment.
"""

_lang = "en"

STRINGS = {
    "en": {
        # --- title / main menu ---
        "subtitle": "ARENA PROTOCOL", "press_start": "CLICK OR PRESS ANY KEY",
        "loading": "INITIALIZING GRID...", "loading_audio": "SYNTHESIZING AUDIO...",
        "play": "PLAY", "multiplayer": "MULTIPLAYER", "story": "STORY", "loadout": "LOADOUT",
        "battlepass": "BATTLE PASS", "locker": "LOCKER", "career": "CAREER",
        "settings": "SETTINGS", "quit": "QUIT", "back": "BACK", "start": "START",
        "resume": "RESUME", "quit_to_menu": "QUIT TO MENU", "apply": "APPLY",
        "reset_defaults": "RESET DEFAULTS", "confirm": "CONFIRM", "cancel": "CANCEL",
        "paused": "PAUSED", "level": "LVL {n}", "coins": "{n} ¢", "restart": "RESTART",
        # --- modes ---
        "mode_ffa": "FREE FOR ALL", "mode_duel": "1v1 VS BOT", "mode_team": "TEAM BATTLE",
        "mode_coop": "CO-OP SURVIVAL", "mode_endless": "ENDLESS SURVIVAL",
        "desc_ffa": "Everyone for themselves. Bots fill the empty slots.",
        "desc_duel": "One arena. One bot. Pick your difficulty.",
        "desc_team": "4v4 with AI wingmen against a bot squad.",
        "desc_coop": "You and AI wingmen hold out against endless waves.",
        "desc_endless": "Survive escalating waves of bots and drones alone.",
        "opt_bots": "BOTS", "opt_difficulty": "DIFFICULTY", "diff_easy": "EASY",
        "diff_normal": "NORMAL", "diff_hard": "HARD", "diff_nightmare": "NIGHTMARE",
        "res_diff_mult": "{d} x{m}", "opt_time": "TIME LIMIT",
        "opt_score": "SCORE LIMIT", "opt_lives": "LIVES MODE", "opt_lives_count": "LIVES",
        "opt_chaos": "CHAOS MODE", "on": "ON", "off": "OFF", "minutes": "{n} MIN",
        "unlimited": "NONE", "select_mode": "SELECT MODE", "match_options": "MATCH OPTIONS",
        "chaos_hint": "Sweeping lasers, mines and gravity zones.",
        "lives_hint": "Limited lives instead of unlimited respawns.",
        # --- multiplayer ---
        "mp_title": "MULTIPLAYER", "mp_name": "CALLSIGN", "mp_server": "SERVER / HOST IP",
        "mp_host_online": "HOST ONLINE", "mp_join_online": "JOIN ONLINE",
        "mp_host_lan": "HOST LAN", "mp_join_lan": "JOIN LAN", "mp_code": "ROOM CODE",
        "mp_room_code": "ROOM CODE  {code}", "mp_waiting": "Waiting for players...",
        "mp_players": "PLAYERS", "mp_start_match": "START MATCH",
        "mp_connecting": "Connecting...", "mp_failed": "Connection failed: {err}",
        "mp_searching_lan": "Searching LAN for room {code}...",
        "mp_not_found": "Room {code} not found", "mp_leave": "LEAVE",
        "mp_find_rooms": "FIND ROOMS", "mp_err_join_failed": "Could not connect to that room any more.", "mp_rooms_title": "ROOM FINDER",
        "mp_rooms_searching": "Searching your network and the relay server...",
        "mp_rooms_count": "{n} room(s) found - refreshes automatically",
        "mp_rooms_none": "No open rooms found yet. Ask a friend to press HOST, or host one yourself.",
        "mp_rooms_relay_down": "(relay {addr} offline - showing LAN rooms only)",
        "mp_code_rules": "Room codes are 4 LETTERS, like DAMH. Tip: press FIND ROOMS to join without typing a code.",
        "rb_code": "CODE", "rb_host": "HOST", "rb_players": "PLAYERS", "rb_state": "STATUS",
        "rb_source": "WHERE", "rb_lobby": "IN LOBBY", "rb_playing": "IN MATCH", "rb_online": "ONLINE",
        "rb_join": "JOIN", "rb_refresh": "REFRESH",
        "mp_not_found_lan": "No room {code} found on your network. Is the host on the same Wi-Fi?",
        "mp_err_refused": "No game server is running at {addr}. Put the host's IP in RELAY SERVER, or use JOIN LAN.",
        "mp_err_timeout": "The server at {addr} did not answer. Check the address and the host's firewall.",
        "mp_err_address": "Unknown server address {addr}.",
        "mp_err_port": "Could not open a port for hosting (another program is using it).",
        "mp_hosting_local": "Hosting on this PC. Friends on the same network: FIND ROOMS, or type code {code} and press JOIN LAN. Can't see the room? Allow NEON GRID in Windows Firewall on both PCs.",
        "mp_show_addr": "SHOW ADDRESS", "mp_hide_addr": "HIDE ADDRESS",
        "mp_addr_line": "Your address: {addr}  -  friends can type it in SERVER / HOST IP. Only share it with people you trust.",
        "mp_host_only": "Waiting for the host to start...",
        "mp_disconnected": "Disconnected: {err}", "mp_hint": "Share the 4-letter code with friends. LAN works without internet.",
        # --- story ---
        "story_title": "STORY MODE",
        "story_soon": "The story campaign is a separate module and is not installed yet.",
        # --- loadout ---
        "lo_primary": "PRIMARY", "lo_secondary": "SECONDARY", "lo_melee": "MELEE",
        "lo_ability1": "ABILITY 1 [Q]", "lo_ability2": "ABILITY 2 [E]",
        "lo_tier": "UPGRADE TIER", "lo_apply_chip": "USE UPGRADE CHIP ({n})",
        "lo_locked": "LOCKED", "lo_buy": "BUY  {cost} ¢",
        "lo_buy_tier": "BUY TIER {n}  -  {cost} ¢", "lo_need_more": "Need {n} more coins",
        "lo_buy_hint": "Earn coins by eliminating enemies, then unlock this here.",
        "lo_coins_hint": "Coins are earned from kills",
        "shop": "SHOP", "shop_weapons": "WEAPONS", "shop_melee": "MELEE",
        "shop_abilities": "ABILITIES", "shop_attachments": "ATTACHMENTS",
        "shop_upgrades": "UPGRADES", "shop_boosts": "BOOSTS", "shop_cosmetics": "COSMETICS",
        "shop_owned": "OWNED", "shop_tier": "TIER {n}/5", "shop_upgrade": "TIER {n}  {cost} \u00a2",
        "shop_empty": "Nothing here yet - buy a weapon first.", "edit_weapon": "EDIT WEAPON",
        "boost_xp2": "Double XP", "boost_coins15": "Coin Rush", "boost_shield": "Spawn Shield",
        "boost_ammo": "Ammo Surplus", "boost_left": "{n} MATCHES LEFT",
        "boostd_xp2": "Double XP from your next {n} matches.",
        "boostd_coins15": "+50% coins from your next {n} matches.",
        "boostd_shield": "Spawn with a 40 HP shield for your next {n} matches.",
        "boostd_ammo": "+50% spare ammo for your next {n} matches.",
        "res_boosts": "BOOSTS USED: {names}",
        "gunsmith": "GUNSMITH", "mods": "MODS", "slot_optic": "OPTIC", "slot_muzzle": "MUZZLE",
        "slot_magazine": "MAGAZINE", "slot_underbarrel": "UNDERBARREL", "slot_stock": "STOCK",
        "mod_none": "NONE", "mod_fitted": "FITTED", "mod_silent": "SILENT",
        "mod_laser": "LASER SIGHT", "mod_reticle_dot": "RED DOT", "mod_reticle_holo": "HOLO",
        "mod_scoped": "SCOPED", "gs_stats": "STATS WITH MODS",
        "gs_hint": "Buy an attachment once with coins, then fit it on any compatible gun.",
        "gs_no_slot": "No attachments fit this slot", "st_spread": "SPREAD",
        "st_recoil": "RECOIL", "st_zoom": "AIM ZOOM", "lo_weapon_xp": "WEAPON XP {xp}",
        "lo_next_tier": "Next tier at {xp} XP", "lo_max_tier": "MAX TIER",
        "st_damage": "DAMAGE", "st_firerate": "FIRE RATE", "st_magazine": "MAGAZINE",
        "st_reload": "RELOAD", "st_range": "RANGE", "st_handling": "HANDLING", "st_dps": "DPS",
        "st_mobility": "MOBILITY", "cooldown": "COOLDOWN {n}s", "energy_cost": "ENERGY {n}",
        # --- battle pass ---
        "bp_title": "BATTLE PASS - SEASON 1: VOLTAGE", "bp_tier": "TIER {n}",
        "bp_free": "FREE", "bp_premium": "PREMIUM",
        "bp_unlock_premium": "UNLOCK PREMIUM ({cost} ¢)", "bp_claim": "CLAIM",
        "bp_claimed": "CLAIMED", "bp_locked": "LOCKED", "bp_xp": "{xp} / {need} XP",
        "bp_premium_owned": "PREMIUM ACTIVE", "bp_note": "Earned with XP and coins only.",
        "rw_coins": "{n} Coins", "rw_chip": "Upgrade Chip", "rw_wskin": "Weapon Skin: {name}",
        "rw_cskin": "Suit: {name}", "rw_title": "Title: {name}",
        # --- locker ---
        "lk_title": "LOCKER", "lk_weapon_skins": "WEAPON SKINS", "lk_char_skins": "SUITS",
        "lk_equip": "EQUIP", "lk_equipped": "EQUIPPED", "lk_buy": "BUY {cost} ¢",
        "lk_not_enough": "Not enough coins", "lk_pass_only": "BATTLE PASS",
        "lk_titles": "TITLES",
        # --- career ---
        "cr_title": "CAREER", "cr_stats": "STATS", "cr_achievements": "ACHIEVEMENTS",
        "cr_challenges": "DAILY CHALLENGES", "cr_highscores": "HIGH SCORES",
        "cs_kills": "Kills", "cs_deaths": "Deaths", "cs_kd": "K/D", "cs_headshots": "Headshots",
        "cs_accuracy": "Accuracy", "cs_matches": "Matches", "cs_wins": "Wins",
        "cs_time": "Time Played", "cs_melee": "Melee Kills", "cs_streak": "Best Streak",
        "cs_damage": "Damage Dealt", "cs_abilities": "Abilities Used",
        "cs_drones": "Drones Destroyed", "cs_turrets": "Turrets Destroyed",
        "hs_endless": "Endless: best wave", "hs_endless_kills": "Endless: most kills",
        "hs_ffa": "FFA: most kills", "hs_coop": "Co-op: best wave",
        "hs_duel": "Duel wins (E/N/H/NM)", "ch_reward": "+{xp} XP  +{coins} ¢",
        "ch_done": "COMPLETE",
        # --- settings ---
        "set_title": "SETTINGS", "tab_video": "VIDEO", "tab_audio": "AUDIO",
        "tab_controls": "CONTROLS", "tab_gameplay": "GAMEPLAY", "tab_hud": "HUD",
        "tab_language": "LANGUAGE", "quality": "QUALITY", "q_high": "HIGH", "q_low": "LOW",
        "fullscreen": "FULLSCREEN", "resolution": "RESOLUTION", "vsync": "VSYNC",
        "fps_cap": "FPS CAP", "fov": "FIELD OF VIEW", "show_fps": "SHOW FPS",
        "bloom": "BLOOM", "reflections": "FLOOR REFLECTIONS", "master": "MASTER",
        "music": "MUSIC", "effects": "EFFECTS", "voice": "VOICE", "announcer": "ANNOUNCER",
        "sensitivity": "MOUSE SENSITIVITY", "ads_sens": "AIM SENSITIVITY",
        "invert_y": "INVERT Y", "toggle_crouch": "TOGGLE CROUCH", "bindings": "KEY BINDINGS",
        "press_key": "PRESS A KEY...", "screen_shake": "SCREEN SHAKE",
        "crosshair_style": "CROSSHAIR", "crosshair_color": "CROSSHAIR COLOR",
        "hit_markers": "HIT MARKERS", "hud_scale": "HUD SCALE", "hud_opacity": "HUD OPACITY",
        "hud_edit": "EDIT HUD LAYOUT", "hud_reset": "RESET LAYOUT", "language": "LANGUAGE",
        "lang_en": "English", "lang_he": "עברית", "quality_hint": "Low: fewer lights, no bloom, fewer particles.",
        "restart_hint": "Some changes apply on next launch.", "hud_edit_hint": "Drag elements. Wheel = size. Right-click = hide/show. ESC = done.",
        "cross_0": "CLASSIC", "cross_1": "CIRCLE", "cross_2": "DOT", "cross_3": "CROSS",
        "cross_4": "T-SHAPE", "cross_5": "X", "cross_6": "CHEVRON", "cross_7": "RING",
        "cross_8": "STATIC PLUS",
        "col_0": "CYAN", "col_1": "WHITE", "col_2": "MAGENTA", "col_3": "LIME", "col_4": "YELLOW",
        "col_5": "ORANGE", "col_6": "RED", "col_7": "BLUE",
        "crosshair_size": "CROSSHAIR SIZE", "crosshair_thickness": "THICKNESS",
        "crosshair_gap": "CENTER GAP", "crosshair_outline": "OUTLINE",
        "crosshair_dynamic": "DYNAMIC SPREAD", "crosshair_preview": "PREVIEW",
        "bind_forward": "Forward", "bind_back": "Back", "bind_left": "Left", "bind_right": "Right",
        "bind_jump": "Jump", "bind_sprint": "Sprint", "bind_crouch": "Crouch / Slide",
        "bind_fire": "Fire", "bind_ads": "Aim", "bind_reload": "Reload",
        "bind_ability1": "Ability 1", "bind_ability2": "Ability 2", "bind_melee": "Quick Melee",
        "bind_weapon1": "Primary", "bind_weapon2": "Secondary", "bind_weapon3": "Melee",
        "bind_scoreboard": "Scoreboard", "bind_interact": "Interact",
        "el_health": "Health", "el_energy": "Energy", "el_ammo": "Ammo",
        "el_abilities": "Abilities", "el_crosshair": "Crosshair", "el_killfeed": "Kill Feed",
        "el_matchinfo": "Match Info", "el_notices": "Notices", "el_damage_dir": "Damage Direction",
        # --- HUD ---
        "hp": "HP", "en": "EN", "reloading": "RELOADING", "no_ammo": "NO AMMO",
        "killed": "eliminated", "you": "YOU", "wave": "WAVE {n}",
        "lives_left": "LIVES {n}", "respawn_in": "RESPAWN IN {n}", "eliminated": "ELIMINATED",
        "spectating": "SPECTATING", "enemies_left": "ENEMIES {n}", "turret_lock": "TURRET LOCK", "drone_lock": "DRONE CHARGING",
        "pickup_ammo": "+{n} AMMO", "pickup_coins": "+{n} ¢", "pickup_xp": "+{n} XP",
        "energy_full": "ENERGY FULL", "charging": "CHARGING", "wave_incoming": "WAVE {n} INCOMING",
        "wave_cleared": "WAVE {n} CLEARED", "next_wave": "NEXT WAVE IN {n}",
        "first_to": "FIRST TO {n}", "team_blue": "CYAN", "team_red": "CRIMSON",
        "you_win": "VICTORY", "you_lose": "DEFEAT", "draw": "DRAW", "place": "#{n}",
        "sb_name": "NAME", "sb_kills": "K", "sb_deaths": "D", "sb_score": "SCORE",
        "sb_ping": "PING", "loot_empty": "RECHARGING", "ability_ready": "READY",
        "not_enough_energy": "NOT ENOUGH ENERGY", "cooldown_short": "{n}",
        "headshot": "HEADSHOT", "kill_confirm": "ELIMINATED {name}", "killed_by": "ELIMINATED BY {name}",
        "streak": "{n} KILL STREAK", "flashed": "", "lead": "YOU TAKE THE LEAD",
        # --- results ---
        "res_title": "MATCH COMPLETE", "res_xp": "+{n} XP", "res_coins": "+{n} ¢",
        "res_level_up": "LEVEL UP!  {n}", "res_tier_up": "BATTLE PASS TIER {n}",
        "res_achievement": "ACHIEVEMENT: {name}", "res_continue": "CONTINUE",
        "res_challenge": "CHALLENGE COMPLETE: {name}", "res_new_best": "NEW HIGH SCORE!",
        "res_tier_unlock": "{weapon}: UPGRADE TIER {n} UNLOCKED",
        # --- announcer captions ---
        "ann_fight": "FIGHT!", "ann_first_blood": "FIRST BLOOD", "ann_double_kill": "DOUBLE KILL",
        "ann_triple_kill": "TRIPLE KILL", "ann_multi_kill": "MULTI KILL",
        "ann_killing_spree": "KILLING SPREE", "ann_rampage": "RAMPAGE",
        "ann_unstoppable": "UNSTOPPABLE", "ann_one_minute": "ONE MINUTE REMAINING",
        "ann_victory": "VICTORY", "ann_defeat": "DEFEAT", "ann_wave_incoming": "WAVE INCOMING",
        "ann_wave_cleared": "WAVE CLEARED", "ann_three": "3", "ann_two": "2", "ann_one": "1",
    },
    "he": {
        "subtitle": "פרוטוקול זירה", "press_start": "לחצו על מקש כלשהו",
        "loading": "מאתחל את הרשת...", "loading_audio": "מסנתז שמע...",
        "play": "שחק", "multiplayer": "מרובה משתתפים", "story": "סיפור", "loadout": "ציוד",
        "battlepass": "כרטיס קרב", "locker": "ארונית", "career": "קריירה",
        "settings": "הגדרות", "quit": "יציאה", "back": "חזרה", "start": "התחל",
        "resume": "המשך", "quit_to_menu": "יציאה לתפריט", "apply": "החל",
        "reset_defaults": "איפוס לברירת מחדל", "confirm": "אישור", "cancel": "ביטול",
        "paused": "מושהה", "level": "רמה {n}", "coins": "{n} ¢", "restart": "הפעל מחדש",
        "mode_ffa": "כולם נגד כולם", "mode_duel": "1 על 1 נגד בוט", "mode_team": "קרב קבוצות",
        "mode_coop": "הישרדות שיתופית", "mode_endless": "הישרדות אינסופית",
        "desc_ffa": "כל אחד לעצמו. בוטים ממלאים מקומות פנויים.",
        "desc_duel": "זירה אחת. בוט אחד. בחרו רמת קושי.",
        "desc_team": "4 על 4 עם שותפי בינה מלאכותית נגד חוליית בוטים.",
        "desc_coop": "אתם ושותפים ממוחשבים מול גלים אינסופיים.",
        "desc_endless": "שרדו לבד גלים הולכים וגדלים של בוטים ורחפנים.",
        "opt_bots": "בוטים", "opt_difficulty": "רמת קושי", "diff_easy": "קל",
        "diff_normal": "רגיל", "diff_hard": "קשה", "diff_nightmare": "סיוט",
        "res_diff_mult": "{d} x{m}", "opt_time": "מגבלת זמן",
        "opt_score": "מגבלת ניקוד", "opt_lives": "מצב חיים", "opt_lives_count": "חיים",
        "opt_chaos": "מצב כאוס", "on": "פעיל", "off": "כבוי", "minutes": "{n} דק׳",
        "unlimited": "ללא", "select_mode": "בחירת מצב", "match_options": "אפשרויות משחק",
        "chaos_hint": "לייזרים סורקים, מוקשים ואזורי כבידה.",
        "lives_hint": "מספר חיים מוגבל במקום הופעה מחדש.",
        "mp_title": "מרובה משתתפים", "mp_name": "כינוי", "mp_server": "שרת / IP של המארח",
        "mp_host_online": "ארח ברשת", "mp_join_online": "הצטרף ברשת",
        "mp_host_lan": "ארח ברשת מקומית", "mp_join_lan": "הצטרף ברשת מקומית",
        "mp_code": "קוד חדר", "mp_room_code": "קוד חדר  {code}",
        "mp_waiting": "ממתין לשחקנים...", "mp_players": "שחקנים",
        "mp_start_match": "התחל משחק", "mp_connecting": "מתחבר...",
        "mp_failed": "החיבור נכשל: {err}", "mp_searching_lan": "מחפש את חדר {code} ברשת המקומית...",
        "mp_not_found": "החדר {code} לא נמצא", "mp_leave": "עזוב",
        "mp_find_rooms": "חיפוש חדרים", "mp_err_join_failed": "לא ניתן להתחבר לחדר הזה יותר.", "mp_rooms_title": "מאתר חדרים",
        "mp_rooms_searching": "מחפש ברשת שלך ובשרת הממסר...",
        "mp_rooms_count": "נמצאו {n} חדרים - מתעדכן אוטומטית",
        "mp_rooms_none": "עדיין לא נמצאו חדרים פתוחים. בקשו מחבר ללחוץ ארח, או ארחו בעצמכם.",
        "mp_rooms_relay_down": "(שרת הממסר {addr} לא זמין - מוצגים חדרים ברשת המקומית בלבד)",
        "mp_code_rules": "קוד חדר הוא 4 אותיות באנגלית, למשל DAMH. טיפ: לחצו חיפוש חדרים כדי להצטרף בלי להקליד קוד.",
        "rb_code": "קוד", "rb_host": "מארח", "rb_players": "שחקנים", "rb_state": "מצב",
        "rb_source": "איפה", "rb_lobby": "בלובי", "rb_playing": "במשחק", "rb_online": "מקוון",
        "rb_join": "הצטרף", "rb_refresh": "רענן",
        "mp_not_found_lan": "החדר {code} לא נמצא ברשת שלך. האם המארח מחובר לאותה רשת?",
        "mp_err_refused": "אין שרת משחק שפועל ב-{addr}. הכניסו את כתובת ה-IP של המארח בשדה שרת ממסר, או השתמשו בהצטרפות ברשת מקומית.",
        "mp_err_timeout": "השרת ב-{addr} לא ענה. בדקו את הכתובת ואת חומת האש של המארח.",
        "mp_err_address": "כתובת שרת לא מוכרת {addr}.",
        "mp_err_port": "לא ניתן לפתוח פורט לאירוח (תוכנה אחרת משתמשת בו).",
        "mp_hosting_local": "מארח במחשב הזה. חברים באותה רשת: חיפוש חדרים, או הקלידו את הקוד {code} ולחצו הצטרף ברשת מקומית. לא רואים את החדר? אפשרו את NEON GRID בחומת האש של Windows בשני המחשבים.",
        "mp_show_addr": "הצג כתובת", "mp_hide_addr": "הסתר כתובת",
        "mp_addr_line": "הכתובת שלך: {addr} - חברים יכולים להקליד אותה בשדה שרת / IP של המארח. שתפו רק עם אנשים שאתם סומכים עליהם.",
        "mp_host_only": "ממתין למארח שיתחיל...", "mp_disconnected": "החיבור נותק: {err}",
        "mp_hint": "שתפו את הקוד בן 4 האותיות עם חברים. רשת מקומית עובדת גם בלי אינטרנט.",
        "story_title": "מצב סיפור",
        "story_soon": "מערכת הסיפור היא מודול נפרד שעדיין לא הותקן.",
        "lo_primary": "נשק ראשי", "lo_secondary": "נשק משני", "lo_melee": "תגרה",
        "lo_ability1": "יכולת 1 [Q]", "lo_ability2": "יכולת 2 [E]",
        "lo_tier": "דרגת שדרוג", "lo_apply_chip": "השתמש בשבב שדרוג ({n})",
        "lo_locked": "נעול", "lo_buy": "קנה  {cost} ¢",
        "lo_buy_tier": "קנה דרגה {n}  -  {cost} ¢", "lo_need_more": "חסרים {n} מטבעות",
        "lo_buy_hint": "הרוויחו מטבעות מחיסול אויבים ופתחו את זה כאן.",
        "lo_coins_hint": "מטבעות מרוויחים מחיסולים",
        "shop": "חנות", "shop_weapons": "נשקים", "shop_melee": "תגרה",
        "shop_abilities": "יכולות", "shop_attachments": "תוספות",
        "shop_upgrades": "שדרוגים", "shop_boosts": "בוסטים", "shop_cosmetics": "עיצובים",
        "shop_owned": "בבעלותך", "shop_tier": "דרגה {n}/5", "shop_upgrade": "דרגה {n}  {cost} \u00a2",
        "shop_empty": "אין כאן עדיין כלום - קנו קודם נשק.", "edit_weapon": "ערוך נשק",
        "boost_xp2": "ניסיון כפול", "boost_coins15": "בהלת מטבעות", "boost_shield": "מגן הופעה",
        "boost_ammo": "תחמושת עודפת", "boost_left": "נותרו {n} משחקים",
        "boostd_xp2": "ניסיון כפול ב-{n} המשחקים הבאים.",
        "boostd_coins15": "+50% מטבעות ב-{n} המשחקים הבאים.",
        "boostd_shield": "הופעה עם מגן של 40 ב-{n} המשחקים הבאים.",
        "boostd_ammo": "+50% תחמושת רזרבית ב-{n} המשחקים הבאים.",
        "res_boosts": "בוסטים בשימוש: {names}",
        "gunsmith": "נשקייה", "mods": "תוספות", "slot_optic": "כוונת", "slot_muzzle": "לוע",
        "slot_magazine": "מחסנית", "slot_underbarrel": "מתחת לקנה", "slot_stock": "קת",
        "mod_none": "ללא", "mod_fitted": "מותקן", "mod_silent": "שקט",
        "mod_laser": "כוונת לייזר", "mod_reticle_dot": "נקודה אדומה", "mod_reticle_holo": "הולו",
        "mod_scoped": "טלסקופי", "gs_stats": "נתונים עם תוספות",
        "gs_hint": "קנו תוספת פעם אחת במטבעות והתקינו אותה על כל נשק מתאים.",
        "gs_no_slot": "אין תוספות למקום הזה", "st_spread": "פיזור",
        "st_recoil": "רתע", "st_zoom": "זום כיוון", "lo_weapon_xp": "ניסיון נשק {xp}",
        "lo_next_tier": "הדרגה הבאה ב-{xp} ניסיון", "lo_max_tier": "דרגה מרבית",
        "st_damage": "נזק", "st_firerate": "קצב אש", "st_magazine": "מחסנית",
        "st_reload": "טעינה", "st_range": "טווח", "st_handling": "תפעול", "st_dps": "נזק לשנייה",
        "st_mobility": "ניידות", "cooldown": "זמן טעינה {n} שנ׳", "energy_cost": "אנרגיה {n}",
        "bp_title": "כרטיס קרב - עונה 1: מתח", "bp_tier": "דרגה {n}",
        "bp_free": "חינם", "bp_premium": "פרימיום",
        "bp_unlock_premium": "פתח פרימיום ({cost} ¢)", "bp_claim": "קבל",
        "bp_claimed": "התקבל", "bp_locked": "נעול", "bp_xp": "{xp} / {need} ניסיון",
        "bp_premium_owned": "פרימיום פעיל", "bp_note": "מושג בניסיון ובמטבעות בלבד.",
        "rw_coins": "{n} מטבעות", "rw_chip": "שבב שדרוג", "rw_wskin": "עיצוב נשק: {name}",
        "rw_cskin": "חליפה: {name}", "rw_title": "תואר: {name}",
        "lk_title": "ארונית", "lk_weapon_skins": "עיצובי נשק", "lk_char_skins": "חליפות",
        "lk_equip": "צייד", "lk_equipped": "מצויד", "lk_buy": "קנה {cost} ¢",
        "lk_not_enough": "אין מספיק מטבעות", "lk_pass_only": "כרטיס קרב", "lk_titles": "תארים",
        "cr_title": "קריירה", "cr_stats": "סטטיסטיקה", "cr_achievements": "הישגים",
        "cr_challenges": "אתגרים יומיים", "cr_highscores": "שיאים",
        "cs_kills": "חיסולים", "cs_deaths": "מוות", "cs_kd": "יחס ח/מ", "cs_headshots": "פגיעות ראש",
        "cs_accuracy": "דיוק", "cs_matches": "משחקים", "cs_wins": "ניצחונות",
        "cs_time": "זמן משחק", "cs_melee": "חיסולי תגרה", "cs_streak": "רצף הטוב ביותר",
        "cs_damage": "נזק שנגרם", "cs_abilities": "שימוש ביכולות",
        "cs_drones": "רחפנים שהושמדו", "cs_turrets": "צריחים שהושמדו",
        "hs_endless": "אינסופי: הגל הטוב ביותר", "hs_endless_kills": "אינסופי: הכי הרבה חיסולים",
        "hs_ffa": "כולם נגד כולם: שיא חיסולים", "hs_coop": "שיתופי: הגל הטוב ביותר",
        "hs_duel": "ניצחונות דו-קרב (ק/ר/ק/ס)", "ch_reward": "+{xp} ניסיון  +{coins} ¢",
        "ch_done": "הושלם",
        "set_title": "הגדרות", "tab_video": "תצוגה", "tab_audio": "שמע",
        "tab_controls": "שליטה", "tab_gameplay": "משחק", "tab_hud": "ממשק",
        "tab_language": "שפה", "quality": "איכות", "q_high": "גבוהה", "q_low": "נמוכה",
        "fullscreen": "מסך מלא", "resolution": "רזולוציה", "vsync": "סנכרון אנכי",
        "fps_cap": "מגבלת פריימים", "fov": "שדה ראייה", "show_fps": "הצג פריימים",
        "bloom": "זוהר", "reflections": "השתקפויות רצפה", "master": "ראשי",
        "music": "מוזיקה", "effects": "אפקטים", "voice": "קול", "announcer": "כרוז",
        "sensitivity": "רגישות עכבר", "ads_sens": "רגישות כיוון",
        "invert_y": "היפוך ציר Y", "toggle_crouch": "כריעה במתג", "bindings": "מקשים",
        "press_key": "לחצו על מקש...", "screen_shake": "רעידת מסך",
        "crosshair_style": "כוונת", "crosshair_color": "צבע כוונת",
        "hit_markers": "סימוני פגיעה", "hud_scale": "גודל ממשק", "hud_opacity": "שקיפות ממשק",
        "hud_edit": "ערוך פריסת ממשק", "hud_reset": "אפס פריסה", "language": "שפה",
        "lang_en": "English", "lang_he": "עברית",
        "quality_hint": "נמוכה: פחות אורות, ללא זוהר, פחות חלקיקים.",
        "restart_hint": "חלק מהשינויים יחולו בהפעלה הבאה.",
        "hud_edit_hint": "גררו רכיבים. גלגלת = גודל. קליק ימני = הסתר/הצג. ESC = סיום.",
        "cross_0": "קלאסי", "cross_1": "עיגול", "cross_2": "נקודה", "cross_3": "צלב",
        "cross_4": "צורת T", "cross_5": "X", "cross_6": "חץ", "cross_7": "טבעת",
        "cross_8": "פלוס קבוע",
        "col_0": "טורקיז", "col_1": "לבן", "col_2": "מג׳נטה", "col_3": "ירוק", "col_4": "צהוב",
        "col_5": "כתום", "col_6": "אדום", "col_7": "כחול",
        "crosshair_size": "גודל כוונת", "crosshair_thickness": "עובי",
        "crosshair_gap": "רווח במרכז", "crosshair_outline": "קו מתאר",
        "crosshair_dynamic": "פיזור דינמי", "crosshair_preview": "תצוגה מקדימה",
        "bind_forward": "קדימה", "bind_back": "אחורה", "bind_left": "שמאלה", "bind_right": "ימינה",
        "bind_jump": "קפיצה", "bind_sprint": "ריצה", "bind_crouch": "כריעה / החלקה",
        "bind_fire": "ירי", "bind_ads": "כיוון", "bind_reload": "טעינה",
        "bind_ability1": "יכולת 1", "bind_ability2": "יכולת 2", "bind_melee": "תגרה מהירה",
        "bind_weapon1": "נשק ראשי", "bind_weapon2": "נשק משני", "bind_weapon3": "נשק תגרה",
        "bind_scoreboard": "לוח תוצאות", "bind_interact": "פעולה",
        "el_health": "בריאות", "el_energy": "אנרגיה", "el_ammo": "תחמושת",
        "el_abilities": "יכולות", "el_crosshair": "כוונת", "el_killfeed": "עדכוני חיסול",
        "el_matchinfo": "מידע משחק", "el_notices": "הודעות", "el_damage_dir": "כיוון פגיעה",
        "hp": "חיים", "en": "אנרגיה", "reloading": "טוען", "no_ammo": "אין תחמושת",
        "killed": "חיסל את", "you": "אתה", "wave": "גל {n}",
        "lives_left": "חיים {n}", "respawn_in": "חזרה בעוד {n}", "eliminated": "חוסלת",
        "spectating": "צופה", "enemies_left": "אויבים {n}", "turret_lock": "צריח ננעל", "drone_lock": "רחפן נטען",
        "pickup_ammo": "+{n} תחמושת", "pickup_coins": "+{n} ¢", "pickup_xp": "+{n} ניסיון",
        "energy_full": "אנרגיה מלאה", "charging": "נטען", "wave_incoming": "גל {n} מתקרב",
        "wave_cleared": "גל {n} הושלם", "next_wave": "הגל הבא בעוד {n}",
        "first_to": "הראשון ל-{n}", "team_blue": "טורקיז", "team_red": "ארגמן",
        "you_win": "ניצחון", "you_lose": "הפסד", "draw": "תיקו", "place": "מקום {n}",
        "sb_name": "שם", "sb_kills": "ח", "sb_deaths": "מ", "sb_score": "ניקוד",
        "sb_ping": "פינג", "loot_empty": "נטען", "ability_ready": "מוכן",
        "not_enough_energy": "אין מספיק אנרגיה", "cooldown_short": "{n}",
        "headshot": "פגיעת ראש", "kill_confirm": "חיסלת את {name}", "killed_by": "חוסלת על ידי {name}",
        "streak": "רצף של {n} חיסולים", "flashed": "", "lead": "עלית להובלה",
        "res_title": "המשחק הסתיים", "res_xp": "+{n} ניסיון", "res_coins": "+{n} ¢",
        "res_level_up": "עלית רמה!  {n}", "res_tier_up": "דרגה {n} בכרטיס הקרב",
        "res_achievement": "הישג: {name}", "res_continue": "המשך",
        "res_challenge": "אתגר הושלם: {name}", "res_new_best": "שיא חדש!",
        "res_tier_unlock": "{weapon}: דרגת שדרוג {n} נפתחה",
        "ann_fight": "קרב!", "ann_first_blood": "דם ראשון", "ann_double_kill": "חיסול כפול",
        "ann_triple_kill": "חיסול משולש", "ann_multi_kill": "חיסול מרובה",
        "ann_killing_spree": "מסע חיסולים", "ann_rampage": "השתוללות",
        "ann_unstoppable": "בלתי ניתן לעצירה", "ann_one_minute": "נותרה דקה אחת",
        "ann_victory": "ניצחון", "ann_defeat": "הפסד", "ann_wave_incoming": "גל מתקרב",
        "ann_wave_cleared": "הגל הושלם", "ann_three": "3", "ann_two": "2", "ann_one": "1",
    },
}

# Achievement and challenge names are looked up with these prefixes.
STRINGS["en"].update({
    "ach_first_blood": "First Blood|Get your first elimination.",
    "ach_centurion": "Centurion|Eliminate 100 enemies.",
    "ach_sharpshooter": "Sharpshooter|Land 50 headshots.",
    "ach_arsenal": "Arsenal|Get kills with 10 different weapons.",
    "ach_blade_runner": "Blade Runner|Get 25 melee eliminations.",
    "ach_survivor": "Survivor|Reach wave 10 in Endless Survival.",
    "ach_untouchable": "Untouchable|Win a Free For All without dying.",
    "ach_hazard_hunter": "Hazard Hunter|Destroy 20 turrets or drones.",
    "ach_chaos_theory": "Chaos Theory|Win a match with Chaos Mode on.",
    "ach_duelist": "Duelist|Beat a Hard or Nightmare bot in 1v1.",
    "ach_team_player": "Team Player|Win 5 Team Battles.",
    "ach_slider": "Slide Master|Slide 200 times.",
    "ach_power_user": "Power User|Use abilities 100 times.",
    "ach_rich": "Neon Tycoon|Earn 5000 coins in total.",
    "ach_level10": "Rising Signal|Reach level 10.",
    "ach_pass_complete": "Fully Charged|Reach battle pass tier 50.",
    "ach_streak5": "On Fire|Get a 5 kill streak.",
    "ach_streak10": "Grid Legend|Get a 10 kill streak.",
    "ach_online": "Connected|Play an online or LAN match.",
    "ach_recharged": "Recharged|Use charging ports 30 times.",
    "chl_kills": "Eliminate {n} enemies", "chl_headshots": "Land {n} headshots",
    "chl_melee": "Get {n} melee eliminations", "chl_drones": "Destroy {n} drones or turrets",
    "chl_matches": "Complete {n} matches", "chl_abilities": "Use abilities {n} times",
    "chl_loot": "Open {n} loot boxes", "chl_slides": "Slide {n} times",
    "chl_wins": "Win {n} matches", "chl_damage": "Deal {n} damage",
})
STRINGS["he"].update({
    "ach_first_blood": "דם ראשון|בצעו את החיסול הראשון.",
    "ach_centurion": "מאה|חסלו 100 אויבים.",
    "ach_sharpshooter": "צלף|בצעו 50 פגיעות ראש.",
    "ach_arsenal": "ארסנל|חסלו עם 10 כלי נשק שונים.",
    "ach_blade_runner": "רץ הלהב|בצעו 25 חיסולי תגרה.",
    "ach_survivor": "שורד|הגיעו לגל 10 בהישרדות אינסופית.",
    "ach_untouchable": "בלתי נגיע|נצחו בכולם נגד כולם בלי למות.",
    "ach_hazard_hunter": "צייד סכנות|השמידו 20 צריחים או רחפנים.",
    "ach_chaos_theory": "תורת הכאוס|נצחו משחק במצב כאוס.",
    "ach_duelist": "דו-קרבן|נצחו בוט קשה ב-1 על 1.",
    "ach_team_player": "שחקן קבוצתי|נצחו 5 קרבות קבוצות.",
    "ach_slider": "אמן ההחלקה|החליקו 200 פעמים.",
    "ach_power_user": "משתמש כבד|השתמשו ביכולות 100 פעמים.",
    "ach_rich": "טייקון ניאון|הרוויחו 5000 מטבעות בסך הכול.",
    "ach_level10": "אות עולה|הגיעו לרמה 10.",
    "ach_pass_complete": "טעון לגמרי|הגיעו לדרגה 50 בכרטיס הקרב.",
    "ach_streak5": "בוער|רצף של 5 חיסולים.",
    "ach_streak10": "אגדת הרשת|רצף של 10 חיסולים.",
    "ach_online": "מחובר|שחקו משחק מקוון או ברשת מקומית.",
    "ach_recharged": "נטען מחדש|השתמשו בעמדות טעינה 30 פעמים.",
    "chl_kills": "חסלו {n} אויבים", "chl_headshots": "בצעו {n} פגיעות ראש",
    "chl_melee": "בצעו {n} חיסולי תגרה", "chl_drones": "השמידו {n} רחפנים או צריחים",
    "chl_matches": "השלימו {n} משחקים", "chl_abilities": "השתמשו ביכולות {n} פעמים",
    "chl_loot": "פתחו {n} תיבות שלל", "chl_slides": "החליקו {n} פעמים",
    "chl_wins": "נצחו ב-{n} משחקים", "chl_damage": "גרמו {n} נזק",
})


def set_language(lang):
    global _lang
    _lang = lang if lang in STRINGS else "en"


def language():
    return _lang


def is_rtl():
    return _lang == "he"


def raw(key, **fmt):
    """Logical-order string (use for storage / logic, not display)."""
    s = STRINGS.get(_lang, {}).get(key)
    if s is None:
        s = STRINGS["en"].get(key, key)
    if fmt:
        try:
            s = s.format(**fmt)
        except (KeyError, IndexError, ValueError):
            pass
    return s


def t(key, _wrap=None, **fmt):
    """Display string for ``key`` in the current language (visual order).

    ``_wrap`` (characters per line) pre-wraps RTL text *before* reordering, so
    wrapped Hebrew lines stay in reading order."""
    s = raw(key, **fmt)
    if _wrap and is_rtl():
        s = wrap(s, _wrap)
    return visual(s)


def wrap(s, width):
    import textwrap
    return "\n".join(textwrap.wrap(s, width)) or s


def pair(key):
    """Split a 'Name|Description' entry into two display strings."""
    s = raw(key)
    name, _, desc = s.partition("|")
    return visual(name), visual(desc)


# ----------------------------------------------------------------------------
# Minimal bidi: convert logical-order text to visual order for RTL display.
# ----------------------------------------------------------------------------
_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<"}


def _dir(ch):
    o = ord(ch)
    if 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "R"
    if ch.isalnum():
        return "L"
    return "N"


def _has_rtl(s):
    return any(_dir(c) == "R" for c in s)


def visual(s):
    if not is_rtl() or not s or not _has_rtl(s):
        return s
    return "\n".join(_visual_line(line) for line in s.split("\n"))


def _visual_line(s):
    dirs = [_dir(c) for c in s]
    n = len(s)
    # resolve neutrals: take the surrounding strong direction if both sides
    # agree, otherwise the paragraph direction (R).
    resolved = list(dirs)
    i = 0
    while i < n:
        if dirs[i] != "N":
            i += 1
            continue
        j = i
        while j < n and dirs[j] == "N":
            j += 1
        prev_d = dirs[i - 1] if i > 0 else "R"
        next_d = dirs[j] if j < n else "R"
        d = prev_d if prev_d == next_d else "R"
        for k in range(i, j):
            resolved[k] = d
        i = j
    # group into runs
    runs = []
    cur = ""
    cur_d = None
    for ch, d in zip(s, resolved):
        if d != cur_d and cur:
            runs.append((cur_d, cur))
            cur = ""
        cur_d = d
        cur += ch
    if cur:
        runs.append((cur_d, cur))
    out = []
    for d, text in reversed(runs):
        if d == "R":
            out.append("".join(_MIRROR.get(c, c) for c in reversed(text)))
        else:
            out.append(text)
    return "".join(out)
