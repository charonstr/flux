from datetime import datetime, timedelta, timezone
import json
import random
import sqlite3
import time

def register_fearofabyss_backend(app, *,
    request, redirect, render_template, url_for,
    connect, applyledger, initialize_user_economy, get_balance, spend_gold,
    userlanguage, currentaccount, texts, navcontext, viewfile,
):
    def _foa_connect():
        return connect("fearofabys")

    @app.route("/fear-of-abyss")
    def fearofabyss():
        current = userlanguage()
        if not current:
            return redirect(url_for("choose"))
        account = currentaccount()
        if not account:
            return redirect(url_for("login"))
        initialize_user_economy(account[0])
        content = texts(current)
        ctx = navcontext(content, current)
        ctx["balance"] = int(get_balance(account[0]))
        return render_template(
            viewfile("fearofabyss.html"),
            **ctx,
        )
    
    
    FOA_BUILDINGS = {
        "hospital": {
            "name": "Hastane",
            "name_key": "foa_building_hospital_name",
            "desc": "Yaralı kahramanlar daha hızlı iyileşir. Seviye arttıkça etki artar.",
            "desc_key": "foa_building_hospital_desc",
        },
        "training_arena": {
            "name": "Eğitim Arenası",
            "name_key": "foa_building_training_arena_name",
            "desc": "Seçilen kahramanları süreli eğitip XP kazandırır. Kapasite ve XP seviye ile artar.",
            "desc_key": "foa_building_training_arena_desc",
        },
        "vendor": {
            "name": "Satıcı",
            "name_key": "foa_building_vendor_name",
            "desc": "Her saat rastgele 4 eşya satar. Seviye arttıkça eşya kalitesi artar.",
            "desc_key": "foa_building_vendor_desc",
        },
        "blacksmith": {
            "name": "Demirci",
            "name_key": "foa_building_blacksmith_name",
            "desc": "Silah üretimi/satın alımı için kullanılır. Seviye eşya kalitesini artırır.",
            "desc_key": "foa_building_blacksmith_desc",
        },
        "armorer": {
            "name": "Zırhçı",
            "name_key": "foa_building_armorer_name",
            "desc": "Zırh üretimi/satın alımı için kullanılır. Seviye ile yeni eşyalar açılır.",
            "desc_key": "foa_building_armorer_desc",
        },
        "mage_tower": {
            "name": "Büyü Kulesi",
            "name_key": "foa_building_mage_tower_name",
            "desc": "Kahraman çağırımı için kullanılır. Seviye ile güçlü kahraman şansı artar.",
            "desc_key": "foa_building_mage_tower_desc",
        },
        "depot": {
            "name": "Depo",
            "name_key": "foa_building_depot_name",
            "desc": "Tüm eşyalar burada depolanır. Seviye depolama kapasitesini artırır.",
            "desc_key": "foa_building_depot_desc",
        },
    }
    FOA_BUILDING_VISUALS = {
        "hospital": {"icon": "fa-solid fa-house-medical", "color": "#ef4444"},
        "training_arena": {"icon": "fa-solid fa-dumbbell", "color": "#22c55e"},
        "vendor": {"icon": "fa-solid fa-store", "color": "#f59e0b"},
        "blacksmith": {"icon": "fa-solid fa-hammer", "color": "#f97316"},
        "armorer": {"icon": "fa-solid fa-shield-halved", "color": "#06b6d4"},
        "mage_tower": {"icon": "fa-solid fa-hat-wizard", "color": "#8b5cf6"},
        "depot": {"icon": "fa-solid fa-warehouse", "color": "#3b82f6"},
    }
    FOA_RECIPES = {
        "iron_sword": {"name": "Demir Kilic", "building_key": "blacksmith", "min_level": 2, "recipe_cost": 220, "craft_cost": 80},
        "steel_blade": {"name": "Celik Bicak", "building_key": "blacksmith", "min_level": 4, "recipe_cost": 480, "craft_cost": 160},
        "chain_armor": {"name": "Zincir Zirh", "building_key": "armorer", "min_level": 2, "recipe_cost": 240, "craft_cost": 90},
        "plate_armor": {"name": "Plaka Zirh", "building_key": "armorer", "min_level": 5, "recipe_cost": 620, "craft_cost": 220},
        "healing_kit": {"name": "Iyilesme Kiti", "building_key": "hospital", "min_level": 3, "recipe_cost": 260, "craft_cost": 110},
        "mana_orb": {"name": "Mana Kuresi", "building_key": "mage_tower", "min_level": 3, "recipe_cost": 340, "craft_cost": 140},
    }
    FOA_MAX_LEVEL = 10
    FOA_UPGRADE_MINUTES = {
        1: (5, 10),
        2: (10, 20),
        3: (30, 60),
        4: (60, 120),
        5: (180, 240),
        6: (240, 300),
        7: (360, 420),
        8: (420, 480),
        9: (540, 600),
    }
    FOA_EQUIP_DEFS = {
        "iron_sword": {"name": "Demir Kilic", "slot": "weapon", "attack": 18, "defense": 0, "hp": 0},
        "steel_blade": {"name": "Celik Bicak", "slot": "weapon", "attack": 30, "defense": 4, "hp": 0},
        "chain_armor": {"name": "Zincir Zirh", "slot": "armor", "attack": 0, "defense": 18, "hp": 45},
        "plate_armor": {"name": "Plaka Zirh", "slot": "armor", "attack": 0, "defense": 30, "hp": 80},
    }
    FOA_CHEST_TIERS = ["hurda", "siradan", "elit", "efsanevi", "ebedi"]
    FOA_CHEST_KEYS = {
        "hurda": "chest_hurda",
        "siradan": "chest_siradan",
        "elit": "chest_elit",
        "efsanevi": "chest_efsanevi",
        "ebedi": "chest_ebedi",
    }
    FOA_TOWER_MAX_FLOOR = 100
    FOA_INFINITY_STONE_DROP_CHANCE = 0.0001
    FOA_SUMMON_COST_SINGLE = 500
    FOA_SUMMON_COST_TEN = 5000
    
    FOA_HERO_POOL = [
        # Common (30)
        {"key": "c01", "name": "Aerin", "rarity": "common"},
        {"key": "c02", "name": "Brom", "rarity": "common"},
        {"key": "c03", "name": "Cyra", "rarity": "common"},
        {"key": "c04", "name": "Doran", "rarity": "common"},
        {"key": "c05", "name": "Elra", "rarity": "common"},
        {"key": "c06", "name": "Fenn", "rarity": "common"},
        {"key": "c07", "name": "Garen", "rarity": "common"},
        {"key": "c08", "name": "Hale", "rarity": "common"},
        {"key": "c09", "name": "Ira", "rarity": "common"},
        {"key": "c10", "name": "Jorin", "rarity": "common"},
        {"key": "c11", "name": "Kael", "rarity": "common"},
        {"key": "c12", "name": "Lena", "rarity": "common"},
        {"key": "c13", "name": "Mira", "rarity": "common"},
        {"key": "c14", "name": "Nox", "rarity": "common"},
        {"key": "c15", "name": "Orin", "rarity": "common"},
        {"key": "c16", "name": "Phea", "rarity": "common"},
        {"key": "c17", "name": "Quin", "rarity": "common"},
        {"key": "c18", "name": "Rhea", "rarity": "common"},
        {"key": "c19", "name": "Sorn", "rarity": "common"},
        {"key": "c20", "name": "Tera", "rarity": "common"},
        {"key": "c21", "name": "Ulric", "rarity": "common"},
        {"key": "c22", "name": "Vera", "rarity": "common"},
        {"key": "c23", "name": "Wynn", "rarity": "common"},
        {"key": "c24", "name": "Xara", "rarity": "common"},
        {"key": "c25", "name": "Yori", "rarity": "common"},
        {"key": "c26", "name": "Zane", "rarity": "common"},
        {"key": "c27", "name": "Asha", "rarity": "common"},
        {"key": "c28", "name": "Bran", "rarity": "common"},
        {"key": "c29", "name": "Cleo", "rarity": "common"},
        {"key": "c30", "name": "Dax", "rarity": "common"},
        # Elite (10)
        {"key": "e01", "name": "Ardent Vale", "rarity": "elite"},
        {"key": "e02", "name": "Briar Thorn", "rarity": "elite"},
        {"key": "e03", "name": "Crimson Jax", "rarity": "elite"},
        {"key": "e04", "name": "Dread Voss", "rarity": "elite"},
        {"key": "e05", "name": "Ember Lyra", "rarity": "elite"},
        {"key": "e06", "name": "Frost Cain", "rarity": "elite"},
        {"key": "e07", "name": "Gale Orion", "rarity": "elite"},
        {"key": "e08", "name": "Hexa Rune", "rarity": "elite"},
        {"key": "e09", "name": "Iron Rook", "rarity": "elite"},
        {"key": "e10", "name": "Jade Vex", "rarity": "elite"},
        # Legendary (5)
        {"key": "l01", "name": "Aurelion", "rarity": "legendary"},
        {"key": "l02", "name": "Bellatrix", "rarity": "legendary"},
        {"key": "l03", "name": "Chrona", "rarity": "legendary"},
        {"key": "l04", "name": "Drakon", "rarity": "legendary"},
        {"key": "l05", "name": "Elyndra", "rarity": "legendary"},
        # Mystic (3)
        {"key": "m01", "name": "Nyx Astral", "rarity": "mystic"},
        {"key": "m02", "name": "Omen Void", "rarity": "mystic"},
        {"key": "m03", "name": "Prisma", "rarity": "mystic"},
        # Eternal (2)
        {"key": "t01", "name": "Aeon Prime", "rarity": "eternal"},
        {"key": "t02", "name": "Eternis", "rarity": "eternal"},
    ]
    
    FOA_RARITY_BASE_WEIGHTS = {
        "common": 95.0,
        "elite": 5.0,
        "legendary": 0.0,
        "mystic": 0.001,
        "eternal": 0.0001,
    }
    
    
    def _foa_enemy_for_floor(floor: int) -> dict:
        f = max(1, min(FOA_TOWER_MAX_FLOOR, int(floor)))
        boss = (f % 5 == 0)
        count = 1 + (f // 12)
        if boss:
            count = max(1, count // 2)
        base = 120 + (f * 35)
        if boss:
            base = int(base * 2.2)
        names = ["Abyss Slime", "Void Knight", "Night Stalker", "Crypt Beast", "Abyss Lord"]
        enemy_name = names[(f - 1) % len(names)] + (" Boss" if boss else "")
        return {
            "floor": f,
            "enemy_name": enemy_name,
            "enemy_count": int(count),
            "enemy_power": int(base * count),
            "is_boss": boss,
        }
    
    
    def _foa_difficulty(party_power: int, enemy_power: int) -> str:
        if party_power <= 0:
            return "very_hard"
        ratio = float(enemy_power) / float(max(1, party_power))
        if ratio >= 1.6:
            return "very_hard"
        if ratio >= 1.2:
            return "hard"
        if ratio >= 0.85:
            return "medium"
        return "easy"
    
    
    def _foa_battle_duration_sec(difficulty: str) -> int:
        if difficulty == "very_hard":
            return 3600
        if difficulty == "hard":
            return 2400
        if difficulty == "medium":
            return 1200
        return random.randint(300, 600)
    
    
    def _foa_rarity_weights_for_mage_level(level: int) -> dict:
        lvl = max(1, int(level))
        common_drop = min(30.0, (lvl - 1) * 1.2)
        weights = dict(FOA_RARITY_BASE_WEIGHTS)
        weights["common"] = max(5.0, weights["common"] - common_drop)
        bonus = common_drop
        weights["elite"] += bonus * 0.55
        weights["legendary"] += bonus * 0.35
        weights["mystic"] += bonus * 0.09
        weights["eternal"] += bonus * 0.01
        return weights
    
    
    def _foa_pick_hero_template(mage_level: int) -> dict:
        weights = _foa_rarity_weights_for_mage_level(mage_level)
        rarity_roll = random.random() * sum(weights.values())
        acc = 0.0
        chosen = "common"
        for r in ["common", "elite", "legendary", "mystic", "eternal"]:
            acc += float(weights.get(r, 0.0))
            if rarity_roll <= acc:
                chosen = r
                break
        pool = [h for h in FOA_HERO_POOL if h["rarity"] == chosen]
        if not pool:
            pool = [h for h in FOA_HERO_POOL if h["rarity"] == "common"]
        return random.choice(pool)
    
    
    def _foa_base_stats_for_rarity(rarity: str) -> tuple[int, int, int]:
        r = str(rarity)
        if r == "eternal":
            return 340, 230, 300
        if r == "mystic":
            return 280, 190, 250
        if r == "legendary":
            return 220, 150, 210
        if r == "elite":
            return 160, 110, 160
        return 120, 80, 130
    
    
    def _foa_xp_to_next(level: int) -> int:
        l = max(1, int(level))
        return 100 + (l - 1) * 40
    
    
    def _foa_add_item(db, user_id: int, item_key: str, qty: int = 1) -> None:
        if int(qty) <= 0:
            return
        db.execute(
            """
            INSERT INTO foa_items (user_id, item_key, qty, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, item_key)
            DO UPDATE SET qty = foa_items.qty + excluded.qty, updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), str(item_key), int(qty)),
        )
    
    
    def _foa_item_display_name(item_key: str) -> str:
        names = {
            "potion_small": "Kucuk Potion",
            "potion_big": "Buyuk Potion",
            "iron_sword": "Demir Kilic",
            "steel_blade": "Celik Bicak",
            "chain_armor": "Zincir Zirh",
            "plate_armor": "Plaka Zirh",
        }
        if item_key in names:
            return names[item_key]
        for tier, key in FOA_CHEST_KEYS.items():
            if item_key == key:
                return f"{tier.title()} Kasa"
        return str(item_key)
    
    
    def _foa_roll_chest_tier(floor: int) -> str:
        f = int(max(1, floor))
        r = random.random()
        if f >= 80 and r < 0.0005:
            return "ebedi"
        if f >= 50 and r < 0.01:
            return "efsanevi"
        if f >= 25 and r < 0.08:
            return "elit"
        if f >= 10 and r < 0.35:
            return "siradan"
        return "hurda"
    
    
    def _foa_roll_chest_loot(tier: str) -> dict:
        t = str(tier)
        pools = {
            "hurda": [
                ("gold", random.randint(15, 55)),
                ("potion_small", random.randint(1, 2)),
            ],
            "siradan": [
                ("gold", random.randint(60, 140)),
                ("potion_small", random.randint(1, 3)),
                ("iron_sword", 1),
                ("chain_armor", 1),
            ],
            "elit": [
                ("gold", random.randint(160, 360)),
                ("potion_big", random.randint(1, 2)),
                ("steel_blade", 1),
                ("plate_armor", 1),
            ],
            "efsanevi": [
                ("gold", random.randint(420, 900)),
                ("potion_big", random.randint(2, 4)),
                ("steel_blade", random.randint(1, 2)),
                ("plate_armor", random.randint(1, 2)),
            ],
            "ebedi": [
                ("gold", random.randint(1200, 3000)),
                ("potion_big", random.randint(4, 8)),
                ("steel_blade", random.randint(2, 4)),
                ("plate_armor", random.randint(2, 4)),
            ],
        }
        options = pools.get(t, pools["hurda"])
        pick = random.choice(options)
        return {"item_key": str(pick[0]), "qty": int(pick[1])}
    
    
    def _foa_refresh_vendor_stock(user_id: int) -> None:
        now_iso = _foa_now().isoformat()
        with _foa_connect() as db:
            rows = db.execute(
                "SELECT slot_idx, expires_at FROM foa_vendor_stock WHERE user_id = ? ORDER BY slot_idx ASC",
                (int(user_id),),
            ).fetchall()
            if rows and all(str(r[1] or "") > now_iso for r in rows):
                return
            db.execute("DELETE FROM foa_vendor_stock WHERE user_id = ?", (int(user_id),))
            pool = [
                ("potion_small", "Kucuk Potion", random.randint(35, 75), random.randint(1, 5)),
                ("potion_big", "Buyuk Potion", random.randint(120, 240), random.randint(1, 4)),
                ("iron_sword", "Demir Kilic", random.randint(260, 420), random.randint(1, 2)),
                ("chain_armor", "Zincir Zirh", random.randint(300, 500), random.randint(1, 2)),
                ("steel_blade", "Celik Bicak", random.randint(700, 1200), 1),
                ("plate_armor", "Plaka Zirh", random.randint(850, 1450), 1),
            ]
            random.shuffle(pool)
            expires = (_foa_now() + timedelta(hours=1)).isoformat()
            for i, (k, n, p, q) in enumerate(pool[:4], start=1):
                db.execute(
                    """
                    INSERT INTO foa_vendor_stock (user_id, slot_idx, item_key, item_name, price, qty, expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (int(user_id), int(i), str(k), str(n), int(p), int(q), expires),
                )
    
    
    def _foa_apply_hero_xp(db, user_id: int, hero_id: str, amount: int) -> None:
        if int(amount) <= 0:
            return
        row = db.execute(
            "SELECT level, xp, attack, defense, hp, max_hp, is_dead FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
            (int(user_id), str(hero_id)),
        ).fetchone()
        if not row:
            return
        level, xp, attack, defense, hp, max_hp, is_dead = [int(x or 0) for x in row]
        if is_dead == 1:
            return
        xp += int(amount)
        gained_hp = 0
        while xp >= _foa_xp_to_next(level):
            xp -= _foa_xp_to_next(level)
            level += 1
            attack += 12
            defense += 8
            max_hp += 25
            gained_hp += 25
        hp = min(max_hp, max(0, hp + gained_hp))
        db.execute(
            """
            UPDATE foa_heroes
            SET level = ?, xp = ?, attack = ?, defense = ?, max_hp = ?, hp = ?, power = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND hero_id = ?
            """,
            (int(level), int(xp), int(attack), int(defense), int(max_hp), int(hp), int(attack), int(user_id), str(hero_id)),
        )
    
    
    def _foa_ensure_table() -> None:
        with _foa_connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_buildings (
                    user_id INTEGER NOT NULL,
                    card_id TEXT NOT NULL,
                    building_key TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    base_cost INTEGER NOT NULL,
                    upgrading_to INTEGER NOT NULL DEFAULT 0,
                    upgrade_started_at TEXT NOT NULL DEFAULT '',
                    upgrade_ends_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, card_id)
                )
                """
            )
            cols = [r[1] for r in db.execute("PRAGMA table_info(foa_buildings)").fetchall()]
            if "upgrade_started_at" not in cols:
                db.execute("ALTER TABLE foa_buildings ADD COLUMN upgrade_started_at TEXT NOT NULL DEFAULT ''")
    
    
    def _foa_ensure_recipe_tables() -> None:
        with _foa_connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_recipe_owns (
                    user_id INTEGER NOT NULL,
                    recipe_key TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, recipe_key)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_items (
                    user_id INTEGER NOT NULL,
                    item_key TEXT NOT NULL,
                    qty INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, item_key)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_tower (
                    user_id INTEGER PRIMARY KEY,
                    current_floor INTEGER NOT NULL DEFAULT 1,
                    infinity_stones INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_heroes (
                    user_id INTEGER NOT NULL,
                    hero_id TEXT NOT NULL,
                    hero_key TEXT NOT NULL DEFAULT '',
                    hero_name TEXT NOT NULL,
                    rarity TEXT NOT NULL DEFAULT 'common',
                    power INTEGER NOT NULL DEFAULT 100,
                    level INTEGER NOT NULL DEFAULT 1,
                    xp INTEGER NOT NULL DEFAULT 0,
                    attack INTEGER NOT NULL DEFAULT 100,
                    defense INTEGER NOT NULL DEFAULT 50,
                    hp INTEGER NOT NULL DEFAULT 100,
                    max_hp INTEGER NOT NULL DEFAULT 100,
                    is_dead INTEGER NOT NULL DEFAULT 0,
                    dead_at TEXT NOT NULL DEFAULT '',
                    delete_at TEXT NOT NULL DEFAULT '',
                    in_party INTEGER NOT NULL DEFAULT 0,
                    hospital_until TEXT NOT NULL DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, hero_id)
                )
                """
            )
            hcols = [r[1] for r in db.execute("PRAGMA table_info(foa_heroes)").fetchall()]
            if "hero_key" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN hero_key TEXT NOT NULL DEFAULT ''")
            if "rarity" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN rarity TEXT NOT NULL DEFAULT 'common'")
            if "level" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
            if "xp" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN xp INTEGER NOT NULL DEFAULT 0")
            if "attack" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN attack INTEGER NOT NULL DEFAULT 100")
            if "defense" not in hcols:
                db.execute("ALTER TABLE foa_heroes ADD COLUMN defense INTEGER NOT NULL DEFAULT 50")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_battles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    floor INTEGER NOT NULL,
                    enemy_name TEXT NOT NULL,
                    enemy_power INTEGER NOT NULL,
                    enemy_count INTEGER NOT NULL,
                    difficulty TEXT NOT NULL,
                    party_power INTEGER NOT NULL,
                    party_json TEXT NOT NULL DEFAULT '[]',
                    started_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    result TEXT NOT NULL DEFAULT '',
                    reward_gold INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_hero_inventory (
                    user_id INTEGER NOT NULL,
                    hero_id TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    item_level INTEGER NOT NULL DEFAULT 1,
                    attack_bonus INTEGER NOT NULL DEFAULT 0,
                    defense_bonus INTEGER NOT NULL DEFAULT 0,
                    hp_bonus INTEGER NOT NULL DEFAULT 0,
                    equipped INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            icols = [r[1] for r in db.execute("PRAGMA table_info(foa_hero_inventory)").fetchall()]
            if "item_level" not in icols:
                db.execute("ALTER TABLE foa_hero_inventory ADD COLUMN item_level INTEGER NOT NULL DEFAULT 1")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_trainings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    hero_id TEXT NOT NULL,
                    arena_level INTEGER NOT NULL DEFAULT 1,
                    xp_gain INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_vendor_stock (
                    user_id INTEGER NOT NULL,
                    slot_idx INTEGER NOT NULL,
                    item_key TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    qty INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, slot_idx)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_battle_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    floor INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    reward_gold INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    
    
    def _foa_seed_heroes(user_id: int) -> None:
        with _foa_connect() as db:
            row = db.execute("SELECT COUNT(*) FROM foa_heroes WHERE user_id = ?", (int(user_id),)).fetchone()
            if int(row[0] or 0) > 0:
                return
            starters = [
                ("h1", "c01", "Aerin", "common"),
            ]
            for hid, hkey, name, rarity in starters:
                atk, dfn, hp = _foa_base_stats_for_rarity(rarity)
                db.execute(
                    """
                    INSERT OR REPLACE INTO foa_heroes
                    (user_id, hero_id, hero_key, hero_name, rarity, power, level, xp, attack, defense, hp, max_hp, is_dead, dead_at, delete_at, in_party, hospital_until, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, 0, '', '', 0, '', CURRENT_TIMESTAMP)
                    """,
                    (int(user_id), hid, hkey, name, rarity, int(atk), int(atk), int(dfn), int(hp), int(hp)),
                )
            db.execute(
                "INSERT OR IGNORE INTO foa_tower (user_id, current_floor, infinity_stones, updated_at) VALUES (?, 1, 0, CURRENT_TIMESTAMP)",
                (int(user_id),),
            )
    
    
    def _foa_cleanup_dead_heroes(user_id: int) -> None:
        now = _foa_now().isoformat()
        with _foa_connect() as db:
            db.execute(
                "DELETE FROM foa_heroes WHERE user_id = ? AND is_dead = 1 AND delete_at <> '' AND delete_at <= ?",
                (int(user_id), now),
            )
    
    
    def _foa_complete_battle_if_due(user_id: int) -> None:
        now_iso = _foa_now().isoformat()
        payout_reward = 0
        payout_ref = ""
        payout_desc = ""
        with _foa_connect() as db:
            row = db.execute(
                """
                SELECT id, floor, enemy_name, enemy_power, enemy_count, difficulty, party_power, party_json, ends_at
                FROM foa_battles
                WHERE user_id = ? AND status = 'active'
                ORDER BY id DESC LIMIT 1
                """,
                (int(user_id),),
            ).fetchone()
            if not row:
                return
            bid, floor, enemy_name, enemy_power, enemy_count, difficulty, party_power, party_json, ends_at = row
            if str(ends_at) > now_iso:
                return
            try:
                party = json.loads(str(party_json or "[]"))
                if not isinstance(party, list):
                    party = []
            except Exception:
                party = []
            ratio = float(party_power) / float(max(1, int(enemy_power)))
            win_chance = max(0.05, min(0.95, 0.35 + (ratio * 0.35)))
            won = random.random() < win_chance
            result = "win" if won else "loss"
            if won:
                ratio_enemy_over_party = float(enemy_power) / float(max(1, int(party_power)))
                reward_scale = max(0.35, min(1.85, ratio_enemy_over_party))
                reward = int(max(5, int(floor) * 25 * reward_scale))
            else:
                reward = 0
            if won:
                db.execute(
                    "UPDATE foa_tower SET current_floor = MIN(?, current_floor + 1), updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (int(FOA_TOWER_MAX_FLOOR), int(user_id)),
                )
                if int(floor) % 5 == 0 and random.random() < FOA_INFINITY_STONE_DROP_CHANCE:
                    db.execute(
                        "UPDATE foa_tower SET infinity_stones = infinity_stones + 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (int(user_id),),
                    )
                if random.random() < min(0.55, 0.15 + (int(floor) * 0.004)):
                    tier = _foa_roll_chest_tier(int(floor))
                    _foa_add_item(db, int(user_id), FOA_CHEST_KEYS[tier], 1)
            if reward > 0:
                payout_reward = int(reward)
                payout_desc = f"foa floor {int(floor)} reward"
                payout_ref = f"foa:reward:{user_id}:{bid}"
            if party:
                dead_pick = random.choice(party)
                dead_id = str(dead_pick.get("hero_id", ""))
                xp_gain = int(max(8, (enemy_power / max(1, len(party))) / 35))
                for p in party:
                    _foa_apply_hero_xp(db, int(user_id), str(p.get("hero_id", "")), xp_gain if won else max(3, xp_gain // 3))
                if dead_id:
                    if not won and random.random() < 0.7:
                        delete_at = (_foa_now() + timedelta(days=7)).isoformat()
                        db.execute(
                            """
                            UPDATE foa_heroes
                            SET hp = 0, is_dead = 1, in_party = 0, dead_at = ?, delete_at = ?, hospital_until = '', updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND hero_id = ?
                            """,
                            (now_iso, delete_at, int(user_id), dead_id),
                        )
                    else:
                        cooldown = (_foa_now() + timedelta(minutes=45)).isoformat()
                        db.execute(
                            """
                            UPDATE foa_heroes
                            SET hp = MAX(1, CAST(max_hp * 0.4 AS INTEGER)), hospital_until = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND hero_id = ? AND is_dead = 0
                            """,
                            (cooldown, int(user_id), dead_id),
                        )
            db.execute(
                "UPDATE foa_battles SET status = 'done', result = ?, reward_gold = ? WHERE id = ?",
                (result, int(reward), int(bid)),
            )
            db.execute(
                "INSERT INTO foa_battle_logs (user_id, floor, result, reward_gold) VALUES (?, ?, ?, ?)",
                (int(user_id), int(floor), result, int(reward)),
            )
        if payout_reward > 0:
            applyledger(int(user_id), int(payout_reward), "foa_tower_reward", payout_desc, payout_ref)
    
    
    def _foa_complete_trainings(user_id: int) -> None:
        now_iso = _foa_now().isoformat()
        with _foa_connect() as db:
            rows = db.execute(
                "SELECT id, hero_id, xp_gain, ends_at FROM foa_trainings WHERE user_id = ? AND status = 'active'",
                (int(user_id),),
            ).fetchall()
            for tid, hero_id, xp_gain, ends_at in rows:
                if str(ends_at or "") <= now_iso:
                    _foa_apply_hero_xp(db, int(user_id), str(hero_id), int(xp_gain or 0))
                    db.execute("UPDATE foa_trainings SET status = 'done' WHERE id = ?", (int(tid),))
    
    
    def _foa_tower_state(user_id: int) -> dict:
        _foa_ensure_recipe_tables()
        _foa_seed_heroes(user_id)
        _foa_cleanup_dead_heroes(user_id)
        _foa_complete_battle_if_due(user_id)
        _foa_complete_trainings(user_id)
        with _foa_connect() as db:
            tr = db.execute(
                "SELECT current_floor, infinity_stones FROM foa_tower WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            hr = db.execute(
                """
                SELECT hero_id, hero_key, hero_name, rarity, power, level, xp, attack, defense, hp, max_hp, is_dead, dead_at, delete_at, in_party, hospital_until
                FROM foa_heroes
                WHERE user_id = ?
                ORDER BY hero_name ASC
                """,
                (int(user_id),),
            ).fetchall()
            inv = db.execute(
                """
                SELECT hero_id, SUM(attack_bonus), SUM(defense_bonus), SUM(hp_bonus)
                FROM foa_hero_inventory
                WHERE user_id = ? AND equipped = 1
                GROUP BY hero_id
                """,
                (int(user_id),),
            ).fetchall()
            hero_items = db.execute(
                """
                SELECT hero_id, item_key, item_name, slot, item_level, attack_bonus, defense_bonus, hp_bonus, equipped
                FROM foa_hero_inventory
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (int(user_id),),
            ).fetchall()
            training_rows = db.execute(
                "SELECT hero_id, xp_gain, started_at, ends_at FROM foa_trainings WHERE user_id = ? AND status = 'active'",
                (int(user_id),),
            ).fetchall()
            depot_rows = db.execute(
                "SELECT item_key, qty FROM foa_items WHERE user_id = ? AND qty > 0 ORDER BY item_key ASC",
                (int(user_id),),
            ).fetchall()
            _foa_refresh_vendor_stock(int(user_id))
            vendor_rows = db.execute(
                """
                SELECT slot_idx, item_key, item_name, price, qty, expires_at
                FROM foa_vendor_stock
                WHERE user_id = ?
                ORDER BY slot_idx ASC
                """,
                (int(user_id),),
            ).fetchall()
            br = db.execute(
                """
                SELECT id, floor, enemy_name, enemy_power, enemy_count, difficulty, party_power, party_json, started_at, ends_at, status
                FROM foa_battles
                WHERE user_id = ? AND status = 'active'
                ORDER BY id DESC LIMIT 1
                """,
                (int(user_id),),
            ).fetchone()
            logs = db.execute(
                "SELECT floor, result, reward_gold, created_at FROM foa_battle_logs WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (int(user_id),),
            ).fetchall()
            mage = db.execute(
                "SELECT level, upgrading_to, upgrade_ends_at FROM foa_buildings WHERE user_id = ? AND building_key = 'mage_tower'",
                (int(user_id),),
            ).fetchone()
        floor = int(tr[0] if tr else 1)
        enemy = _foa_enemy_for_floor(floor)
        heroes = []
        now = _foa_now().isoformat()
        bonus_map = {str(hid): (int(a or 0), int(d or 0), int(h or 0)) for hid, a, d, h in inv}
        hero_item_map: dict[str, list[dict]] = {}
        for hid, ik, nm, slot, ilvl, a, d, h, eq in hero_items:
            key = str(hid)
            hero_item_map.setdefault(key, []).append(
                {
                    "item_key": str(ik),
                    "item_name": str(nm),
                    "slot": str(slot),
                    "item_level": int(ilvl or 1),
                    "attack_bonus": int(a or 0),
                    "defense_bonus": int(d or 0),
                    "hp_bonus": int(h or 0),
                    "equipped": bool(int(eq or 0)),
                }
            )
        training_map = {
            str(hid): {"xp_gain": int(xp or 0), "started_at": str(st or ""), "ends_at": str(et or "")}
            for hid, xp, st, et in training_rows
        }
        for h in hr:
            hid, hero_key, name, rarity, power, level, xp, attack, defense, hp, max_hp, is_dead, dead_at, delete_at, in_party, hospital_until = h
            b_atk, b_def, b_hp = bonus_map.get(str(hid), (0, 0, 0))
            hospital_block = str(hospital_until or "") > now
            total_attack = int(attack) + b_atk
            total_defense = int(defense) + b_def
            total_max_hp = int(max_hp) + b_hp
            total_hp = min(total_max_hp, int(hp) + b_hp)
            heroes.append(
                {
                    "hero_id": str(hid),
                    "hero_key": str(hero_key or ""),
                    "hero_name": str(name),
                    "rarity": str(rarity or "common"),
                    "power": int(power),
                    "level": int(level),
                    "xp": int(xp),
                    "next_level_xp": int(_foa_xp_to_next(level)),
                    "attack": int(attack),
                    "defense": int(defense),
                    "equipment_bonus": {"attack": int(b_atk), "defense": int(b_def), "hp": int(b_hp)},
                    "total_attack": int(total_attack),
                    "total_defense": int(total_defense),
                    "hp": int(hp),
                    "max_hp": int(max_hp),
                    "total_hp": int(total_hp),
                    "total_max_hp": int(total_max_hp),
                    "is_dead": bool(int(is_dead)),
                    "dead_at": str(dead_at or ""),
                    "delete_at": str(delete_at or ""),
                    "in_party": bool(int(in_party)),
                    "hospital_until": str(hospital_until or ""),
                    "hospital_block": hospital_block,
                    "inventory": hero_item_map.get(str(hid), []),
                    "training": training_map.get(str(hid)),
                }
            )
        active = None
        if br:
            bid, bf, ename, ep, ec, diff, pp, party_json, started_at, ends_at, _ = br
            try:
                party = json.loads(str(party_json or "[]"))
                if not isinstance(party, list):
                    party = []
            except Exception:
                party = []
            prog = _foa_progress(str(started_at), str(ends_at))
            rem = max(0, int((datetime.fromisoformat(str(ends_at)) - _foa_now()).total_seconds()))
            active = {
                "id": int(bid),
                "floor": int(bf),
                "enemy_name": str(ename),
                "enemy_power": int(ep),
                "enemy_count": int(ec),
                "difficulty": str(diff),
                "party_power": int(pp),
                "party": party,
                "started_at": str(started_at),
                "ends_at": str(ends_at),
                "remaining_sec": rem,
                "progress": prog,
            }
        return {
            "balance": _foa_safe_balance(int(user_id)),
            "floor": floor,
            "max_floor": FOA_TOWER_MAX_FLOOR,
            "enemy": enemy,
            "infinity_stones": int(tr[1] if tr else 0),
            "heroes": heroes,
            "active_battle": active,
            "battle_logs": [{"floor": int(f), "result": str(r), "reward_gold": int(g), "created_at": str(c)} for f, r, g, c in logs],
            "depot_items": [{"item_key": str(k), "item_name": _foa_item_display_name(str(k)), "qty": int(q)} for k, q in depot_rows],
            "vendor_stock": [
                {
                    "slot_idx": int(s),
                    "item_key": str(k),
                    "item_name": str(n),
                    "price": int(p),
                    "qty": int(q),
                    "expires_at": str(e),
                }
                for s, k, n, p, q, e in vendor_rows
            ],
            "summon": {"single_cost": FOA_SUMMON_COST_SINGLE, "ten_cost": FOA_SUMMON_COST_TEN},
            "mage_tower": {
                "built": bool(mage and int(mage[0] or 0) > 0),
                "level": int(mage[0] if mage else 0),
                "ready": bool(mage and int(mage[0] or 0) > 0 and not (int(mage[1] or 0) > 0 and str(mage[2] or "") > _foa_now().isoformat())),
            },
        }
    
    
    def _foa_ensure_layout_table() -> None:
        with _foa_connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_layouts (
                    user_id INTEGER NOT NULL,
                    device TEXT NOT NULL,
                    layout_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, device)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS foa_layout_defaults (
                    device TEXT PRIMARY KEY,
                    layout_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    
    
    def _foa_now() -> datetime:
        return datetime.now(timezone.utc)
    
    
    def _foa_upgrade_minutes(level_from: int) -> int:
        lo, hi = FOA_UPGRADE_MINUTES.get(int(level_from), (5, 10))
        return random.randint(int(lo), int(hi))
    
    
    def _foa_safe_balance(user_id: int, retries: int = 3) -> int:
        for i in range(max(1, int(retries))):
            try:
                return int(get_balance(int(user_id)))
            except sqlite3.OperationalError:
                if i + 1 >= retries:
                    break
                time.sleep(0.05 * (i + 1))
        return 0
    
    
    def _foa_finish_due_upgrades(user_id: int) -> None:
        now_iso = _foa_now().isoformat()
        with _foa_connect() as db:
            rows = db.execute(
                """
                SELECT card_id, upgrading_to, upgrade_ends_at
                FROM foa_buildings
                WHERE user_id = ? AND upgrading_to > 0 AND upgrade_ends_at <> ''
                """,
                (int(user_id),),
            ).fetchall()
            for card_id, upgrading_to, ends_at in rows:
                if str(ends_at) <= now_iso:
                    db.execute(
                        """
                        UPDATE foa_buildings
                        SET level = ?, upgrading_to = 0, upgrade_started_at = '', upgrade_ends_at = '', updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND card_id = ?
                        """,
                        (int(upgrading_to), int(user_id), str(card_id)),
                    )
    
    
    def _foa_rows(user_id: int):
        with _foa_connect() as db:
            return db.execute(
                """
                SELECT card_id, building_key, level, base_cost, upgrading_to, upgrade_started_at, upgrade_ends_at
                FROM foa_buildings
                WHERE user_id = ?
                ORDER BY card_id ASC
                """,
                (int(user_id),),
            ).fetchall()
    
    
    def _foa_operation_cost(level: int, base_cost: int) -> int:
        level = int(level)
        base_cost = int(base_cost)
        if level <= 0:
            return base_cost
        return base_cost * (2 ** max(0, level - 1))
    
    
    def _foa_progress(start_iso: str, end_iso: str) -> float:
        try:
            s = datetime.fromisoformat(str(start_iso))
            e = datetime.fromisoformat(str(end_iso))
            n = _foa_now()
            total = max(1.0, (e - s).total_seconds())
            done = max(0.0, min(total, (n - s).total_seconds()))
            return max(0.0, min(1.0, done / total))
        except Exception:
            return 0.0
    
    
    def _foa_recipe_state(user_id: int, rows) -> tuple[list[dict], list[dict]]:
        levels = {}
        for _, building_key, level, *_ in rows:
            levels[str(building_key)] = max(levels.get(str(building_key), 0), int(level))
        with _foa_connect() as db:
            owned_rows = db.execute(
                "SELECT recipe_key FROM foa_recipe_owns WHERE user_id = ?",
                (int(user_id),),
            ).fetchall()
            inv_rows = db.execute(
                "SELECT item_key, qty FROM foa_items WHERE user_id = ? AND qty > 0",
                (int(user_id),),
            ).fetchall()
        owned = {str(r[0]) for r in owned_rows}
        recipes = []
        for key, meta in FOA_RECIPES.items():
            bkey = str(meta["building_key"])
            blevel = int(levels.get(bkey, 0))
            recipes.append(
                {
                    "key": key,
                    "name": meta["name"],
                    "building_key": bkey,
                    "building_level": blevel,
                    "min_level": int(meta["min_level"]),
                    "recipe_cost": int(meta["recipe_cost"]),
                    "craft_cost": int(meta["craft_cost"]),
                    "unlocked": blevel >= int(meta["min_level"]),
                    "owned": key in owned,
                }
            )
        inventory = [{"item_key": str(k), "qty": int(q)} for k, q in inv_rows]
        return recipes, inventory
    
    
    def _foa_normalize_card_ids(user_id: int) -> None:
        # Legacy IDs (g1, g2, 1, 2...) are migrated to shared slot IDs for PC/mobile parity.
        with _foa_connect() as db:
            rows = db.execute(
                "SELECT card_id FROM foa_buildings WHERE user_id = ?",
                (int(user_id),),
            ).fetchall()
            used = {str(r[0]) for r in rows}
            for (card_id_raw,) in rows:
                card_id = str(card_id_raw or "")
                if card_id.startswith("slot-"):
                    continue
                slot = None
                if card_id.startswith("g") and card_id[1:].isdigit():
                    slot = int(card_id[1:])
                elif card_id.isdigit():
                    slot = int(card_id)
                if not slot or slot <= 0:
                    continue
                target = f"slot-{slot}"
                if target in used and target != card_id:
                    continue
                db.execute(
                    "UPDATE foa_buildings SET card_id = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND card_id = ?",
                    (target, int(user_id), card_id),
                )
                used.discard(card_id)
                used.add(target)
    
    
    def _foa_depot_summary(rows) -> dict:
        best_level = 0
        for _, building_key, level, *_ in rows:
            if str(building_key) == "depot":
                best_level = max(best_level, int(level))
        if best_level <= 0:
            return {"built": False, "level": 0, "capacity": 0}
        return {"built": True, "level": best_level, "capacity": best_level * 100}


    def _foa_content() -> dict:
        lang = userlanguage() or "en"
        return texts(lang)


    def _foa_text(content: dict, key: str, fallback: str) -> str:
        if key:
            val = content.get(key, fallback)
            if isinstance(val, str) and val.strip():
                return val
        return fallback
    
    
    def _foa_state_payload(user_id: int) -> dict:
        _foa_normalize_card_ids(user_id)
        _foa_finish_due_upgrades(user_id)
        _foa_ensure_recipe_tables()
        rows = _foa_rows(user_id)
        content = _foa_content()
        now_iso = _foa_now().isoformat()
        out = []
        for card_id, building_key, level, base_cost, upgrading_to, upgrade_started_at, upgrade_ends_at in rows:
            meta = FOA_BUILDINGS.get(str(building_key), {})
            level = int(level)
            base_cost = int(base_cost)
            upgrading_to = int(upgrading_to or 0)
            next_upgrade_cost = _foa_operation_cost(level, base_cost)
            is_upgrading = upgrading_to > 0 and str(upgrade_ends_at or "") > now_iso
            progress = _foa_progress(str(upgrade_started_at or ""), str(upgrade_ends_at or "")) if is_upgrading else 0.0
            quick_finish_cost = (_foa_operation_cost(level, base_cost) * 3) if is_upgrading else 0
            out.append(
                {
                    "card_id": str(card_id),
                    "building_key": str(building_key),
                    "building_name": _foa_text(content, str(meta.get("name_key", "")), str(meta.get("name", str(building_key)))),
                    "visual": FOA_BUILDING_VISUALS.get(str(building_key), {}),
                    "level": level,
                    "max_level": FOA_MAX_LEVEL,
                    "base_cost": base_cost,
                    "next_upgrade_cost": next_upgrade_cost,
                    "upgrading_to": upgrading_to,
                    "upgrade_started_at": str(upgrade_started_at or ""),
                    "upgrade_ends_at": str(upgrade_ends_at or ""),
                    "is_upgrading": is_upgrading,
                    "progress": progress,
                    "quick_finish_cost": int(quick_finish_cost),
                }
            )
        recipes, inventory = _foa_recipe_state(user_id, rows)
        return {
            "ok": True,
            "balance": _foa_safe_balance(int(user_id)),
            "max_level": FOA_MAX_LEVEL,
            "buildings": out,
            "building_defs": [
                {
                    "key": key,
                    "name": _foa_text(content, str(meta.get("name_key", "")), str(meta.get("name", key))),
                    "desc": _foa_text(content, str(meta.get("desc_key", "")), str(meta.get("desc", ""))),
                }
                for key, meta in FOA_BUILDINGS.items()
            ],
            "depot": _foa_depot_summary(rows),
            "recipes": recipes,
            "inventory": inventory,
            "now": now_iso,
        }
    
    
    @app.route("/api/fear-of-abyss/state")
    def fearofabyssstate():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/layout")
    def fearofabysslayoutget():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        _foa_ensure_layout_table()
        device = str(request.args.get("device", "pc") or "pc").strip().lower()
        if device not in {"pc", "mobile"}:
            return {"ok": False, "error": "invalid_device"}, 400
        with _foa_connect() as db:
            row = db.execute(
                "SELECT layout_json, updated_at FROM foa_layouts WHERE user_id = ? AND device = ?",
                (int(me[0]), device),
            ).fetchone()
            if not row:
                row = db.execute(
                    "SELECT layout_json, updated_at FROM foa_layout_defaults WHERE device = ?",
                    (device,),
                ).fetchone()
        if not row:
            return {"ok": True, "device": device, "items": [], "updated_at": "", "source": "none"}
        try:
            items = json.loads(str(row[0] or "[]"))
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        return {"ok": True, "device": device, "items": items, "updated_at": str(row[1] or ""), "source": "db"}
    
    
    @app.route("/api/fear-of-abyss/layout", methods=["POST"])
    def fearofabysslayoutset():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        _foa_ensure_layout_table()
        payload = request.get_json(silent=True) or {}
        device = str(payload.get("device", "pc") or "pc").strip().lower()
        if device not in {"pc", "mobile"}:
            return {"ok": False, "error": "invalid_device"}, 400
        items = payload.get("items", [])
        if not isinstance(items, list):
            return {"ok": False, "error": "invalid_items"}, 400
        trimmed = []
        for it in items[:200]:
            if not isinstance(it, dict):
                continue
            trimmed.append(
                {
                    "id": str(it.get("id", ""))[:64],
                    "x": float(it.get("x", 0) or 0),
                    "y": float(it.get("y", 0) or 0),
                    "w": float(it.get("w", 0.2) or 0.2),
                    "h": float(it.get("h", 0.12) or 0.12),
                }
            )
        with _foa_connect() as db:
            db.execute(
                """
                INSERT INTO foa_layouts (user_id, device, layout_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, device)
                DO UPDATE SET layout_json = excluded.layout_json, updated_at = CURRENT_TIMESTAMP
                """,
                (int(me[0]), device, json.dumps(trimmed, ensure_ascii=True)),
            )
            if bool(payload.get("set_default", False)):
                db.execute(
                    """
                    INSERT INTO foa_layout_defaults (device, layout_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(device)
                    DO UPDATE SET layout_json = excluded.layout_json, updated_at = CURRENT_TIMESTAMP
                    """,
                    (device, json.dumps(trimmed, ensure_ascii=True)),
                )
        return {"ok": True, "device": device, "saved": len(trimmed)}
    
    
    @app.route("/api/fear-of-abyss/build", methods=["POST"])
    def fearofabyssbuild():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        payload = request.get_json(silent=True) or {}
        card_id = str(payload.get("card_id", "")).strip()
        building_key = str(payload.get("building_key", "")).strip()
        if not card_id:
            return {"ok": False, "error": "missing_card_id"}, 400
        if building_key not in FOA_BUILDINGS:
            return {"ok": False, "error": "invalid_building_key"}, 400
    
        with _foa_connect() as db:
            same_building = db.execute(
                "SELECT card_id FROM foa_buildings WHERE user_id = ? AND building_key = ?",
                (int(me[0]), building_key),
            ).fetchone()
            if same_building:
                return {"ok": False, "error": "building_already_exists", **_foa_state_payload(me[0])}, 400
            existing = db.execute(
                "SELECT building_key FROM foa_buildings WHERE user_id = ? AND card_id = ?",
                (int(me[0]), card_id),
            ).fetchone()
            if existing:
                return {"ok": False, "error": "card_already_built", **_foa_state_payload(me[0])}, 400
    
        base_cost = random.randint(100, 200)
        ref = f"foa:build:{me[0]}:{card_id}:{int(time.time() * 1000)}"
        ok = spend_gold(int(me[0]), int(base_cost), f"foa build {building_key}", reference_id=ref, tx_type="foa_build")
        if not ok:
            return {"ok": False, "error": "insufficient_balance", **_foa_state_payload(me[0])}, 400
    
        minutes = _foa_upgrade_minutes(1)
        start_at = _foa_now().isoformat()
        ends_at = (_foa_now() + timedelta(minutes=minutes)).isoformat()
        with _foa_connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO foa_buildings (user_id, card_id, building_key, level, base_cost, upgrading_to, upgrade_started_at, upgrade_ends_at, updated_at)
                VALUES (?, ?, ?, 0, ?, 1, ?, ?, CURRENT_TIMESTAMP)
                """,
                (int(me[0]), card_id, building_key, int(base_cost), start_at, ends_at),
            )
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/upgrade", methods=["POST"])
    def fearofabyssupgrade():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        _foa_finish_due_upgrades(me[0])
        payload = request.get_json(silent=True) or {}
        card_id = str(payload.get("card_id", "")).strip()
        if not card_id:
            return {"ok": False, "error": "missing_card_id"}, 400
    
        with _foa_connect() as db:
            row = db.execute(
                """
                SELECT building_key, level, base_cost, upgrading_to, upgrade_ends_at
                FROM foa_buildings
                WHERE user_id = ? AND card_id = ?
                """,
                (int(me[0]), card_id),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "building_not_found", **_foa_state_payload(me[0])}, 404
    
        building_key, level, base_cost, upgrading_to, upgrade_ends_at = row
        level = int(level)
        base_cost = int(base_cost)
        upgrading_to = int(upgrading_to or 0)
        if upgrading_to > 0 and str(upgrade_ends_at or "") > _foa_now().isoformat():
            return {"ok": False, "error": "already_upgrading", **_foa_state_payload(me[0])}, 400
        if level >= FOA_MAX_LEVEL:
            return {"ok": False, "error": "max_level", **_foa_state_payload(me[0])}, 400
    
        target_level = level + 1
        cost = _foa_operation_cost(level, base_cost)
        ref = f"foa:upgrade:{me[0]}:{card_id}:{target_level}:{int(time.time() * 1000)}"
        ok = spend_gold(int(me[0]), int(cost), f"foa upgrade {building_key} to {target_level}", reference_id=ref, tx_type="foa_upgrade")
        if not ok:
            return {"ok": False, "error": "insufficient_balance", **_foa_state_payload(me[0])}, 400
    
        minutes = _foa_upgrade_minutes(level)
        start_at = _foa_now().isoformat()
        ends_at = (_foa_now() + timedelta(minutes=minutes)).isoformat()
        with _foa_connect() as db:
            db.execute(
                """
                UPDATE foa_buildings
                SET upgrading_to = ?, upgrade_started_at = ?, upgrade_ends_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND card_id = ?
                """,
                (int(target_level), start_at, ends_at, int(me[0]), card_id),
            )
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/finish-now", methods=["POST"])
    def fearofabyssfinishnow():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        payload = request.get_json(silent=True) or {}
        card_id = str(payload.get("card_id", "")).strip()
        if not card_id:
            return {"ok": False, "error": "missing_card_id"}, 400
        with _foa_connect() as db:
            row = db.execute(
                "SELECT building_key, level, base_cost, upgrading_to, upgrade_ends_at FROM foa_buildings WHERE user_id = ? AND card_id = ?",
                (int(me[0]), card_id),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "building_not_found", **_foa_state_payload(me[0])}, 404
        building_key, level, base_cost, upgrading_to, upgrade_ends_at = row
        level = int(level)
        base_cost = int(base_cost)
        upgrading_to = int(upgrading_to or 0)
        if upgrading_to <= 0 or str(upgrade_ends_at or "") <= _foa_now().isoformat():
            return {"ok": False, "error": "not_in_progress", **_foa_state_payload(me[0])}, 400
        instant_cost = _foa_operation_cost(level, base_cost) * 3
        ref = f"foa:finishnow:{me[0]}:{card_id}:{upgrading_to}:{int(time.time() * 1000)}"
        ok = spend_gold(int(me[0]), int(instant_cost), f"foa instant finish {building_key}", reference_id=ref, tx_type="foa_finish_now")
        if not ok:
            return {"ok": False, "error": "insufficient_balance", **_foa_state_payload(me[0])}, 400
        with _foa_connect() as db:
            db.execute(
                """
                UPDATE foa_buildings
                SET level = ?, upgrading_to = 0, upgrade_started_at = '', upgrade_ends_at = '', updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND card_id = ?
                """,
                (int(upgrading_to), int(me[0]), card_id),
            )
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/recipe/buy", methods=["POST"])
    def fearofabyssrecipebuy():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        _foa_ensure_recipe_tables()
        payload = request.get_json(silent=True) or {}
        recipe_key = str(payload.get("recipe_key", "")).strip()
        meta = FOA_RECIPES.get(recipe_key)
        if not meta:
            return {"ok": False, "error": "invalid_recipe", **_foa_state_payload(me[0])}, 400
        rows = _foa_rows(me[0])
        levels = {str(r[1]): int(r[2]) for r in rows}
        if levels.get(str(meta["building_key"]), 0) < int(meta["min_level"]):
            return {"ok": False, "error": "recipe_locked", **_foa_state_payload(me[0])}, 400
        with _foa_connect() as db:
            owned = db.execute(
                "SELECT 1 FROM foa_recipe_owns WHERE user_id = ? AND recipe_key = ?",
                (int(me[0]), recipe_key),
            ).fetchone()
        if owned:
            return {"ok": False, "error": "already_owned", **_foa_state_payload(me[0])}, 400
        ref = f"foa:recipebuy:{me[0]}:{recipe_key}:{int(time.time() * 1000)}"
        ok = spend_gold(int(me[0]), int(meta["recipe_cost"]), f"foa recipe buy {recipe_key}", reference_id=ref, tx_type="foa_recipe_buy")
        if not ok:
            return {"ok": False, "error": "insufficient_balance", **_foa_state_payload(me[0])}, 400
        with _foa_connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO foa_recipe_owns (user_id, recipe_key) VALUES (?, ?)",
                (int(me[0]), recipe_key),
            )
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/craft", methods=["POST"])
    def fearofabysscraft():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        _foa_ensure_recipe_tables()
        payload = request.get_json(silent=True) or {}
        recipe_key = str(payload.get("recipe_key", "")).strip()
        qty = max(1, min(999, int(payload.get("qty", 1) or 1)))
        meta = FOA_RECIPES.get(recipe_key)
        if not meta:
            return {"ok": False, "error": "invalid_recipe", **_foa_state_payload(me[0])}, 400
        rows = _foa_rows(me[0])
        levels = {str(r[1]): int(r[2]) for r in rows}
        if levels.get(str(meta["building_key"]), 0) < int(meta["min_level"]):
            return {"ok": False, "error": "recipe_locked", **_foa_state_payload(me[0])}, 400
        with _foa_connect() as db:
            owned = db.execute(
                "SELECT 1 FROM foa_recipe_owns WHERE user_id = ? AND recipe_key = ?",
                (int(me[0]), recipe_key),
            ).fetchone()
        if not owned:
            return {"ok": False, "error": "recipe_not_owned", **_foa_state_payload(me[0])}, 400
        total_cost = int(meta["craft_cost"]) * int(qty)
        ref = f"foa:craft:{me[0]}:{recipe_key}:{qty}:{int(time.time() * 1000)}"
        ok = spend_gold(int(me[0]), total_cost, f"foa craft {recipe_key} x{qty}", reference_id=ref, tx_type="foa_craft")
        if not ok:
            return {"ok": False, "error": "insufficient_balance", **_foa_state_payload(me[0])}, 400
        with _foa_connect() as db:
            db.execute(
                """
                INSERT INTO foa_items (user_id, item_key, qty, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, item_key)
                DO UPDATE SET qty = foa_items.qty + excluded.qty, updated_at = CURRENT_TIMESTAMP
                """,
                (int(me[0]), recipe_key, int(qty)),
            )
        return _foa_state_payload(me[0])
    
    
    @app.route("/api/fear-of-abyss/tower/state")
    def fearofabysstowerstate():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        tower = _foa_tower_state(me[0])
        return {"ok": True, **tower}
    
    
    @app.route("/api/fear-of-abyss/tower/toggle_party", methods=["POST"])
    def fearofabysstoggletowerparty():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        if not hero_id:
            return {"ok": False, "error": "missing_hero_id"}, 400
        _foa_ensure_recipe_tables()
        _foa_seed_heroes(me[0])
        now = _foa_now().isoformat()
        with _foa_connect() as db:
            row = db.execute(
                "SELECT is_dead, in_party, hospital_until FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
                (int(me[0]), hero_id),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "hero_not_found"}, 404
            is_dead, in_party, hospital_until = row
            if int(is_dead) == 1:
                return {"ok": False, "error": "hero_dead", **_foa_tower_state(me[0])}, 400
            if str(hospital_until or "") > now:
                return {"ok": False, "error": "hero_hospital", **_foa_tower_state(me[0])}, 400
            db.execute(
                "UPDATE foa_heroes SET in_party = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND hero_id = ?",
                (0 if int(in_party) else 1, int(me[0]), hero_id),
            )
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/tower/start_battle", methods=["POST"])
    def fearofabysstowerstartbattle():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        _foa_ensure_recipe_tables()
        _foa_seed_heroes(me[0])
        now = _foa_now()
        now_iso = now.isoformat()
        with _foa_connect() as db:
            active = db.execute(
                "SELECT id FROM foa_battles WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (int(me[0]),),
            ).fetchone()
            if active:
                return {"ok": False, "error": "battle_already_active", **_foa_tower_state(me[0])}, 400
            tr = db.execute("SELECT current_floor FROM foa_tower WHERE user_id = ?", (int(me[0]),)).fetchone()
            floor = int(tr[0] if tr else 1)
            heroes = db.execute(
                """
                SELECT hero_id, hero_name, attack, defense, hp, max_hp, is_dead, hospital_until
                FROM foa_heroes
                WHERE user_id = ? AND in_party = 1
                """,
                (int(me[0]),),
            ).fetchall()
            inv = db.execute(
                """
                SELECT hero_id, SUM(attack_bonus), SUM(defense_bonus), SUM(hp_bonus)
                FROM foa_hero_inventory
                WHERE user_id = ? AND equipped = 1
                GROUP BY hero_id
                """,
                (int(me[0]),),
            ).fetchall()
            if not heroes:
                return {"ok": False, "error": "empty_party", **_foa_tower_state(me[0])}, 400
            bonus_map = {str(hid): (int(a or 0), int(d or 0), int(h or 0)) for hid, a, d, h in inv}
            party = []
            party_power = 0
            for hid, name, attack, defense, hp, max_hp, is_dead, hospital_until in heroes:
                if int(is_dead) == 1:
                    return {"ok": False, "error": "party_has_dead", **_foa_tower_state(me[0])}, 400
                if str(hospital_until or "") > now_iso:
                    return {"ok": False, "error": "hospital_cooldown", **_foa_tower_state(me[0])}, 400
                b_atk, b_def, b_hp = bonus_map.get(str(hid), (0, 0, 0))
                t_atk = int(attack) + b_atk
                t_def = int(defense) + b_def
                t_max_hp = int(max_hp) + b_hp
                t_hp = min(t_max_hp, int(hp) + b_hp)
                party_power += t_atk + t_def + int(max(0, t_hp))
                party.append(
                    {
                        "hero_id": str(hid),
                        "hero_name": str(name),
                        "hp": int(t_hp),
                        "max_hp": int(t_max_hp),
                        "attack": int(t_atk),
                        "defense": int(t_def),
                        "is_dead": False,
                    }
                )
            enemy = _foa_enemy_for_floor(floor)
            diff = _foa_difficulty(party_power, int(enemy["enemy_power"]))
            dur = _foa_battle_duration_sec(diff)
            ends = (now + timedelta(seconds=dur)).isoformat()
            db.execute(
                """
                INSERT INTO foa_battles
                (user_id, floor, enemy_name, enemy_power, enemy_count, difficulty, party_power, party_json, started_at, ends_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    int(me[0]),
                    int(floor),
                    str(enemy["enemy_name"]),
                    int(enemy["enemy_power"]),
                    int(enemy["enemy_count"]),
                    diff,
                    int(party_power),
                    json.dumps(party, ensure_ascii=True),
                    now_iso,
                    ends,
                ),
            )
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/hero/delete", methods=["POST"])
    def fearofabyssherodelete():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        if not hero_id:
            return {"ok": False, "error": "missing_hero_id"}, 400
        with _foa_connect() as db:
            row = db.execute(
                "SELECT is_dead FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
                (int(me[0]), hero_id),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "hero_not_found"}, 404
            if int(row[0]) != 1:
                return {"ok": False, "error": "hero_not_dead", **_foa_tower_state(me[0])}, 400
            db.execute("DELETE FROM foa_heroes WHERE user_id = ? AND hero_id = ?", (int(me[0]), hero_id))
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/hero/summon", methods=["POST"])
    def fearofabyssherosummon():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        initialize_user_economy(me[0])
        _foa_ensure_table()
        _foa_ensure_recipe_tables()
        payload = request.get_json(silent=True) or {}
        count = 10 if int(payload.get("count", 1) or 1) >= 10 else 1
        with _foa_connect() as db:
            mage = db.execute(
                "SELECT level, upgrading_to, upgrade_ends_at FROM foa_buildings WHERE user_id = ? AND building_key = 'mage_tower'",
                (int(me[0]),),
            ).fetchone()
        if not mage:
            return {"ok": False, "error": "mage_tower_required", **_foa_tower_state(me[0])}, 400
        m_level, m_up, m_end = int(mage[0] or 0), int(mage[1] or 0), str(mage[2] or "")
        if m_level <= 0 or (m_up > 0 and m_end > _foa_now().isoformat()):
            return {"ok": False, "error": "mage_tower_not_ready", **_foa_tower_state(me[0])}, 400
        cost = FOA_SUMMON_COST_TEN if count == 10 else FOA_SUMMON_COST_SINGLE
        ref = f"foa:summon:{me[0]}:{count}:{int(time.time() * 1000)}"
        if not spend_gold(int(me[0]), int(cost), f"foa summon x{count}", reference_id=ref, tx_type="foa_summon"):
            return {"ok": False, "error": "insufficient_balance", **_foa_tower_state(me[0])}, 400
    
        results = []
        with _foa_connect() as db:
            for i in range(count):
                tpl = _foa_pick_hero_template(m_level)
                existing = db.execute(
                    "SELECT hero_id FROM foa_heroes WHERE user_id = ? AND hero_key = ?",
                    (int(me[0]), str(tpl["key"])),
                ).fetchone()
                if existing:
                    hid = str(existing[0])
                    xp_gain = 65 if count == 1 else 85
                    _foa_apply_hero_xp(db, int(me[0]), hid, xp_gain)
                    results.append({"hero_key": tpl["key"], "hero_name": tpl["name"], "rarity": tpl["rarity"], "duplicate": True, "xp_gain": xp_gain})
                    continue
                atk, dfn, hp = _foa_base_stats_for_rarity(str(tpl["rarity"]))
                hid = f"h{int(time.time() * 1000)}_{i}_{random.randint(100, 999)}"
                db.execute(
                    """
                    INSERT INTO foa_heroes
                    (user_id, hero_id, hero_key, hero_name, rarity, power, level, xp, attack, defense, hp, max_hp, is_dead, dead_at, delete_at, in_party, hospital_until, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, 0, '', '', 0, '', CURRENT_TIMESTAMP)
                    """,
                    (int(me[0]), hid, str(tpl["key"]), str(tpl["name"]), str(tpl["rarity"]), int(atk), int(atk), int(dfn), int(hp), int(hp)),
                )
                results.append({"hero_key": tpl["key"], "hero_name": tpl["name"], "rarity": tpl["rarity"], "duplicate": False, "xp_gain": 0})
        return {"ok": True, "results": results, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/hero/equip_best", methods=["POST"])
    def fearofabyssheroequipbest():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        if not hero_id:
            return {"ok": False, "error": "missing_hero_id"}, 400
        with _foa_connect() as db:
            h = db.execute(
                "SELECT is_dead FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
                (int(me[0]), hero_id),
            ).fetchone()
            if not h:
                return {"ok": False, "error": "hero_not_found"}, 404
            if int(h[0]) == 1:
                return {"ok": False, "error": "hero_dead", **_foa_tower_state(me[0])}, 400
    
            for slot in ("weapon", "armor"):
                best_key = None
                best_score = -1
                for key, meta in FOA_EQUIP_DEFS.items():
                    if meta["slot"] != slot:
                        continue
                    row = db.execute(
                        "SELECT qty FROM foa_items WHERE user_id = ? AND item_key = ?",
                        (int(me[0]), key),
                    ).fetchone()
                    if not row or int(row[0] or 0) <= 0:
                        continue
                    score = int(meta["attack"]) * 3 + int(meta["defense"]) * 2 + int(meta["hp"])
                    if score > best_score:
                        best_score = score
                        best_key = key
                if not best_key:
                    continue
                meta = FOA_EQUIP_DEFS[best_key]
                db.execute(
                    "DELETE FROM foa_hero_inventory WHERE user_id = ? AND hero_id = ? AND slot = ?",
                    (int(me[0]), hero_id, slot),
                )
                db.execute(
                    """
                    INSERT INTO foa_hero_inventory
                    (user_id, hero_id, item_key, item_name, slot, attack_bonus, defense_bonus, hp_bonus, equipped)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (int(me[0]), hero_id, best_key, meta["name"], slot, int(meta["attack"]), int(meta["defense"]), int(meta["hp"])),
                )
                db.execute(
                    "UPDATE foa_items SET qty = qty - 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_key = ? AND qty > 0",
                    (int(me[0]), best_key),
                )
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/hero/train", methods=["POST"])
    def fearofabyssherotrain():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        minutes = max(5, min(240, int(payload.get("minutes", 20) or 20)))
        if not hero_id:
            return {"ok": False, "error": "missing_hero_id"}, 400
        with _foa_connect() as db:
            arena = db.execute(
                "SELECT level, upgrading_to, upgrade_ends_at FROM foa_buildings WHERE user_id = ? AND building_key = 'training_arena'",
                (int(me[0]),),
            ).fetchone()
            if not arena or int(arena[0] or 0) <= 0:
                return {"ok": False, "error": "training_arena_required", **_foa_tower_state(me[0])}, 400
            if int(arena[1] or 0) > 0 and str(arena[2] or "") > _foa_now().isoformat():
                return {"ok": False, "error": "training_arena_not_ready", **_foa_tower_state(me[0])}, 400
            h = db.execute(
                "SELECT is_dead, hospital_until FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
                (int(me[0]), hero_id),
            ).fetchone()
            if not h:
                return {"ok": False, "error": "hero_not_found"}, 404
            if int(h[0] or 0) == 1:
                return {"ok": False, "error": "hero_dead", **_foa_tower_state(me[0])}, 400
            if str(h[1] or "") > _foa_now().isoformat():
                return {"ok": False, "error": "hospital_cooldown", **_foa_tower_state(me[0])}, 400
            active_count = db.execute(
                "SELECT COUNT(*) FROM foa_trainings WHERE user_id = ? AND status = 'active'",
                (int(me[0]),),
            ).fetchone()
            cap = max(1, int(arena[0] or 1))
            if int(active_count[0] or 0) >= cap:
                return {"ok": False, "error": "training_capacity_full", **_foa_tower_state(me[0])}, 400
            exists = db.execute(
                "SELECT id FROM foa_trainings WHERE user_id = ? AND hero_id = ? AND status = 'active'",
                (int(me[0]), hero_id),
            ).fetchone()
            if exists:
                return {"ok": False, "error": "hero_already_training", **_foa_tower_state(me[0])}, 400
            arena_level = int(arena[0] or 1)
            xp_gain = int(minutes * (8 + arena_level * 3))
            started = _foa_now().isoformat()
            ends = (_foa_now() + timedelta(minutes=minutes)).isoformat()
            db.execute(
                """
                INSERT INTO foa_trainings (user_id, hero_id, arena_level, xp_gain, started_at, ends_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (int(me[0]), hero_id, arena_level, int(xp_gain), started, ends),
            )
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/depot/open_chest", methods=["POST"])
    def fearofabyssdepotopenchest():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        tier = str(payload.get("tier", "")).strip().lower()
        amount = max(1, min(999, int(payload.get("amount", 1) or 1)))
        if tier not in FOA_CHEST_TIERS:
            return {"ok": False, "error": "invalid_tier"}, 400
        chest_key = FOA_CHEST_KEYS[tier]
        with _foa_connect() as db:
            row = db.execute(
                "SELECT qty FROM foa_items WHERE user_id = ? AND item_key = ?",
                (int(me[0]), chest_key),
            ).fetchone()
            have = int(row[0] or 0) if row else 0
            if have <= 0:
                return {"ok": False, "error": "no_chest", **_foa_tower_state(me[0])}, 400
            amount = min(amount, have)
            db.execute(
                "UPDATE foa_items SET qty = qty - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_key = ?",
                (int(amount), int(me[0]), chest_key),
            )
            rewards = {}
            gold_total = 0
            for _ in range(amount):
                loot = _foa_roll_chest_loot(tier)
                k = str(loot["item_key"])
                q = int(loot["qty"])
                rewards[k] = rewards.get(k, 0) + q
                if k == "gold":
                    gold_total += q
                else:
                    _foa_add_item(db, int(me[0]), k, q)
        if gold_total > 0:
            applyledger(int(me[0]), int(gold_total), "foa_chest_open", f"foa chest {tier} open", f"foa:chest:{me[0]}:{int(time.time() * 1000)}")
        reward_list = [{"item_key": k, "item_name": _foa_item_display_name(k), "qty": int(v)} for k, v in rewards.items()]
        return {"ok": True, "opened": int(amount), "tier": tier, "rewards": reward_list, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/vendor/state")
    def fearofabyssvendorstate():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        t = _foa_tower_state(me[0])
        return {"ok": True, "vendor_stock": t.get("vendor_stock", []), "balance": t.get("balance", 0)}
    
    
    @app.route("/api/fear-of-abyss/vendor/buy", methods=["POST"])
    def fearofabyssvendorbuy():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        slot_idx = int(payload.get("slot_idx", 0) or 0)
        qty = max(1, min(99, int(payload.get("qty", 1) or 1)))
        if slot_idx <= 0:
            return {"ok": False, "error": "invalid_slot"}, 400
        _foa_refresh_vendor_stock(me[0])
        with _foa_connect() as db:
            row = db.execute(
                "SELECT item_key, item_name, price, qty, expires_at FROM foa_vendor_stock WHERE user_id = ? AND slot_idx = ?",
                (int(me[0]), int(slot_idx)),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "stock_not_found", **_foa_tower_state(me[0])}, 404
        item_key, item_name, price, stock_qty, expires_at = row
        if str(expires_at or "") <= _foa_now().isoformat():
            _foa_refresh_vendor_stock(me[0])
            return {"ok": False, "error": "stock_expired", **_foa_tower_state(me[0])}, 400
        buy_qty = min(int(stock_qty or 0), qty)
        if buy_qty <= 0:
            return {"ok": False, "error": "out_of_stock", **_foa_tower_state(me[0])}, 400
        total_price = int(price) * int(buy_qty)
        if not spend_gold(int(me[0]), int(total_price), f"foa vendor buy {item_key}", reference_id=f"foa:vendor:{me[0]}:{slot_idx}:{int(time.time()*1000)}", tx_type="foa_vendor_buy"):
            return {"ok": False, "error": "insufficient_balance", **_foa_tower_state(me[0])}, 400
        with _foa_connect() as db:
            db.execute(
                "UPDATE foa_vendor_stock SET qty = qty - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND slot_idx = ?",
                (int(buy_qty), int(me[0]), int(slot_idx)),
            )
            _foa_add_item(db, int(me[0]), str(item_key), int(buy_qty))
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/gear/upgrade", methods=["POST"])
    def fearofabyssgearupgrade():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        slot = str(payload.get("slot", "")).strip().lower()
        if not hero_id or slot not in {"weapon", "armor"}:
            return {"ok": False, "error": "invalid_request"}, 400
        with _foa_connect() as db:
            row = db.execute(
                """
                SELECT rowid, item_key, item_level
                FROM foa_hero_inventory
                WHERE user_id = ? AND hero_id = ? AND slot = ? AND equipped = 1
                ORDER BY rowid DESC LIMIT 1
                """,
                (int(me[0]), hero_id, slot),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "no_equipped_item", **_foa_tower_state(me[0])}, 400
        rowid, item_key, item_level = row
        item_level = max(1, int(item_level or 1))
        cost = 5000 * (2 ** (item_level - 1))
        if not spend_gold(int(me[0]), int(cost), f"foa gear upgrade {item_key}", reference_id=f"foa:gearup:{me[0]}:{rowid}:{item_level+1}", tx_type="foa_gear_upgrade"):
            return {"ok": False, "error": "insufficient_balance", **_foa_tower_state(me[0])}, 400
        meta = FOA_EQUIP_DEFS.get(str(item_key), {"attack": 10, "defense": 5, "hp": 20})
        next_level = item_level + 1
        mul = 1.0 + (next_level - 1) * 0.35
        with _foa_connect() as db:
            db.execute(
                """
                UPDATE foa_hero_inventory
                SET item_level = ?, attack_bonus = ?, defense_bonus = ?, hp_bonus = ?
                WHERE rowid = ?
                """,
                (int(next_level), int(round(meta["attack"] * mul)), int(round(meta["defense"] * mul)), int(round(meta["hp"] * mul)), int(rowid)),
            )
        return {"ok": True, **_foa_tower_state(me[0])}
    
    
    @app.route("/api/fear-of-abyss/hero/revive", methods=["POST"])
    def fearofabyssherorevive():
        me = currentaccount()
        if not me:
            return {"ok": False, "error": "unauthorized"}, 401
        payload = request.get_json(silent=True) or {}
        hero_id = str(payload.get("hero_id", "")).strip()
        if not hero_id:
            return {"ok": False, "error": "missing_hero_id"}, 400
        with _foa_connect() as db:
            tr = db.execute("SELECT infinity_stones FROM foa_tower WHERE user_id = ?", (int(me[0]),)).fetchone()
            stones = int(tr[0] if tr else 0)
            if stones <= 0:
                return {"ok": False, "error": "no_infinity_stone", **_foa_tower_state(me[0])}, 400
            row = db.execute(
                "SELECT max_hp, is_dead FROM foa_heroes WHERE user_id = ? AND hero_id = ?",
                (int(me[0]), hero_id),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "hero_not_found"}, 404
            max_hp, is_dead = row
            if int(is_dead) != 1:
                return {"ok": False, "error": "hero_not_dead", **_foa_tower_state(me[0])}, 400
            db.execute(
                "UPDATE foa_tower SET infinity_stones = infinity_stones - 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (int(me[0]),),
            )
            db.execute(
                """
                UPDATE foa_heroes
                SET hp = ?, is_dead = 0, dead_at = '', delete_at = '', hospital_until = '', updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND hero_id = ?
                """,
                (max(1, int(int(max_hp) * 0.5)), int(me[0]), hero_id),
            )
        return {"ok": True, **_foa_tower_state(me[0])}
    
