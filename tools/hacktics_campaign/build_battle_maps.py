#!/usr/bin/env python3
"""Builds the Hacktics battle maps: one-off skirmishes where TEAM_1 is always the player.

    python3 tools/hacktics_campaign/build_battle_maps.py            # write the maps, meta and previews
    python3 tools/hacktics_campaign/build_battle_maps.py --check    # validate only, write nothing

Maps go to config/hacktics/version1/maps/battle_maps. RE-RUNNING THIS SCRIPT
OVERWRITES THEM AND THEIR META, so port any in-game edits back here first.

Each map is drawn for one side only and then mirrored, so every team gets the
same ground. "copies" lists the mirrors: flip across x, flip across y, and which
owner each of the drawn owners becomes. Terrain and unit notation is the same as
in build_campaign.py.

"sides" groups the teams. Teams on the same side are allies, everyone else is an
enemy. An enemy team counts as beaten once it has no units left or one of the
player's side holds its Origin; the player wins when every enemy team is beaten,
and loses on losing their own Origin or last unit.
"""
import argparse
import itertools
import json
import os

import build_campaign as bc
from build_campaign import EVERYTHING, TERRAIN, UNITS, held, say, victory

BATTLE_MAPS = os.path.join(bc.VERSION, "maps", "battle_maps")
PREVIEWS = os.path.join(bc.HERE, "battle_map_previews")
TEAMS = {"1": "TEAM_1", "2": "TEAM_2", "3": "TEAM_3", "4": "TEAM_4"}
# Preview colours for the extra teams, taken from the game's team palettes
EXTRA_PALETTES = {
    "TEAM_3": {"L": (128, 0, 128), "M": (128, 0, 128), "D": (0, 128, 128), "K": (128, 128, 0)},
    "TEAM_4": {"L": (255, 191, 204), "M": (153, 102, 51), "D": (102, 153, 51), "K": (51, 102, 153)},
}

SAME = {}
MAPS = [
    dict(
        file="1v1-crossfire.json", title="1v1 - Crossfire", size=(23, 13), sides=["1", "2"],
        brief="One line runs from your Origin to theirs, with an empty Generator on each half and two Compute nodes dead centre.",
        copies=[(False, False, SAME), (True, False, {"1": "2"})],
        terrain="""
            ## 5,9>5,12  5,0>5,2  11,10>11,12  11,0>11,2  9,2  9,10
            O1 1,6
            +1 2,6>4,6  3,7>3,8
            C1 3,9
            +. 5,6>11,6  3,4>3,5  7,7>7,9
            G. 8,6
            C. 3,3  7,10  11,7  11,5
            E. 9,8  9,4
        """,
        units="w1:2,7 w1:2,5 v1:4,7 v1:4,5 d1:0,6 b1:4,6",
    ),
    dict(
        file="1v2-pincer.json", title="1v2 - Pincer", size=(25, 15), sides=["1", "23"],
        brief="Two enemies, north and south, and one line from your Generator that forks toward both. You start richer than either of them. They start with more between them.",
        copies=[(False, False, SAME), (False, True, {"2": "3"})],
        terrain="""
            ## 7,11>7,14  15,9>18,9  17,7>24,8
            O1 1,7
            +1 2,7>5,7  1,8>1,9  4,8>4,9
            G1 6,7
            C1 1,10  4,10
            +. 7,7>12,7  12,8>12,12  13,12>18,12
            G. 15,12
            C. 9,8  12,13
            E. 10,10  16,10  14,7
            O2 22,12
            +2 19,12>21,12  22,10>22,11
            C2 19,13  22,9
        """,
        units="""w1:0,7 b1:7,7 o1:3,7 w1:2,8 v1:5,8 v1:6,8 d1:3,9 n1:5,9
                 w2:21,13 w2:23,12 v2:19,11 v2:20,11 b2:18,12 d2:21,11 n2:20,13 v2:18,11""",
    ),
    dict(
        file="1v3-last-stand.json", title="1v3 - Last Stand", size=(27, 17), sides=["1", "234"],
        brief="Three enemies to the east and a fortified base of your own: six Compute nodes, a Generator at the gate and Encryptors already in your hands. Outlast them, then break out.",
        copies=[(False, False, SAME), (False, True, {"2": "4"})],
        terrain="""
            ## 9,12>10,16  19,11>22,11  0,14>1,16
            O1 2,8
            +1 3,8>6,8  2,9>2,11  5,9>5,10
            G1 7,8
            C1 2,12  5,11  6,9
            E1 8,10
            +. 8,8>21,8  13,9>13,14  14,14>20,14
            G. 12,8
            C. 10,9  13,15  17,13  17,9
            E. 15,11  19,10
            O2 24,14
            +2 21,14>23,14  24,12>24,13
            C2 21,15  24,11
            O3 25,8
            +3 22,8>24,8
            C3 22,9
        """,
        units="""w1:1,8 o1:3,8 b1:8,8 w1:3,9 v1:6,10 v1:7,9 d1:4,9 n1:6,11 f1:8,10 i1:4,10
                 w2:25,14 w2:23,13 v2:21,13 v2:22,13 b2:20,14 d2:23,15 n2:22,15 m2:21,12
                 w3:26,8 b3:21,8 v3:22,10 v3:23,9 d3:24,9 n3:23,10""",
    ),
    dict(
        file="2v2-twin-fronts.json", title="2v2 - Twin Fronts", size=(27, 17), sides=["13", "24"],
        brief="You hold the north-west and your ally the south-west, against two enemies across the map. Two lines run east and one crosses the centre, joining them.",
        copies=[(False, False, SAME), (False, True, {"1": "3"}), (True, False, {"1": "2"}), (True, True, {"1": "4"})],
        terrain="""
            ## 6,14>6,16  10,15>13,16  5,8>8,8
            O1 2,12
            +1 3,12>5,12  2,13>2,14  2,10>2,11
            C1 2,15  4,13
            +. 6,12>13,12  2,8>2,9  13,8>13,11
            G. 9,12
            C. 9,13  13,13  12,8
            E. 11,10  7,10
        """,
        units="w1:3,13 w1:1,12 v1:5,13 v1:5,11 d1:3,11 b1:6,12 n1:4,11",
    ),
    dict(
        file="ffa-four-corners.json", title="Free for all - Four Corners", size=(23, 23), sides=["1", "2", "3", "4"],
        brief="Four Origins, one in each corner, and everyone is your enemy. Lines run round the edge and cross in the middle, where a single Generator is there for whoever can wire it up.",
        copies=[(False, False, SAME), (True, False, {"1": "2"}), (False, True, {"1": "3"}), (True, True, {"1": "4"})],
        terrain="""
            ## 5,6>5,9  6,5>9,5  8,8>9,9
            O1 2,2
            +1 3,2>5,2  2,3>2,5
            C1 4,3  3,4
            +. 6,2>10,2  2,6>2,10  11,3>11,10  3,11>10,11
            G. 11,2  2,11  11,11
            C. 8,3  3,8  10,10
            E. 6,6
        """,
        units="w1:1,2 w1:2,1 v1:4,4 v1:5,3 v1:3,5 d1:1,1 b1:3,3",
    ),
]


# --- Building ----------------------------------------------------------------

def mirrored(cells, size, copies):
    """cells is {(x, y): code}. Returns every copy laid over each other."""
    width, height = size
    out = {}
    for flip_x, flip_y, owners in copies:
        for (x, y), code in cells.items():
            pos = (width - 1 - x if flip_x else x, height - 1 - y if flip_y else y)
            new = code[0] + owners.get(code[1], code[1]) if code != "##" else code
            assert out.get(pos, new) == new, f"mirroring puts both {out[pos]} and {new} on {pos}"
            out[pos] = new
    return out


def build(spec):
    width, height = spec["size"]
    terrain = mirrored(bc.parse_terrain(spec["terrain"]), spec["size"], spec["copies"])
    unit_cells = {}
    for token in spec["units"].split():
        head, where = token.split(":")
        pos = tuple(map(int, where.split(",")))
        assert pos not in unit_cells, f"{spec['file']}: two units drawn on {pos}"
        unit_cells[pos] = head
    units = mirrored(unit_cells, spec["size"], spec["copies"])

    entities, origins = [], {}
    next_id = 1

    def add(kind, x, y, team=None):
        nonlocal next_id
        entity = {"Id": next_id, "Position": {"X": x, "Y": y}, "Type": kind}
        if team:
            entity["TeamId"] = team
        entities.append(entity)
        next_id += 1
        return entity["Id"]

    for x in range(width):
        for y in range(height):
            add("Ground", x, y)
    for (x, y), code in sorted(terrain.items()):
        if code == "##":
            add("Void", x, y)
            continue
        team = TEAMS.get(code[1])
        entity_id = add(TERRAIN[code[0]], x, y, team)
        if code[0] == "O":
            origins[team] = entity_id
    for (x, y), code in sorted(units.items()):
        add(UNITS[code[0]], x, y, TEAMS[code[1]])

    side_of = {TEAMS[t]: n for n, side in enumerate(spec["sides"]) for t in side}
    teams = sorted(side_of)
    assert teams[0] == "TEAM_1" and set(origins) == set(teams), f"{spec['file']}: every team needs one Origin"
    team_config = []
    for team in teams:
        relationships = [f"{other}|{'Ally' if side_of[other] == side_of[team] else 'Enemy'}" for other in teams if other != team]
        team_config.append({"TeamId": team, "TeamEntity": "PLAYER" if team == "TEAM_1" else "AI_DEFAULT",
                            "AiProfile": "Standard", "Relationships": relationships})

    stats = {"EntitiesPurchased": 0, "EntitiesLost": 0, "TotalDamageDone": 0.0, "TotalDamageTaken": 0.0,
             "NumberOfCaptures": 0, "IncomePool": []}
    cursor = [e["Position"] for e in entities if e["Id"] == origins["TEAM_1"]][0]
    return {
        "Version": 1,
        "ImportedDefaults": True,
        "Width": width,
        "Height": height,
        "CursorStartingX": cursor["X"],
        "CursorStartingY": cursor["Y"],
        "CameraStartingX": 0,
        "CameraStartingY": 0,
        "TeamsConfig": {"NumberOfTeams": len(teams), "StartingTeam": "TEAM_1", "TurnNumber": 1, "ActiveTeams": teams,
                        "TeamConfig": team_config},
        "EntityConfig": entities,
        "Stats": {"Battle": {"TotalEntitesCreated": 0, "TotalEntitiesDestroyed": 0},
                  **{team: dict(stats) for team in teams + ["TEAM_UNDEFINED"]}, "TeamConfig": {}},
        "Triggers": triggers(spec, teams, side_of, origins),
    }


def triggers(spec, teams, side_of, origins):
    player = "TEAM_1"
    friends = [t for t in teams if side_of[t] == side_of[player]]
    enemies = [t for t in teams if side_of[t] != side_of[player]]
    wiped = lambda team: {"Type": "TEAM_REMAINING_ENTITIES", "TeamId": team, "EntityTagFilter": "Unit"}
    ally_note = " Your ally fights on without you, but the battle is lost if you fall." if len(friends) > 1 else ""
    out = [
        {"Name": "Brief", "Conditions": [{"Type": "TURN_NUMBER"}], "Actions": [say(
            spec["brief"],
            "A team is beaten when it has no units left or its Origin is captured. Beat every enemy to win. "
            "Lose your own Origin or your last unit and it's over." + ally_note, done="Begin")]},
        {"Name": "AllowUnits", "Conditions": [{"Type": "TURN_NUMBER"}],
         "Actions": [{"Type": "SUPPRESS_ENTITIES", "EntitySelector": {"AllowEntities": EVERYTHING}}]},
    ]
    # every way of beating each enemy: wiped out, or its Origin held by someone on the player's side
    ways = [[wiped(e)] + [held(origins[e], f) for f in friends] for e in enemies]
    for n, combination in enumerate(itertools.product(*ways)):
        out.append(victory(f"Won{n}", list(combination), player))
    out.append(victory("PlayerWipedOut", [wiped(player)], enemies[0]))
    for enemy in enemies:
        out.append(victory(f"PlayerOriginLostTo{enemy}", [held(origins[player], enemy)], enemy))
    return out


def meta(maps):
    header = "version |   name            |   filename                        |   isFile  |   path    |   onUi    |   uiPath      |   action    |   subMeta     |   env     |   notes"
    row = "1       |   {title:<28} |   {file:<28} |   1       |   /       |   1       |   /           |   loadMap     |   0           |   0       |   {notes}"
    lines = [header] + [row.format(title=m["title"], file=m["file"], notes=m["title"] + " battle map") for m in maps]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate everything but write nothing")
    args = parser.parse_args()

    types = bc.known_types()
    built, problems = {}, []
    for spec in MAPS:
        built[spec["file"]] = build(spec)
        problems += bc.check_map(spec["file"], built[spec["file"]], types)
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Checked {len(MAPS)} battle maps: no problems found")
    if args.check:
        return

    os.makedirs(BATTLE_MAPS, exist_ok=True)
    os.makedirs(PREVIEWS, exist_ok=True)
    for name, data in built.items():
        with open(os.path.join(BATTLE_MAPS, name), "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    with open(os.path.join(BATTLE_MAPS, "meta"), "w") as fh:
        fh.write(meta(MAPS))

    art = bc.load_art()
    palettes = {"TEAM_1": art[0].TEAM_PREVIEW["Team 1"], "TEAM_2": art[0].TEAM_PREVIEW["Team 2"], **EXTRA_PALETTES}
    for name, data in built.items():
        picture = bc.render_map(data, art, scale=1, palettes=palettes, face_centre=True)
        picture.save(os.path.join(PREVIEWS, name.replace(".json", ".png")))
    print(f"Wrote {len(built)} maps and their meta to {BATTLE_MAPS}, previews to {PREVIEWS}")


if __name__ == "__main__":
    main()
