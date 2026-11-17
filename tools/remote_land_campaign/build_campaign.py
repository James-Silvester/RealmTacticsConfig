#!/usr/bin/env python3
"""Builds the Remote Land campaign: nine levels, campaign.json, the intro, the campaign map and previews.

    python3 tools/remote_land_campaign/build_campaign.py            # write everything
    python3 tools/remote_land_campaign/build_campaign.py --check    # validate only, write nothing

Everything lands in config/remote-land/version1/maps/campaign. RE-RUNNING THIS
SCRIPT OVERWRITES THE LEVELS, so port any in-game edits back here first.

How a level is described ((0,0) is the bottom left square):
    scatter    natural ground cover, as a share of the map per terrain. It is laid down in clumps
               from the level's seed, so the same seed always gives the same map.
    paint      terrain drawn on top of that, one line per kind: a terrain letter then places.
               "x,y" is one square, "x0,y0>x1,y1" every square in that rectangle.
               .  grassland   f forest   h hill   m mountain   ~ ocean   r rocky   s swamp   = bridge
    buildings  "B1:2,7" is a player Barracks at (2,7). Second character is the owner: . 1 or 2.
               B barracks  C camp  K castle  D dungeon  F farm  H house  O outpost  Q quarry
               S sanctuary  V village  T watchtower  W witch hut
    units      "w1:3,7" is a player Warrior at (3,7).
               a archer  b barbarian  c cyclops  d deep one  g dragon  h healer  k knight  m mage
               f merfolk  p paladin  r rogue  s spider  w warrior  x witch
    waves      numbered groups of enemy units ("s:22,8") that triggers can drop in later.

Buildings and starting ground units always stand on clear grassland unless you paint under them.
Money in Remote Land is one pool per team (food, wood, gold), so there are no supply lines here:
territory is the buildings themselves.
"""
import argparse
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "hacktics_campaign"))
from build_campaign import (ACTIONS, CONDITIONS, allow, flatten, held, hint, intro, on_turn, places, say,  # noqa: E402
                            victory, wiped_out)

VERSION = os.path.join(ROOT, "config", "remote-land", "version1")
CAMPAIGN = os.path.join(VERSION, "maps", "campaign")
TYPES = os.path.join(VERSION, "entities", "types")

TERRAIN = {".": "Grassland", "f": "Forest", "h": "Hill", "m": "Mountain", "~": "Ocean", "r": "Rocky", "s": "Swamp",
           "=": "Bridge"}
BUILDINGS = {"B": "Barracks", "C": "Camp", "K": "Castle", "D": "Dungeon", "F": "Farm", "H": "House", "O": "Outpost",
             "Q": "Quarry", "S": "Sanctuary", "V": "Village", "T": "Watchtower", "W": "WitchHut"}
UNITS = {"a": "Archer", "b": "Barbarian", "c": "Cyclops", "d": "DeepOne", "g": "Dragon", "h": "Healer", "k": "Knight",
         "m": "Mage", "f": "Merfolk", "p": "Paladin", "r": "Rouge", "s": "Spider", "w": "Warrior", "x": "Witch"}
SWIMS, FLIES = {"Merfolk"}, {"Dragon", "Witch"}
WATER = {"Ocean", "Swamp", "Bridge"}
OWNERS = {"1": "TEAM_1", "2": "TEAM_2", ".": None}
P1, P2, NEUTRAL = "TEAM_1", "TEAM_2", "TEAM_UNDEFINED"
HUMANS = ["Archer", "Barbarian", "Warrior", "Knight", "Rouge", "Mage", "Healer", "Paladin"]


# --- Trigger helpers particular to Remote Land -------------------------------

def wave(name, turn, units, *lines, team=P2, done="To arms", fed_by=None):
    """Drops reinforcements in at the start of a team's turn. With fed_by (building ids) the wave
    only arrives while that team still owns every one of them."""
    conditions = [{"Type": "TURN_NUMBER", "TurnNumber": turn}, {"Type": "CURRENT_TEAM", "TeamId": team}]
    conditions += [held(b, team) for b in (fed_by or [])]
    actions = [say(*lines, done=done)] if lines else []
    for code, x, y in units:
        actions.append({"Type": "INSERT_ENTITY", "EntityType": UNITS[code], "TeamId": team,
                        "Position": {"X": x, "Y": y}, "TurnEnded": False})
    return {"Name": name, "Conditions": conditions, "Actions": actions}


def when_held(name, building, by, *lines, done="Understood"):
    return {"Name": name, "Conditions": [held(building, by)], "Actions": [say(*lines, done=done)]}


def destroyed(entity_id):
    return {"Type": "ENTITY", "EntitySelector": {"EntitySelected": entity_id}, "CheckIsDestroyed": True}


def endings(m, win=None, keep=None):
    """win: extra ways to win, each a list of conditions. keep: a building the player must not lose."""
    out = [victory(f"Won{n}", conditions, P1) for n, conditions in enumerate(win or [])]
    if keep:
        out.append(victory("StrongholdLost", [held(keep, P2)], P2))
    return out + [wiped_out(P1, P2), wiped_out(P2, P1)]


# --- Levels ------------------------------------------------------------------

LEVELS = [
    dict(
        file="01-landfall.json", name="Landfall", flag="Landfall_Complete", difficulty=1,
        description="Learn to move, fight, capture buildings and recruit",
        summary="The king's charter gives Ashmark the Remote Land, if Ashmark can hold it. Your boats ground on a quiet beach. It does not stay quiet.",
        terms="Capture the enemy Camp, or destroy every enemy unit.\nYou lose if all your units are destroyed.",
        size=(18, 12), seed=3, scatter={"f": 0.2, "h": 0.07},
        paint="""
            ~ 0,0>0,11
            . 1,4>16,7
            f 7,7>8,7  12,4>13,4
        """,
        buildings="H.:6,6 C.:10,5 F.:8,9 C2:15,6 H2:16,8",
        units="w1:2,6 w1:2,5 a1:2,7 a1:2,4   b2:14,6 b2:15,5 a2:16,6 w2:15,7",
        triggers=lambda m: [
            intro("Edda: Welcome ashore, Captain. I'm Edda, your quartermaster. I keep the ledgers; you keep us alive.",
                  "Edda: The Tidewatch landed here before us and they don't mean to share. Their camp is east along the track.",
                  "Edda: Select a unit to see where it can go. Warriors fight up close. Archers shoot from a distance and are best kept behind them.",
                  done="Understood"),
            allow(P1, "Archer", "Barbarian", "Warrior"),
            allow(P2, "Archer", "Barbarian", "Warrior"),
            hint("TaughtWarrior", "Warrior",
                 "Warriors can move and then strike an enemy on the next square in the same turn. They are armoured, so they take the first blows better than most."),
            hint("TaughtArcher", "Archer",
                 "Archers hit targets 2 to 4 squares away, but only if they have not moved this turn. Move them one turn, shoot the next, and never leave one next to an enemy."),
            hint("TaughtForest", "Forest",
                 "Forest and hills cost ground units extra movement to enter, but anything standing in them is harder to hurt. The open track is quicker and more dangerous.",
                 team=NEUTRAL),
            hint("TaughtHouse", "House",
                 "Buildings belong to whoever captures them. Stand a unit on this House and choose Capture. Most buildings need capturing twice; a unit that doesn't move can do both in one turn.",
                 team=NEUTRAL),
            when_held("HouseTaken", m.at(6, 6), P1,
                      "Edda: That House is ours, and it pays a little gold every turn. Everything we own pays into one purse: food, wood and gold.",
                      "Edda: There's an empty Camp further along the track. Take that and we can recruit."),
            when_held("CampTaken", m.at(10, 5), P1,
                      "Edda: The Camp is ours. Select it to recruit. A recruit appears on the Camp and can't act until next turn, and each building musters one unit a turn.",
                      done="Good"),
            endings(m, win=[[held(m.at(15, 6), P1)]]),
        ],
    ),
    dict(
        file="02-the-granary.json", name="The Granary", flag="TheGranary_Complete", difficulty=2,
        description="Fight over farms, quarries and a village to out-grow the enemy",
        summary="An army marches on food, builds with wood and is paid in gold. The valley inland has all three, and the Tidewatch has seen it too.",
        terms="Capture the enemy Barracks, or destroy every enemy unit.\nYou lose if your Barracks is captured or all your units are destroyed.",
        size=(22, 14), seed=11, scatter={"f": 0.18, "h": 0.07, "r": 0.03},
        paint="""
            . 2,6>19,7
        """,
        buildings="""B1:2,7 H1:3,9 F1:2,5
                     F.:6,10 F.:7,3 F.:10,7 Q.:9,11 Q.:12,3 H.:5,6 H.:8,8 H.:13,9 V.:11,6
                     B2:19,7 H2:18,9 F2:19,5 C2:16,7 Q2:17,11""",
        units="w1:3,7 w1:3,6 a1:2,8 a1:2,6 k1:4,7   b2:17,7 b2:17,6 r2:18,8 a2:19,8 a2:19,6 w2:18,6",
        waves={1: "r:20,12 r:20,1 b:21,7", 2: "k:20,7 w:20,8 a:21,6"},
        triggers=lambda m: [
            intro("Edda: Three things run an army, Captain. Food from Farms, gold from Quarries and Houses, and wood from Barracks, Camps and Villages.",
                  "Edda: Every recruit costs some of each. A Knight wants ten food, ten wood and five gold. Right now we can barely feed an Archer.",
                  "Edda: The valley is full of buildings nobody holds yet. Whoever takes more of them recruits faster. The Village in the middle is worth three farms.",
                  done="Then we take it"),
            allow(P1, "Archer", "Barbarian", "Warrior", "Knight"),
            allow(P2, "Archer", "Barbarian", "Warrior", "Knight", "Rouge"),
            hint("TaughtFarm", "Farm", "A Farm gives 3 food a turn and nothing else. Food is in nearly every recruit's price.", team=NEUTRAL),
            hint("TaughtQuarry", "Quarry", "A Quarry gives 3 gold a turn. Gold pays for the better troops: Knights now, Mages and Paladins later.", team=NEUTRAL),
            hint("TaughtVillage", "Village",
                 "A Village gives 4 of everything and can muster troops as well, so taking it puts your recruits in the middle of the valley instead of back at the Barracks.",
                 team=NEUTRAL),
            hint("TaughtKnight", "Knight",
                 "Knights are slow and heavily armoured. Put one on a building you mean to keep: buildings shelter whoever owns them, and a Knight on a Village is very hard to shift."),
            hint("TaughtRogue", "Rouge",
                 "Rogues cover nine squares a turn and go for whatever is undefended. They hit hard but glance off armour, so a Warrior or Knight sees them off.",
                 team=P2),
            wave("Raiders", 4, m.wave(1), "Edda: Riders on both flanks! Rogues, and they're after our farms. Don't leave buildings empty behind you."),
            wave("Column", 8, m.wave(2), "Edda: A fresh column at their Barracks, with a Knight at its head."),
            endings(m, win=[[held(m.at(19, 7), P1)]], keep=m.at(2, 7)),
        ],
    ),
    dict(
        file="03-bridgewater.json", name="Bridgewater", flag="Bridgewater_Complete", difficulty=2,
        description="Force a river with two bridges, a ford and something in the water",
        summary="The Bridgewater cuts the island in two. There are two bridges and a ford, and the Tidewatch holds the far bank.",
        terms="Capture the enemy Barracks, or destroy every enemy unit.\nYou lose if your Barracks is captured or all your units are destroyed.",
        size=(24, 14), seed=7, scatter={"f": 0.2, "h": 0.06, "r": 0.03},
        paint="""
            ~ 11,0>12,13
            = 11,10>12,10  11,3>12,3
            s 11,6>12,7
            . 2,10>10,10  13,10>21,10  2,3>10,3  13,3>21,3  5,6>10,7  13,6>18,7
        """,
        buildings="""B1:2,7 V1:4,9 H1:3,5 F1:2,11 Q1:5,2
                     T.:9,10 T.:14,10 T.:9,3 T.:14,3 O.:9,7 F.:7,12 Q.:16,1 H.:8,5 H.:15,8
                     B2:21,7 V2:19,5 H2:20,9 F2:21,2 Q2:18,12 O2:14,6""",
        units="""w1:4,7 w1:4,6 k1:5,7 a1:3,8 a1:3,6 m1:3,7
                 w2:19,7 w2:19,6 k2:18,7 a2:15,10 a2:15,3 a2:20,8 f2:11,8 f2:12,5 b2:17,8""",
        waves={1: "f:11,12 f:12,1 b:22,7", 2: "k:22,8 m:22,6 w:22,7"},
        triggers=lambda m: [
            intro("Edda: The Bridgewater. Too deep to wade except at the ford in the middle, and the ford is a swamp that will take your troops a whole turn to cross.",
                  "Edda: So it's the bridges, and they have Archers watching both. I've brought you a Mage. Keep her alive; she cost more than the boats.",
                  "Edda: One more thing. The Tidewatch didn't get their name by staying dry. Watch the water.",
                  done="Forward"),
            allow(P1, "Archer", "Barbarian", "Warrior", "Knight", "Mage", "Merfolk", "DeepOne"),
            allow(P2, "Archer", "Barbarian", "Warrior", "Knight", "Rouge", "Mage", "Merfolk"),
            hint("TaughtMage", "Mage",
                 "The Mage strikes anything up to 6 squares away if she has not moved, and the blast also burns every unit beside the target, friend or foe. She has no armour at all."),
            hint("TaughtBridge", "Bridge",
                 "A Bridge is the only dry way over deep water. Whoever stands on it blocks it, which makes a Knight on a bridge worth three in a field.",
                 team=NEUTRAL),
            hint("TaughtSwamp", "Swamp",
                 "Swamp costs ground units three extra movement to enter and gives no cover at all. Things that swim cross it as if it were open water.",
                 team=NEUTRAL),
            hint("TaughtMerfolk", "Merfolk",
                 "Merfolk never leave the water, but they can move and then strike up to 2 squares away, so anything on the bank or a bridge is in reach. Archers and Mages can answer them; swords cannot reach.",
                 team=P2),
            hint("TaughtOutpost", "Outpost",
                 "An Outpost on the bank musters creatures of the river. Capture it and you can put Merfolk of your own in the water. It only needs capturing once.",
                 team=NEUTRAL),
            hint("TaughtWatchtower", "Watchtower",
                 "A Watchtower earns nothing, but a unit standing in one you own is well protected. It only needs capturing once.", team=NEUTRAL),
            wave("RiverRising", 5, m.wave(1), "Edda: More of them in the river, north and south. They're going for whoever is on the bridges."),
            wave("FarBank", 9, m.wave(2), "Edda: Reinforcements on the far bank, and they have a Mage of their own. Spread out."),
            endings(m, win=[[held(m.at(21, 7), P1)]], keep=m.at(2, 7)),
        ],
    ),
    dict(
        file="04-sanctuary-road.json", name="Sanctuary Road", flag="SanctuaryRoad_Complete", difficulty=3,
        description="Relieve a besieged Sanctuary and shut the Dungeon the spiders come from",
        summary="Deep in the forest the brothers of the Sanctuary are holding out against things that were not on any Tidewatch muster roll. They have asked for help once. They will not be able to ask twice.",
        terms="Capture the Dungeon, or destroy every enemy unit.\nYou lose if the Sanctuary is captured or all your units are destroyed.",
        size=(26, 14), seed=5, scatter={"f": 0.34, "h": 0.07, "r": 0.04},
        paint="""
            . 2,6>24,7  9,8>9,9  12,10>12,11  8,3>8,5  22,3>22,5  22,8>22,10
            . 14,5>18,9
        """,
        buildings="""B1:2,6 H1:2,9 F1:3,4 S1:16,7
                     V.:9,9 F.:8,3 Q.:12,11 H.:11,5 T.:13,7
                     C2:22,10 C2:22,3 D2:23,7""",
        units="""w1:3,6 w1:3,7 k1:4,6 a1:2,7 a1:2,5 m1:3,5 h1:16,8 p1:17,7 a1:16,6 w1:15,7
                 s2:19,9 s2:19,5 s2:20,7 b2:18,10 b2:18,4 a2:21,8 a2:21,6 w2:22,7 r2:21,10""",
        waves={1: "s:22,8 s:22,6", 2: "s:22,8 s:22,6 b:24,7", 3: "s:21,7 s:22,8 s:22,6"},
        triggers=lambda m: [
            intro("Edda: Spiders the size of ponies, Captain. The brothers say they come out of an old Dungeon at the end of the road, and the Tidewatch is driving them.",
                  "Edda: The Sanctuary's garrison is a Healer, a Paladin and whoever could hold a bow. If the Sanctuary is captured we lose them and the road.",
                  "Edda: Get the column there, then go on and take the Dungeon. Until someone does, more will keep crawling out of it.",
                  done="March"),
            allow(P1, "Archer", "Barbarian", "Warrior", "Knight", "Mage", "Healer", "Paladin"),
            allow(P2, "Archer", "Barbarian", "Warrior", "Rouge", "Spider"),
            hint("TaughtHealer", "Healer",
                 "The Healer mends instead of fighting. Pick a spot up to 4 squares away and every friendly unit within 2 squares of it recovers a little, the Healer included. She cannot move and heal in one turn."),
            hint("TaughtPaladin", "Paladin",
                 "Paladins are quick, very well armoured and hit monsters for two and a half times the usual damage. Send them at the spiders. They are expensive, so do not send them alone."),
            hint("TaughtSpider", "Spider",
                 "Spiders ignore terrain altogether: forest, hills, even water cost them nothing. Magic barely touches them. A Paladin's hammer does.",
                 team=P2),
            hint("TaughtSanctuary", "Sanctuary",
                 "A Sanctuary musters Healers and Paladins, and shelters whoever stands in it better than anything short of a Castle."),
            hint("TaughtDungeon", "Dungeon",
                 "Monsters are mustered at Dungeons. While the Tidewatch holds this one, spiders will keep coming. Capture it and they stop.",
                 team=P2),
            wave("Brood1", 3, m.wave(1), "Edda: More spiders out of the Dungeon. They will go round your line, not through it.", fed_by=[m.at(23, 7)]),
            wave("Brood2", 6, m.wave(2), "Edda: Another brood. That Dungeon will not empty itself.", fed_by=[m.at(23, 7)]),
            wave("Brood3", 9, m.wave(3), "Edda: Still coming. Captain, the Dungeon.", fed_by=[m.at(23, 7)]),
            when_held("DungeonTaken", m.at(23, 7), P1, "Edda: The Dungeon is sealed. Whatever is still out there is all there is."),
            endings(m, win=[[held(m.at(23, 7), P1)]], keep=m.at(16, 7)),
        ],
    ),
    dict(
        file="05-the-witchwood.json", name="The Witchwood", flag="TheWitchwood_Complete", difficulty=3,
        description="Hunt down three Witch Huts while their owners fly over your lines",
        summary="The spiders had a mistress. The brothers call her Mother Sallow, and the marsh she lives in the Witchwood. The Tidewatch pays her in something other than gold.",
        terms="Capture all three Witch Huts, or destroy every enemy unit.\nYou lose if your Barracks is captured or all your units are destroyed.",
        size=(24, 16), seed=21, scatter={"f": 0.28, "s": 0.16, "h": 0.04},
        paint="""
            . 2,7>9,8  9,8>9,12  9,4>9,7  9,12>17,12  9,4>16,4  13,8>19,8
        """,
        buildings="""B1:2,8 S1:3,10 V1:3,5 F1:2,12 Q1:4,3
                     H.:8,12 H.:9,4 F.:10,9 Q.:12,6 T.:13,11 T.:13,4 V.:14,8
                     W2:19,13 W2:21,8 W2:18,2 C2:21,11""",
        units="""w1:4,8 w1:4,7 k1:5,8 a1:3,9 a1:3,7 a1:4,9 m1:3,8 h1:2,9 p1:5,7
                 x2:18,12 x2:20,9 x2:18,3 s2:16,8 s2:17,11 b2:17,5 b2:19,6 a2:20,12 a2:20,3 w2:21,9""",
        waves={1: "x:20,14", 2: "x:22,8", 3: "x:19,1", 4: "x:20,14 s:20,13", 5: "x:22,8 s:22,9", 6: "x:19,1 s:19,2"},
        triggers=lambda m: [
            intro("Edda: Mother Sallow's sisters ride the air, Captain. Ten squares a turn, over forest and marsh as if it were a parade ground.",
                  "Edda: A sword can't reach something that flies. Only Archers, Mages and Paladins can touch them. Everyone else is a target.",
                  "Edda: They roost in three huts in the marsh. Every hut still standing sends another witch. Burn out all three.",
                  done="Into the marsh"),
            allow(P1, "Archer", "Barbarian", "Warrior", "Knight", "Mage", "Healer", "Paladin", "Witch"),
            allow(P2, "Archer", "Barbarian", "Warrior", "Spider", "Witch"),
            hint("TaughtWitch", "Witch",
                 "Witches fly, so terrain means nothing to them and most blades cannot reach them. They are frail: one good volley from Archers or a Mage's blast brings one down.",
                 team=P2),
            hint("TaughtWitchHut", "WitchHut",
                 "Each Witch Hut the enemy owns keeps sending witches. Capture it and that stops, and you can muster witches of your own from it.",
                 team=P2),
            wave("NorthHut1", 3, m.wave(1), "Edda: A witch up from the northern hut.", fed_by=[m.at(19, 13)]),
            wave("EastHut1", 4, m.wave(2), "Edda: Another, from the hut in the east.", fed_by=[m.at(21, 8)]),
            wave("SouthHut1", 5, m.wave(3), "Edda: And the southern one. They take it in turns.", fed_by=[m.at(18, 2)]),
            wave("NorthHut2", 8, m.wave(4), fed_by=[m.at(19, 13)]),
            wave("EastHut2", 9, m.wave(5), fed_by=[m.at(21, 8)]),
            wave("SouthHut2", 10, m.wave(6), fed_by=[m.at(18, 2)]),
            when_held("NorthHutTaken", m.at(19, 13), P1, "Edda: The northern hut is ours. One less roost."),
            when_held("EastHutTaken", m.at(21, 8), P1, "Edda: The eastern hut is ours."),
            when_held("SouthHutTaken", m.at(18, 2), P1, "Edda: The southern hut is ours."),
            endings(m, win=[[held(m.at(19, 13), P1), held(m.at(21, 8), P1), held(m.at(18, 2), P1)]], keep=m.at(2, 8)),
        ],
    ),
    dict(
        file="06-tidefall.json", name="Tidefall", flag="Tidefall_Complete", difficulty=4,
        description="Hold a harbour town against what comes up out of the sea",
        summary="With the Witchwood quiet, Ashmark's settlers have built a town on the eastern shore. The Tidewatch's oldest allies live just off it, and they have noticed.",
        terms="Hold out until turn 12, capture all three Outposts, or destroy every enemy unit.\nYou lose if your Castle is captured or all your units are destroyed.",
        size=(24, 16), seed=9, scatter={"f": 0.14, "h": 0.06, "r": 0.04},
        paint="""
            ~ 14,0>23,15
            r 16,11>18,13  18,6>20,8  16,2>18,4
            . 17,12  19,7  17,3
            = 14,12>15,12  14,3>15,3  14,7>17,7
            . 10,3>13,3  10,7>13,7  10,12>13,12  10,3>10,12
        """,
        buildings="""K1:6,8 V1:8,10 V1:8,5 B1:5,5 S1:4,10 F1:3,7 F1:4,13 Q1:2,4 H1:7,7 H1:9,8 T1:12,12 T1:12,7 T1:12,3
                     O2:17,12 O2:19,7 O2:17,3""",
        units="""w1:11,12 w1:11,3 k1:11,7 k1:10,8 a1:10,11 a1:10,4 a1:9,7 m1:8,8 h1:7,8 p1:9,6
                 d2:16,12 d2:17,11 d2:18,7 d2:20,7 d2:17,4 d2:16,3 f2:15,10 f2:15,5 f2:16,9 f2:14,1""",
        waves={1: "d:16,13 d:18,12", 2: "d:18,8 d:20,6", 3: "d:16,2 d:18,3", 4: "f:20,14 f:21,10 f:20,1",
               5: "d:16,13 d:18,12 d:17,13", 6: "d:18,8 d:20,6 d:19,6", 7: "d:16,2 d:18,3 d:17,2"},
        triggers=lambda m: [
            intro("Edda: Deep Ones, Captain. They have Outposts on three reefs out in the bay, and a causeway from each one to our shore.",
                  "Edda: The king's ships are ten turns out. Hold the Castle until turn 12 and the fleet does the rest. Lose the Castle and there is no town for them to save.",
                  "Edda: Or go out along a causeway and take the Outposts yourself. Each one you capture is one less tide coming in.",
                  done="Man the shore"),
            allow(P1, *HUMANS, "Merfolk", "DeepOne"),
            allow(P2, "DeepOne", "Merfolk"),
            hint("TaughtDeepOne", "DeepOne",
                 "Deep Ones fight on land like any raider, quick and lightly protected. There are simply a great many of them, and they keep coming while their Outposts stand.",
                 team=P2),
            hint("TaughtCastle", "Castle",
                 "A Castle pays 3 of everything and shelters its garrison better than any other building. It takes four captures to change hands, so a determined enemy needs two turns standing on it."),
            hint("TaughtEnemyOutpost", "Outpost",
                 "This reef Outpost is where the Deep Ones muster. It only needs capturing once, but you have to cross the causeway to do it, with Merfolk on both sides of you.",
                 team=P2),
            wave("NorthTide1", 3, m.wave(1), "Edda: They're coming off the northern reef.", fed_by=[m.at(17, 12)]),
            wave("MidTide1", 4, m.wave(2), "Edda: The middle reef now. The long causeway.", fed_by=[m.at(19, 7)]),
            wave("SouthTide1", 5, m.wave(3), "Edda: And the south.", fed_by=[m.at(17, 3)]),
            wave("Shoal", 6, m.wave(4), "Edda: Merfolk in the bay, a whole shoal of them. Keep your Archers back from the water's edge."),
            wave("NorthTide2", 8, m.wave(5), "Edda: A bigger tide off the northern reef.", fed_by=[m.at(17, 12)]),
            wave("MidTide2", 9, m.wave(6), "Edda: The middle reef again.", fed_by=[m.at(19, 7)]),
            wave("SouthTide2", 10, m.wave(7), "Edda: Sails on the horizon, Captain. Two more turns.", fed_by=[m.at(17, 3)]),
            endings(m, win=[[{"Type": "TURN_NUMBER", "TurnNumber": 12}, {"Type": "CURRENT_TEAM", "TeamId": P1}],
                            [held(m.at(17, 12), P1), held(m.at(19, 7), P1), held(m.at(17, 3), P1)]], keep=m.at(6, 8)),
        ],
    ),
    dict(
        file="07-giants-pass.json", name="Giant's Pass", flag="GiantsPass_Complete", difficulty=4,
        description="Break through a mountain pass held by Cyclopes",
        summary="The only road to the Tidewatch heartland runs through the mountains, and the mountains have tenants. Steel hardly marks them.",
        terms="Capture both Dungeons, or destroy every enemy unit.\nYou lose if your Barracks is captured or all your units are destroyed.",
        size=(26, 16), seed=14, scatter={"r": 0.1, "h": 0.1, "f": 0.1},
        paint="""
            m 6,14>19,15  6,0>19,1  11,10>12,13  11,2>12,5  17,10>18,12  17,3>18,5
            . 2,7>23,8  9,9>9,12  10,3>10,6  15,9>15,11  15,4>15,6  21,9>21,12  22,4>22,6
        """,
        buildings="""B1:2,8 V1:3,5 S1:3,11 Q1:2,3 F1:4,13 H1:5,8
                     Q.:9,12 Q.:10,3 V.:13,8 T.:11,8 T.:16,8 H.:15,11 H.:15,4 F.:8,8
                     D2:22,12 D2:23,4 C2:21,8""",
        units="""w1:4,8 w1:4,7 k1:5,7 a1:3,9 a1:3,7 m1:3,8 m1:2,7 p1:5,9 h1:2,9
                 c2:20,8 c2:21,11 c2:22,5 b2:19,9 b2:19,7 a2:22,8 a2:23,9 r2:20,6 s2:18,8""",
        waves={1: "c:21,12", 2: "c:22,4", 3: "c:21,12 s:22,13", 4: "c:22,4 s:22,3"},
        triggers=lambda m: [
            intro("Edda: Cyclopes, Captain. The Tidewatch has let two Dungeons full of them loose on the pass.",
                  "Edda: A sword takes off a tenth of what it should. They shrug at arrows. What they don't like is magic, and what they like least of all is a Paladin.",
                  "Edda: There is gold in these hills. Take the Quarries, buy Mages and Paladins, and close those Dungeons.",
                  done="Through the pass"),
            allow(P1, *HUMANS, "Cyclops", "Spider"),
            allow(P2, "Archer", "Barbarian", "Rouge", "Cyclops", "Spider"),
            hint("TaughtCyclops", "Cyclops",
                 "A Cyclops turns aside nine parts in ten of an ordinary blow and hits twice as hard as a Knight. Magic gets half its force through, and a Paladin's hammer does two and a half times its usual harm. It is slow: don't let it catch you.",
                 team=P2),
            hint("TaughtMountain", "Mountain",
                 "Mountains cost ground units two extra movement to enter and shelter whoever is on them. Cyclopes walk over mountain and rock as if they were a road.",
                 team=NEUTRAL),
            hint("TaughtEnemyDungeon", "Dungeon",
                 "While the Tidewatch holds this Dungeon it will keep turning out Cyclopes. Capture it and you can muster monsters from it yourself.",
                 team=P2),
            wave("North1", 4, m.wave(1), "Edda: Another Cyclops out of the northern Dungeon.", fed_by=[m.at(22, 12)]),
            wave("South1", 6, m.wave(2), "Edda: And one from the south.", fed_by=[m.at(23, 4)]),
            wave("North2", 9, m.wave(3), "Edda: The northern Dungeon again, and it has brought a spider.", fed_by=[m.at(22, 12)]),
            wave("South2", 11, m.wave(4), "Edda: The southern one too. Captain, the gold won't last for ever.", fed_by=[m.at(23, 4)]),
            when_held("NorthDungeonTaken", m.at(22, 12), P1, "Edda: The northern Dungeon is ours. If you fancy a Cyclops of your own, now you can afford to ask."),
            when_held("SouthDungeonTaken", m.at(23, 4), P1, "Edda: The southern Dungeon is ours."),
            endings(m, win=[[held(m.at(22, 12), P1), held(m.at(23, 4), P1)]], keep=m.at(2, 8)),
        ],
    ),
    dict(
        file="08-three-castles.json", name="Three Castles", flag="ThreeCastles_Complete", difficulty=5,
        description="A full war for the heartland: hold all three Castles",
        summary="Beyond the pass lies the best land on the island and Lord Corvane's seat. Three Castles stand in a line across it. Ashmark holds one.",
        terms="Hold all three Castles, or destroy every enemy unit.\nYou lose if your own Castle is captured or all your units are destroyed.",
        size=(30, 18), seed=4, scatter={"f": 0.2, "h": 0.08, "r": 0.04, "s": 0.03},
        paint="""
            ~ 14,3>16,4  13,13>14,14
            . 3,8>26,9  10,10>10,14  11,4>11,7  19,10>19,13  20,4>20,7
        """,
        buildings="""K1:3,9 V1:5,12 B1:4,6 F1:2,13 Q1:2,4 H1:6,8
                     K.:15,9 V.:10,14 V.:11,4 V.:19,13 V.:20,4 B.:15,12 F.:7,10 F.:9,2 F.:13,6 F.:17,11 F.:22,8
                     F.:21,15 Q.:8,16 Q.:15,1 Q.:22,2 H.:12,10 H.:18,8 S.:15,15 C.:10,8 C.:20,9 T.:12,9 T.:18,10
                     K2:26,9 V2:24,6 B2:25,12 F2:27,5 Q2:28,14 H2:23,10""",
        units="""w1:4,9 w1:4,8 w1:5,10 k1:5,9 k1:5,8 a1:3,10 a1:3,8 a1:4,10 m1:2,9 h1:2,8 p1:6,9 r1:5,7
                 w2:25,9 w2:25,8 w2:24,10 k2:24,9 k2:24,8 a2:26,10 a2:26,8 a2:25,10 m2:27,9 h2:27,8 p2:23,9
                 r2:24,7 b2:23,8""",
        waves={1: "k:28,9 m:28,8 a:28,10", 2: "p:28,9 k:27,10 w:27,8 r:28,11"},
        triggers=lambda m: [
            intro("Edda: No monsters this time, Captain. Just Lord Corvane, his whole household, and the best farmland on the island between you.",
                  "Edda: Three Castles: ours, his, and an empty one in the middle that neither of you can afford to let the other keep. Hold all three and he has nowhere left to sit.",
                  "Edda: There are villages, farms and quarries all the way across. This will be won by whoever is still recruiting at the end.",
                  done="For Ashmark"),
            allow(P1, *HUMANS),
            allow(P2, *HUMANS),
            hint("TaughtMiddleCastle", "Castle",
                 "The middle Castle belongs to nobody yet. It takes four captures, so bring two units or expect to stand there for two turns, and expect company.",
                 team=NEUTRAL),
            wave("Household", 6, m.wave(1), "Edda: Corvane's household troops have come up to his Castle."),
            wave("Corvane", 12, m.wave(2), "Edda: That's his own banner, Captain, and Paladins under it. He has decided to stop losing."),
            when_held("MiddleTaken", m.at(15, 9), P1, "Edda: The middle Castle is ours. He will want it back badly. Garrison it."),
            when_held("MiddleLost", m.at(15, 9), P2, "Edda: Corvane has the middle Castle. Two of three. Take it off him before he digs in."),
            endings(m, win=[[held(m.at(15, 9), P1), held(m.at(26, 9), P1)]], keep=m.at(3, 9)),
        ],
    ),
    dict(
        file="09-dragonspire.json", name="Dragonspire", flag="Dragonspire_Complete", difficulty=5,
        description="Kill the dragon",
        summary="Corvane is beaten, and Mother Sallow has one debt left to call in. It sleeps on a spire at the edge of the island. It is awake now.",
        terms="Kill the Dragon, or destroy every enemy unit.\nYou lose if your Castle is captured or all your units are destroyed.",
        size=(30, 18), seed=17, scatter={"f": 0.18, "h": 0.08, "r": 0.07, "s": 0.03},
        paint="""
            m 23,7>27,11  22,8>22,10  24,12>26,12  24,6>26,6
            r 21,6>21,12  28,6>28,12
            . 3,8>20,9  11,10>11,13  12,4>12,7  16,10>16,14  20,10>20,13  20,4>20,7
        """,
        buildings="""K1:3,9 B1:4,6 S1:4,12 V1:6,9 Q1:2,3 F1:2,15
                     V.:11,13 V.:12,4 Q.:14,9 F.:9,7 H.:10,10 S.:16,14 T.:15,6 T.:17,10 Q.:17,3 F.:14,15
                     D2:22,13 D2:23,4 W2:20,9 C2:21,5""",
        units="""p1:5,9 p1:5,10 p1:6,8 k1:6,10 w1:5,8 w1:6,7 a1:4,9 a1:4,10 a1:4,8 m1:3,10 h1:3,8 h1:4,11
                 g2:25,9 x2:21,10 x2:21,8 c2:22,11 c2:23,6 s2:19,12 s2:19,5 s2:20,7 b2:20,11 b2:21,4
                 a2:23,9 a2:23,10""",
        waves={1: "c:21,13 s:22,14", 2: "c:22,4 s:23,3", 3: "x:19,9", 4: "c:21,13 s:22,14", 5: "c:22,4 s:23,3", 6: "x:19,9 x:20,10"},
        triggers=lambda m: [
            intro("Edda: I have been a quartermaster for thirty years, Captain, and I have never had to write 'one dragon' in a ledger.",
                  "Edda: It flies, so only Archers, Mages and Paladins can reach it. Magic slides off it. Arrows annoy it. The only thing we own that it truly feels is a Paladin's hammer.",
                  "Edda: Its fire lands exactly two squares from it and burns everything around the spot. Stand right beside it or well away from it, and never in a huddle.",
                  "Edda: Sallow's Dungeons and her hut are still feeding it friends. Shut them if you can. Then kill that thing and we can all go home.",
                  done="Paladins, with me"),
            allow(P1, *HUMANS, "Cyclops", "Spider", "Witch"),
            allow(P2, "Barbarian", "Archer", "Cyclops", "Spider", "Witch"),
            hint("TaughtDragon", "Dragon",
                 "The Dragon turns aside four parts in five of any blow and nearly all magic. Paladins hit monsters for two and a half times the damage, which is the only arithmetic that works. It cannot breathe fire on anything standing next to it.",
                 team=P2),
            wave("North1", 4, m.wave(1), "Edda: The northern Dungeon is emptying.", fed_by=[m.at(22, 13)]),
            wave("South1", 5, m.wave(2), "Edda: And the southern.", fed_by=[m.at(23, 4)]),
            wave("Hut1", 6, m.wave(3), "Edda: A witch from the hut below the spire.", fed_by=[m.at(20, 9)]),
            wave("North2", 9, m.wave(4), fed_by=[m.at(22, 13)]),
            wave("South2", 10, m.wave(5), fed_by=[m.at(23, 4)]),
            wave("Hut2", 11, m.wave(6), "Edda: More witches. She is throwing in everything she has.", fed_by=[m.at(20, 9)]),
            endings(m, win=[[destroyed(m.unit_at(25, 9))]], keep=m.at(3, 9)),
        ],
    ),
]

INTRO = """The king's charter is a single page. It gives the March of Ashmark every acre of the Remote Land, a chain of islands at the edge of every map, on the one condition that Ashmark goes and takes them.

.

The Tidewatch holds the same charter from a different king.

.

<b>From the quartermaster's ledger</b>

<i>Boats: three. Soldiers: enough. Captain: new.</i>

<i>We land at dawn.</i>

<i>Edda</i>

.

Nobody thought to ask who was living there already.
"""

# The campaign map is a chart of the islands. Each level has a site on it, in map pixels (x from the
# left, y from the top), grouped into the islands they stand on.
MAP_PIXELS = (416, 224)
MAP_SITES = [(40, 172), (88, 130), (142, 156), (180, 92), (150, 44), (236, 172), (276, 112), (322, 152), (374, 66)]
ISLANDS = [  # name, the sites on it, label position, tint
    ("ASHMARK", (0, 1, 2), (52, 196), (214, 150, 120)),
    ("WITCHWOOD", (3, 4), (176, 22), (120, 160, 110)),
    ("TIDEWATCH", (5, 6, 7), (244, 198), (130, 160, 214)),
    ("DRAGONSPIRE", (8,), (318, 28), (150, 140, 140)),
]


# --- Building maps -----------------------------------------------------------

def tokens(text):
    out = []
    for token in text.split():
        head, where = token.split(":")
        x, y = map(int, where.split(","))
        out.append((head, x, y))
    return out


def make_terrain(level):
    import numpy as np
    from PIL import Image
    width, height = level["size"]
    rng = np.random.default_rng(level["seed"])

    def noise(cell):
        small = rng.random((height // cell + 2, width // cell + 2)).astype("float32")
        return np.asarray(Image.fromarray(small).resize((width, height), Image.BICUBIC))

    grid = {(x, y): "." for x in range(width) for y in range(height)}
    for code, share in level["scatter"].items():
        field = noise(4) + 0.35 * noise(2)
        cut = np.quantile(field, 1 - share)
        for (x, y) in grid:
            if field[y, x] > cut and grid[(x, y)] == ".":
                grid[(x, y)] = code
    painted = set()
    for line in level["paint"].strip().splitlines():
        code, *specs = line.split()
        for spec in specs:
            for pos in places(spec):
                assert pos in grid, f"{level['file']}: paint off the map at {pos}"
                grid[pos] = code
                painted.add(pos)
    for head, x, y in tokens(level["buildings"]) + tokens(level["units"]):
        walks = head[0] in BUILDINGS or UNITS.get(head[0]) not in SWIMS | FLIES
        if (x, y) not in painted and walks:
            grid[(x, y)] = "."
    return grid


class MapRef:
    def __init__(self, level):
        self.level, self.buildings, self.units = level, {}, {}

    def at(self, x, y):
        assert (x, y) in self.buildings, f"{self.level['file']}: no building at {(x, y)}"
        return self.buildings[(x, y)]

    def unit_at(self, x, y):
        assert (x, y) in self.units, f"{self.level['file']}: no unit at {(x, y)}"
        return self.units[(x, y)]

    def wave(self, number):
        return [(head[0], x, y) for head, x, y in tokens(self.level["waves"][number])]


def build_map(level):
    width, height = level["size"]
    grid = make_terrain(level)
    ref = MapRef(level)
    entities = []

    def add(kind, x, y, team=None):
        entity = {"Id": len(entities) + 1, "Position": {"X": x, "Y": y}, "Type": kind}
        if team:
            entity["TeamId"] = team
        entities.append(entity)
        return entity["Id"]

    for x in range(width):
        for y in range(height):
            add(TERRAIN[grid[(x, y)]], x, y)
    for head, x, y in tokens(level["buildings"]):
        ref.buildings[(x, y)] = add(BUILDINGS[head[0]], x, y, OWNERS[head[1]])
    for head, x, y in tokens(level["units"]):
        ref.units[(x, y)] = add(UNITS[head[0]], x, y, OWNERS[head[1]])

    start = [(x, y) for head, x, y in tokens(level["units"]) if head[1] == "1"][0]
    return {
        "Version": 1,
        "ImportedDefaults": True,
        "Width": width,
        "Height": height,
        "CursorStartingX": start[0],
        "CursorStartingY": start[1],
        "CameraStartingX": 0,
        "CameraStartingY": 0,
        "TeamsConfig": {
            "NumberOfTeams": 2, "StartingTeam": P1, "TurnNumber": 1, "ActiveTeams": [P1, P2],
            "TeamConfig": [{"TeamId": P1, "TeamEntity": "PLAYER", "AiProfile": "Standard"},
                           {"TeamId": P2, "TeamEntity": "AI_DEFAULT", "AiProfile": "Standard"}],
        },
        "EntityConfig": entities,
        "Triggers": flatten(level["triggers"](ref)),
    }


# --- Checks ------------------------------------------------------------------

def known_types():
    names = set()
    for folder in ("unit", "building", "terrain"):
        for file in os.listdir(os.path.join(TYPES, folder)):
            if file.endswith(".json"):
                names.add(json.load(open(os.path.join(TYPES, folder, file)))["Name"])
    return names


def check_map(name, data, types):
    problems = []
    w, h = data["Width"], data["Height"]
    ids = [e["Id"] for e in data["EntityConfig"]]
    terrain, buildings, units = {}, {}, {}
    for e in data["EntityConfig"]:
        pos = (e["Position"]["X"], e["Position"]["Y"])
        if e["Type"] not in types:
            problems.append(f"unknown entity type {e['Type']!r}")
        if not (0 <= pos[0] < w and 0 <= pos[1] < h):
            problems.append(f"{e['Type']} out of bounds at {pos}")
        layer = terrain if e["Type"] in TERRAIN.values() else buildings if e["Type"] in BUILDINGS.values() else units
        if pos in layer:
            problems.append(f"two things of the same kind on {pos}: {layer[pos]['Type']} and {e['Type']}")
        layer[pos] = e
    if len(terrain) != w * h:
        problems.append("not every square has exactly one terrain")

    def can_stand(kind, pos):
        ground = terrain[pos]["Type"]
        if kind in FLIES:
            return True
        if kind in SWIMS:
            return ground in WATER
        return ground != "Ocean"

    for pos, e in buildings.items():
        if terrain[pos]["Type"] in ("Ocean", "Bridge"):
            problems.append(f"{e['Type']} built on water at {pos}")
    for pos, e in units.items():
        if not can_stand(e["Type"], pos):
            problems.append(f"{e['Type']} cannot stand on {terrain[pos]['Type']} at {pos}")

    walkers = [pos for pos, e in units.items() if e.get("TeamId") == P1 and e["Type"] not in SWIMS | FLIES]
    seen, queue = set(walkers[:1]), deque(walkers[:1])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in terrain and nxt not in seen and terrain[nxt]["Type"] != "Ocean":
                seen.add(nxt)
                queue.append(nxt)
    for pos, e in list(buildings.items()) + [(p, u) for p, u in units.items() if u["Type"] not in SWIMS | FLIES]:
        if pos not in seen:
            problems.append(f"{e['Type']} at {pos} cannot be reached on foot from the player's start")

    names = [t["Name"] for t in data["Triggers"] if "Name" in t]
    for dup in {n for n in names if names.count(n) > 1}:
        problems.append(f"two triggers are both called {dup!r}")
    for n, trigger in enumerate(data["Triggers"]):
        for cond in trigger.get("Conditions", []):
            if cond["Type"] not in CONDITIONS:
                problems.append(f"trigger {n}: unknown condition {cond['Type']}")
            selected = cond.get("EntitySelector", {}).get("EntitySelected")
            if selected is not None and selected not in ids:
                problems.append(f"trigger {n}: selects missing entity id {selected}")
            if cond["Type"] == "CURSOR_ENTITY" and cond.get("EntityType") not in types:
                problems.append(f"trigger {n}: unknown entity type {cond.get('EntityType')!r}")
        for action in trigger.get("Actions", []):
            if action["Type"] not in ACTIONS:
                problems.append(f"trigger {n}: unknown action {action['Type']}")
            if action["Type"] == "INSERT_ENTITY":
                pos = (action["Position"]["X"], action["Position"]["Y"])
                if action["EntityType"] not in types:
                    problems.append(f"trigger {n}: inserts unknown type {action['EntityType']!r}")
                elif pos not in terrain or not can_stand(action["EntityType"], pos):
                    problems.append(f"trigger {n}: inserts a {action['EntityType']} where it cannot stand, {pos}")
                elif pos in buildings:
                    problems.append(f"trigger {n}: inserts a unit on top of the {buildings[pos]['Type']} at {pos}")
            if action["Type"] == "SUPPRESS_ENTITIES":
                for kind in action["EntitySelector"].get("AllowEntities", []):
                    if kind not in types:
                        problems.append(f"trigger {n}: allows unknown type {kind!r}")
    return [f"{name}: {p}" for p in problems]


# --- Campaign index and meta -------------------------------------------------

def screenshot_name(file):
    return "screenshots/" + file.replace(".json", "_screenshot.png")


def campaign_json():
    width, height = MAP_PIXELS
    levels, icons, connectors = [], [], []

    def pct(site):                                         # the game measures Y up from the bottom edge
        return {"X": round(site[0] / width * 100, 1), "Y": round((height - site[1]) / height * 100, 1)}

    for n, level in enumerate(LEVELS):
        previous = LEVELS[n - 1]["flag"] if n else None
        unlock = {previous: True} if previous else {}
        levels.append({
            "Name": level["name"], "Description": level["description"], "Summary": level["summary"],
            "DifficultyRating": str(level["difficulty"]), "Terms": level["terms"],
            "MapImageFilePath": screenshot_name(level["file"]), "MapFile": level["file"],
            "UnlockRequirements": unlock, "OnCompletionGlobalSet": {level["flag"]: True},
        })
        icon = {"Level": level["name"], "Position": pct(MAP_SITES[n]), "Title": level["name"],
                "HighlightRequirements": {level["flag"]: False}}
        if unlock:
            icon["UnlockRequirements"] = unlock
            connectors.append({"StartPosition": pct(MAP_SITES[n - 1]), "EndPosition": pct(MAP_SITES[n]),
                               "UnlockRequirements": unlock,
                               "HighlightRequirements": {previous: True, level["flag"]: False}})
        icons.append(icon)
    return {
        "Name": "The Remote Land",
        "Description": "Take the islands for Ashmark, from the first beach to the dragon's spire",
        "Levels": levels,
        "Map": {"MapFile": "campaign_map.png", "IconHighlightAnimation": {"AnimationKey": "BIG_SLOW_PULSE_REPEAT"},
                "ConnectorConfigs": connectors, "IconConfigs": icons},
    }


def previous_versions():
    """filename -> version from the campaign meta as it is on disk, so re-runs keep counting up."""
    path = os.path.join(CAMPAIGN, "meta")
    out = {}
    if os.path.exists(path):
        for line in open(path):
            cols = [c.strip() for c in line.split("|")]
            if len(cols) > 3 and cols[0].isdigit():
                out[cols[2]] = int(cols[0])
    return out


def meta(changed):
    """changed: filenames whose contents differ from what is on disk and so need a new version."""
    old = previous_versions()
    row = "{version:<7} |   {name:<24} |   {file:<44} |   {is_file}       |   /       |   {on_ui}       |   /           |   {action:<15} |   0           |   0       |   {notes}"

    def line(name, file, action, notes, on_ui=0, is_file=1):
        version = old.get(file, 0) + (1 if file in changed or file not in old else 0)
        return row.format(version=version, name=name, file=file, action=action, notes=notes, on_ui=on_ui, is_file=is_file)

    lines = ["version |   name                     |   filename                                     |   isFile  |   path    |   onUi    |   uiPath      |   action          |   subMeta     |   env     |   notes",
             "", line("Campaign", "campaign.json", "loadCampaign", "The Remote Land campaign"),
             "", line("Map", "campaign_map.png", "loadCampaignMap", "Campaign map", on_ui=1), ""]
    lines += [line(level["name"], level["file"], "loadMap", level["name"]) for level in LEVELS]
    lines += [""] + [line(level["name"] + " Preview", screenshot_name(level["file"]), "", level["name"] + " preview")
                     for level in LEVELS]
    lines += ["", line("Intro", "campaignIntro.msg", "message", "Introduction to the Remote Land campaign"),
              "", line("The Remote Land", "", "header", "Take the islands for Ashmark", is_file=0),
              "", line("Saves", "saves", "folder", "Saves", on_ui=1, is_file=0),
              "", line("Restart Campaign", "restartCampaign", "resetCampaign", "Restart the Campaign", on_ui=1, is_file=0)]
    return "\n".join(lines) + "\n"


# --- Pictures ----------------------------------------------------------------

TILE = 40
TEAM_TINT = {P1: (235, 70, 60), P2: (70, 105, 235)}


def load_art():
    """The game's own artwork, cropped the way the sprite configs crop it and shrunk to one tile."""
    from PIL import Image
    art = {}
    for folder, crop in (("terrain", (50, 50, 160, 160)), ("building", (50, 30, 160, 120)), ("unit", None)):
        for file in os.listdir(os.path.join(TYPES, folder)):
            if not file.endswith(".json"):
                continue
            config = json.load(open(os.path.join(TYPES, folder, file)))
            picture = Image.open(os.path.join(TYPES, config["Sprite"]["FilePath"])).convert("RGBA")
            if crop:
                picture = picture.crop(crop)
            art[config["Name"]] = picture.resize((TILE, TILE), Image.LANCZOS)
    return art


def tinted(picture, colour):
    from PIL import Image, ImageChops
    wash = Image.new("RGBA", picture.size, (*colour, 255))
    return Image.blend(picture, ImageChops.multiply(picture, wash), 0.6)


def render_map(data, art):
    from PIL import Image
    w, h = data["Width"], data["Height"]
    im = Image.new("RGBA", (w * TILE, h * TILE), (10, 10, 14, 255))
    order = lambda e: 0 if e["Type"] in TERRAIN.values() else 1 if e["Type"] in BUILDINGS.values() else 2
    for e in sorted(data["EntityConfig"], key=order):
        picture = art[e["Type"]]
        if e.get("TeamId") in TEAM_TINT:
            picture = tinted(picture, TEAM_TINT[e["TeamId"]])
        im.alpha_composite(picture, (e["Position"]["X"] * TILE, (h - 1 - e["Position"]["Y"]) * TILE))
    return im.convert("RGB")


def render_campaign_map():
    """A sea chart of the island chain: four islands, a marked site for every level, and the route."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    width, height = MAP_PIXELS
    rng = np.random.default_rng(23)
    ys, xs = np.mgrid[0:height, 0:width].astype(float)

    def to_segment(a, b):
        ax, ay, bx, by = *a, *b
        dx, dy = bx - ax, by - ay
        u = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (dx * dx + dy * dy or 1), 0, 1)
        return np.hypot(xs - (ax + u * dx), ys - (ay + u * dy))

    def smooth_noise(cell, strength):
        small = rng.random((height // cell + 2, width // cell + 2)).astype("float32")
        return (np.asarray(Image.fromarray(small).resize((width, height), Image.BICUBIC)) - 0.5) * 2 * strength

    wobble = smooth_noise(20, 9) + smooth_noise(7, 4)
    edge = np.minimum.reduce([xs, ys, width - 1 - xs, height - 1 - ys])
    land = np.zeros((height, width), bool)
    owner = np.full((height, width), -1)
    for n, (_, sites, _, _) in enumerate(ISLANDS):
        field = np.full((height, width), 1e9)
        points = [MAP_SITES[s] for s in sites]
        for a, b in zip(points, points[1:] + points[:1]):
            field = np.minimum(field, to_segment(a, b) - 22)
        island = (field + wobble + np.clip(12 - edge, 0, None) * 3) < 0
        island &= ~land
        land |= island
        owner[island] = n

    def grow(mask):
        out = mask.copy()
        out[1:, :] |= mask[:-1, :]
        out[:-1, :] |= mask[1:, :]
        out[:, 1:] |= mask[:, :-1]
        out[:, :-1] |= mask[:, 1:]
        return out

    image = np.zeros((height, width, 3)) + (38, 66, 104)   # the sea, with soundings round every coast
    reach = land.copy()
    for step in range(1, 15):
        wider = grow(reach)
        ring = wider & ~reach
        if step <= 2:
            image[ring] = (112, 160, 178) if step == 1 else (70, 112, 148)
        elif step in (6, 10, 14):
            image[ring] = (52, 84, 124)
        reach = wider
    image[((xs % 52 == 26) | (ys % 52 == 26)) & ~reach] = (44, 74, 114)

    ground = np.zeros((height, width, 3))
    for n, (_, _, _, tint) in enumerate(ISLANDS):
        ground[owner == n] = np.array((176, 190, 128)) * 0.6 + np.array(tint) * 0.4
    ground *= 1 + smooth_noise(26, 0.07)[..., None]
    inner = land & ~grow(~land)
    ground[land & ~inner] = (226, 212, 160)                # beaches
    woods = land & inner & (smooth_noise(9, 1) > 0.45) & ((xs + ys * 2) % 4 == 0)
    ground[woods] *= 0.72
    image[land] = np.clip(ground, 0, 255)[land]

    canvas = Image.fromarray(image.astype("uint8"), "RGB")
    pen = ImageDraw.Draw(canvas)
    pen.fontmode = "1"
    ink, pale = (52, 40, 34), (240, 232, 208)

    peaks = np.argwhere(land & inner & (smooth_noise(11, 1) > 0.5) & (xs % 9 == 4) & (ys % 7 == 3))
    for y, x in peaks:                                     # hills and mountains
        if all(abs(x - sx) > 12 or abs(y - sy) > 12 for sx, sy in MAP_SITES):
            pen.polygon([(x - 3, y + 2), (x, y - 3), (x + 3, y + 2)], fill=(150, 140, 120), outline=ink)
    sx, sy = MAP_SITES[-1]                                 # the spire itself
    pen.polygon([(sx + 8, sy + 6), (sx + 16, sy - 18), (sx + 24, sy + 6)], fill=(110, 100, 100), outline=ink)
    pen.polygon([(sx + 13, sy - 9), (sx + 16, sy - 18), (sx + 19, sy - 9)], fill=pale)

    for a, b in zip(MAP_SITES, MAP_SITES[1:]):             # the route: a track on land, a dotted lane at sea
        length = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])))
        for n in range(length + 1):
            x, y = round(a[0] + (b[0] - a[0]) * n / length), round(a[1] + (b[1] - a[1]) * n / length)
            if land[y, x]:
                if n % 5 < 3:
                    pen.point((x, y), ink)
            elif n % 4 == 0:
                pen.point((x, y), pale)

    font = ImageFont.load_default()
    for name, _, (x, y), tint in ISLANDS:
        shade = tuple(int(c * 0.45) for c in tint) if land[min(y + 5, height - 1), min(x + 8, width - 1)] else pale
        for ch in name:
            pen.text((x, y), ch, fill=shade, font=font)
            x += 8

    for n, (x, y) in enumerate(MAP_SITES):                 # a marked site for every battle
        last = n == len(MAP_SITES) - 1
        for r, colour in ((8, ink), (7, (150, 60, 50) if last else (200, 60, 50)), (5, pale), (2, ink)):
            pen.ellipse((x - r, y - r, x + r, y + r), fill=colour)
    hx, hy = MAP_SITES[0]                                  # an anchor mark where the boats land
    pen.line((hx - 14, hy - 4, hx - 14, hy + 5), fill=pale)
    pen.line((hx - 17, hy + 2, hx - 14, hy + 5, hx - 11, hy + 2), fill=pale)
    pen.line((hx - 16, hy - 2, hx - 12, hy - 2), fill=pale)

    cx, cy = 388, 196                                      # compass
    pen.line((cx, cy - 9, cx, cy + 9), fill=pale)
    pen.line((cx - 9, cy, cx + 9, cy), fill=pale)
    pen.polygon([(cx, cy - 12), (cx - 3, cy - 4), (cx + 3, cy - 4)], fill=pale)
    pen.text((cx - 2, cy - 25), "N", fill=pale, font=font)

    pen.rectangle((0, 0, width - 1, height - 1), outline=ink)
    pen.rectangle((1, 1, width - 2, height - 2), outline=(196, 180, 140))
    return canvas


# --- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate everything but write nothing")
    args = parser.parse_args()

    types = known_types()
    built, problems = {}, []
    for level in LEVELS:
        built[level["file"]] = build_map(level)
        problems += check_map(level["file"], built[level["file"]], types)
    assert len(LEVELS) == len(MAP_SITES) == sum(len(sites) for _, sites, _, _ in ISLANDS)
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Checked {len(LEVELS)} levels: no problems found")
    if args.check:
        return

    os.makedirs(os.path.join(CAMPAIGN, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(CAMPAIGN, "saves"), exist_ok=True)
    art = load_art()
    files = {name: json.dumps(data, indent=2) + "\n" for name, data in built.items()}
    files["campaign.json"] = json.dumps(campaign_json(), indent=4) + "\n"
    files["campaignIntro.msg"] = INTRO
    changed = set()
    for name, text in files.items():
        path = os.path.join(CAMPAIGN, name)
        if not os.path.exists(path) or open(path).read() != text:
            changed.add(name)
            with open(path, "w") as fh:
                fh.write(text)
    pictures = {screenshot_name(name): render_map(data, art) for name, data in built.items()}
    pictures["campaign_map.png"] = render_campaign_map()
    for name, picture in pictures.items():
        path = os.path.join(CAMPAIGN, name)
        from PIL import Image, ImageChops
        same = os.path.exists(path) and Image.open(path).size == picture.size and \
            ImageChops.difference(Image.open(path).convert("RGB"), picture.convert("RGB")).getbbox() is None
        if not same:
            changed.add(name)
            picture.save(path)
    saves_meta = os.path.join(CAMPAIGN, "saves", "meta")
    if not os.path.exists(saves_meta):
        with open(saves_meta, "w") as fh:
            fh.write("version |   name            |   filename                        |   isFile  |   path    |   onUi    |   uiPath      |   action    |   subMeta     |   env     |   notes\n")
    text = meta(changed)
    with open(os.path.join(CAMPAIGN, "meta"), "w") as fh:
        fh.write(text)
    print(f"Wrote {len(built)} levels, campaign.json, the intro, {len(pictures)} pictures and the meta to {CAMPAIGN}")
    print(f"Files changed this run: {len(changed)}")


if __name__ == "__main__":
    main()
