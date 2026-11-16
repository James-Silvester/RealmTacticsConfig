#!/usr/bin/env python3
"""Builds the Hacktics campaign: levels 2-10, campaign.json, the campaign map and level previews.

    python3 tools/hacktics_campaign/build_campaign.py            # write everything
    python3 tools/hacktics_campaign/build_campaign.py --check    # validate only, write nothing

Level 1 (the tutorial) is a hand made map and is left alone apart from its preview.
Levels 2-10 are defined below. RE-RUNNING THIS SCRIPT OVERWRITES THEM, so if you
edit one of those maps in the in-game editor, either delete its entry from LEVELS
first or port the change back here.

The maps are built around supply lines. Income only reaches an Origin or Generator
through an unbroken chain of that team's own Connectors, so long Connector lines
are both what you fight to extend and what you capture to starve the other side.
Enemy reinforcements that come "off a Generator" are scripted to stop while any
Connector feeding that Generator is out of enemy hands.

Notation ((0,0) is the bottom left square):
    places   "x,y" is one square, "x0,y0>x1,y1" is every square in that rectangle
             (so also a straight line).
    terrain  one line per kind: a two letter code then any number of places.
             .. ground   ## void   +  connector   C compute   E encryptor   G generator   O origin
             second letter is the owner: . neutral, 1 player, 2 enemy. Later lines overwrite earlier ones.
    units    "w1:3,4" is a player Worker at (3,4).
             w worker  v virus  m worm  f firewall  b brute  d ddos  n botnet  i injector
             t man in the middle  o optimiser  k overclocker  r ransomware
    waves    numbered groups of enemy units ("v:3,4") that triggers can drop in later.
"""
import argparse
import itertools
import json
import os
import sys
import warnings
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VERSION = os.path.join(ROOT, "config", "hacktics", "version1")
CAMPAIGN = os.path.join(VERSION, "maps", "campaign")
TYPES = os.path.join(VERSION, "entities", "types")

TERRAIN = {"#": "Void", "+": "Connector", "C": "Compute", "E": "Encryptor", "G": "Generator", "O": "Origin"}
UNITS = {"w": "Worker", "v": "Virus", "m": "Worm", "f": "Firewall", "b": "Brute", "d": "DDOS", "n": "Botnet",
         "i": "Injector", "t": "Man in the Middle", "o": "Optimiser", "k": "Overclocker", "r": "Ransomware"}
NETWORKED = {"Connector", "Compute", "Encryptor", "Generator", "Origin"}
OWNERS = {"1": "TEAM_1", "2": "TEAM_2", ".": None}
P1, P2, NEUTRAL = "TEAM_1", "TEAM_2", "TEAM_UNDEFINED"
EVERYTHING = ["Worker", "Virus", "Worm", "Firewall", "Brute", "DDOS", "Botnet", "Injector", "Man in the Middle",
              "Optimiser", "Overclocker", "Ransomware"]


# --- Trigger helpers ---------------------------------------------------------

def say(*lines, done="Understood"):
    parts = [{"Text": text, "SubmitActionText": "Next"} for text in lines]
    parts[-1]["SubmitActionText"] = done
    return {"Type": "SEND_NOTIFICATION", "Notifications": parts}


def intro(*lines, done="Let's go"):
    return {"Name": "Intro", "Conditions": [{"Type": "TURN_NUMBER"}], "Actions": [say(*lines, done=done)]}


def hint(name, entity_type, *lines, team=P1, done="Got it", after=None):
    """Fires the first time the cursor lands on one of these entities."""
    conditions = [{"Type": "CURSOR_ENTITY", "EntityType": entity_type, "TeamId": team}]
    if after:
        conditions.append({"Type": "OTHERS_TRIGGERED", "Name": after})
    return {"Name": name, "Conditions": conditions, "Actions": [say(*lines, done=done)]}


def allow(team, *entity_types):
    """Limits what a team can buy to the listed units."""
    return {"Name": "Allow" + team, "Conditions": [{"Type": "TURN_NUMBER"}],
            "Actions": [{"Type": "SUPPRESS_ENTITIES", "TeamId": team,
                         "EntitySelector": {"AllowEntities": list(entity_types)}}]}


def held(entity_id, by):
    """True while that team owns the entity."""
    return {"Type": "ENTITY", "EntitySelector": {"EntitySelected": entity_id}, "CheckIsCaptured": True,
            "CapturedByTeamId": by}


def wave(name, turn, units, *lines, team=P2, done="Brace", fed_by=None):
    """Drops reinforcements in at the start of a team's turn. With fed_by (a list of Connector ids)
    the wave only arrives while that team still owns every one of them: cut the line and it waits."""
    conditions = [{"Type": "TURN_NUMBER", "TurnNumber": turn}, {"Type": "CURRENT_TEAM", "TeamId": team}]
    conditions += [held(link, team) for link in (fed_by or [])]
    actions = [say(*lines, done=done)] if lines else []
    for code, x, y in units:
        actions.append({"Type": "INSERT_ENTITY", "EntityType": UNITS[code], "TeamId": team,
                        "Position": {"X": x, "Y": y}, "TurnEnded": False})
    return {"Name": name, "Conditions": conditions, "Actions": actions}


def on_turn(name, turn, *lines, team=P1, done="Understood"):
    return {"Name": name, "Conditions": [{"Type": "TURN_NUMBER", "TurnNumber": turn},
                                         {"Type": "CURRENT_TEAM", "TeamId": team}], "Actions": [say(*lines, done=done)]}


def when_taken(prefix, links, by, messages, done="Understood"):
    """One notice per Connector in a line, said when that team captures it. The messages rotate,
    because there is no way to say "only the first time any of these is taken"."""
    texts = itertools.cycle(messages)
    return [{"Name": f"{prefix}{n}", "Conditions": [held(link, by)], "Actions": [say(next(texts), done=done)]}
            for n, link in enumerate(links)]


def victory(name, conditions, team):
    return {"Name": name, "Conditions": conditions, "Actions": [{"Type": "TEAM_VICTORY", "TeamId": team}]}


def wiped_out(team, winner):
    return victory(team + "WipedOut", [{"Type": "TEAM_REMAINING_ENTITIES", "TeamId": team, "EntityTagFilter": "Unit"}],
                   winner)


def standard_endings(m, origins_needed=1):
    """Capture their Origin(s) to win, lose yours to lose, and either side loses with no units left."""
    out = [victory("OriginTaken", [held(o, P1) for o in m.origins(P2)[:origins_needed]], P1)]
    if m.origins(P1):
        out.append(victory("OriginLost", [held(m.origins(P1)[0], P2)], P2))
    return out + [wiped_out(P1, P2), wiped_out(P2, P1)]


CUT_THEIRS = ["Echo: That's their line cut. Everything past that Connector just lost its funding.",
              "Echo: Another link gone. Hold it, or they'll send a Worker to stitch the line back together.",
              "Echo: Keep cutting. A Generator with no line behind it is just scenery."]
CUT_OURS = ["Echo: They've taken one of our Connectors. Everything beyond it is cut off from the Origin until you take it back.",
            "Echo: Another link lost. Get a Worker onto it before the rest of the line goes hungry.",
            "Echo: Our line is broken again. Retake that Connector."]

# --- Levels ------------------------------------------------------------------
# "triggers" is given a MapRef so it can look up Origins, Connector lines and waves.

LEVELS = [
    dict(
        file="02-proving-grounds.json", name="Proving Grounds", flag="ProvingGrounds_Complete", difficulty=2,
        description="Learn ranged attackers and heavy close-range units",
        summary="Echo has brought you to the Open Front, a loose band of hackers holding out against CyberCorp. First they want to see what you can do.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(14, 10),
        terrain="""
            ## 6,4>7,5  3,5>3,6  10,3>10,4  10,7>10,8  3,1>3,2
            O1 1,8
            O2 12,1
            E. 5,8  8,1
            +. 5,3  8,6
        """,
        units="w1:1,7 d1:2,8 b1:2,7 v1:3,8   w2:12,2 d2:11,1 b2:11,2 v2:10,1",
        triggers=lambda m: [
            intro("Echo: We've got trouble. We're receiving reports of a CyberCorp attack on one of our key territories.",
                  "Echo: This is your chance to show what you're capable of. I'll be here to provide guidance, but I've got urgent matters to attend to elsewhere.",
                  "Echo: The defence is in your hands now. We're counting on you to program our network to repel the CyberCorp incursion.",
                  "Echo: Remember, you've got the skills and determination to make a difference. Trust your instincts, and let's show CyberCorp what the Open Front is made of."),
            hint("TaughtRange", "DDOS",
                 "DDOS units strike from range but can't move and attack in the same turn, and they fold fast if anything reaches them. Keep them behind your front line."),
            hint("TaughtBrute", "Brute",
                 "Brute Forcers hit hard up close and shrug off damage, but they're slow. Push them in first to soak hits while your DDOS pick off targets from behind.",
                 after="TaughtRange", done="Understood"),
            standard_endings(m),
        ],
    ),
    dict(
        file="03-open-port.json", name="Open Port", flag="OpenPort_Complete", difficulty=2,
        description="Stall one flank with Ransomware while a Worm slips through the other",
        summary="A poorly secured port gives you an opening into CyberCorp territory, but they won't give the ground up easily.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(16, 11),
        terrain="""
            ## 1,4>14,6  5,9  10,8  5,2  10,1
            O1 0,5
            O2 15,5
            +. 8,8  7,2
        """,
        units="w1:0,5 r1:0,2 m1:0,8 v1:1,3   b2:9,2 b2:12,2 v2:11,1 d2:12,8 v2:14,7 w2:15,5",
        triggers=lambda m: [
            intro("A poorly secured port gives you an opening into enemy territory - but they won't give up the ground easily.",
                  "Your Ransomware can't attack, but its presence alone slows every hostile unit nearby. Post it in a corridor and it becomes a wall.",
                  "Your Worm moves fast and can pass straight through occupied squares. Use it to slip past a weaker guard and strike the enemy Origin directly.",
                  done="Let's move"),
            standard_endings(m),
        ],
    ),
    dict(
        file="04-supply-lines.json", name="Supply Lines", flag="SupplyLines_Complete", difficulty=2,
        description="Extend your network along the trunk line, earn income and buy units",
        summary="CyberCorp is starving the Open Front of cycles. Echo wants a supply line of your own before the next push, and theirs cut.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(20, 13),
        terrain="""
            ## 9,9>10,12  9,0>10,3  6,2>6,3  13,9>13,10
            O1 1,6
            +1 2,6>4,6  3,7>3,9
            C1 3,10
            +. 5,6>14,6  3,3>3,5  7,7  12,5  16,3>16,5
            C. 3,2  7,8  12,4  16,2
            E. 9,7  10,5
            O2 18,6
            +2 15,6>17,6  16,7>16,8
            C2 16,9
        """,
        units="w1:2,7 w1:2,5 v1:4,7 v1:4,5 d1:0,6   w2:17,7 w2:17,5 v2:15,7 v2:15,5 d2:19,6 b2:14,6",
        triggers=lambda m: [
            intro("Echo: You've proven you can fight. Now learn to feed a fight. CyberCorp wins wars by out-spending us.",
                  "Echo: One trunk line of Connectors runs across this whole sector, from your Origin to theirs. Each of you owns your own end. The middle is nobody's.",
                  "Echo: Income only counts if an unbroken chain of your Connectors carries it home. Walk Workers down the trunk, capture as you go, and take the Compute nodes that branch off it.",
                  done="On it"),
            allow(P1, "Worker", "Virus", "DDOS", "Brute"),
            allow(P2, "Worker", "Virus", "DDOS", "Brute"),
            hint("TaughtConnector", "Connector",
                 "Nobody owns this Connector yet. Put a Worker on it and capture it to push your network one square further. A Compute node only pays into your Origin if your own Connectors join them without a gap.",
                 team=NEUTRAL),
            hint("TaughtOrigin", "Origin",
                 "Your Origin can buy units with the income its network has banked. A new unit appears on the Origin and can't act until next turn, so move it off before you buy another of the same kind."),
            hint("TaughtEnemyLine", "Connector",
                 "This Connector belongs to CyberCorp. Capture it and every Connector and Compute node beyond it stops paying into their Origin. Lines can be cut as well as built.",
                 team=P2),
            on_turn("EnemyBuilding", 4,
                    "Echo: CyberCorp is working down the trunk from their end. Whoever holds the middle holds the two Compute nodes hanging off it."),
            when_taken("TheirLineCut", m.line("15,6>17,6") + m.line("16,7>16,8"), P1, CUT_THEIRS),
            when_taken("OurLineCut", m.line("2,6>4,6") + m.line("3,7>3,9"), P2, CUT_OURS),
            standard_endings(m),
        ],
    ),
    dict(
        file="05-zombie-horde.json", name="Zombie Horde", flag="ZombieHorde_Complete", difficulty=3,
        description="Hold two gaps with Firewalls and massed Botnets, and keep your own line whole",
        summary="A hijacked swarm of machines is bearing down on an Open Front relay. It only has to stay standing long enough for Echo's trace to finish.",
        terms="Survive until turn 12, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(20, 13),
        terrain="""
            ## 10,0>10,12  6,10>6,12  6,0>6,2  14,10>14,11  14,1>14,2
            .. 10,9  10,3
            O1 1,6
            +1 2,6>7,6  1,7  1,5  5,7  5,5
            G1 8,6
            C1 1,8  1,4  5,8  5,4
            E. 9,9  9,3
            O2 18,6
            +2 15,6>17,6  15,7
            C2 15,8
        """,
        units="""f1:9,9 f1:9,3 n1:7,7 n1:8,7 n1:7,5 n1:8,5 v1:8,8 v1:8,4 d1:6,6 w1:2,7 w1:2,5
                 n2:13,8 n2:13,4 n2:14,9 n2:14,3 n2:14,6 v2:12,6 v2:12,7 v2:12,5""",
        waves={1: "n:17,8 n:17,4 v:16,7 w:16,5", 2: "b:16,6 n:17,9 n:17,3 v:16,5 w:16,4",
               3: "v:17,8 v:17,4 b:16,5 w:17,7 m:16,7"},
        triggers=lambda m: [
            intro("Echo: Bad news. CyberCorp has pointed a botnet at this relay, thousands of hijacked machines moving as one.",
                  "Echo: I'm tracing its controller, but I need until turn 12. The wall of dead space leaves them two ways in. Hold both.",
                  "Echo: Your Generator sits right behind the wall, so anything you buy starts at the front. It only works while the line back to your Origin is whole. They know that too.",
                  done="Hold the line"),
            allow(P1, "Worker", "Virus", "Botnet", "Firewall", "DDOS"),
            allow(P2, "Worker", "Virus", "Botnet"),
            hint("TaughtBotnet", "Botnet",
                 "A lone Botnet barely scratches, and it only reaches targets exactly 3 squares away. Every friendly Botnet within 2 squares multiplies its power, so keep them bunched."),
            hint("TaughtFirewall", "Firewall",
                 "Firewalls can't attack, but they soak up punishment and nothing hostile can walk through them. Park one in a gap and it becomes a door only you can open."),
            hint("TaughtGenerator", "Generator",
                 "A Generator builds units just like an Origin, using the same pool of income, for as long as your own Connectors join the two. If an enemy Worker captures a single link, this Generator has nothing to spend."),
            wave("Wave1", 3, m.wave(1), "Echo: Second wave inbound, and there's a Worker with them. It isn't here to fight. It's here for your Connectors."),
            wave("Wave2", 6, m.wave(2), "Echo: They've brought a Brute to crack your Firewalls. Focus it down before it reaches the wall."),
            wave("Wave3", 9, m.wave(3), "Echo: Trace is nearly there. One more push from them. Watch for the Worm, it will go straight past your Firewalls."),
            when_taken("OurLineCut", m.line("2,6>7,6"), P2, CUT_OURS),
            victory("TraceComplete", [{"Type": "TURN_NUMBER", "TurnNumber": 12}, {"Type": "CURRENT_TEAM", "TeamId": P1}], P1),
            victory("OriginLost", [held(m.origins(P1)[0], P2)], P2),
            wiped_out(P1, P2), wiped_out(P2, P1),
        ],
    ),
    dict(
        file="06-patch-cycle.json", name="Patch Cycle", flag="PatchCycle_Complete", difficulty=3,
        description="Keep a strike team alive long enough to cut the line feeding an enemy Generator",
        summary="Echo's trace leads to a CyberCorp staging server. No reinforcements this time: a strike team, two Workers, and a supply line that needs cutting.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if all your units are destroyed. You cannot buy units here.",
        size=(22, 12),
        terrain="""
            ## 5,8>5,11  5,0>5,3  9,9>12,9  9,2>12,2  14,10>14,11  14,0>14,1  18,8>18,9  18,2>18,3
            E. 7,7  7,4
            G2 11,6
            +2 12,6>19,6  16,7>16,8  16,4>16,5
            C2 16,9  16,3
            E2 13,8  13,4
            O2 20,6
        """,
        units="""w1:0,6 w1:0,5 o1:1,6 k1:1,5 b1:2,6 b1:2,5 v1:3,7 v1:3,4 v1:2,7 d1:1,4 m1:2,8
                 d2:13,8 d2:13,4 f2:10,6 v2:11,7 v2:11,5 b2:15,6 v2:17,7 v2:17,5 w2:20,6 b2:19,7""",
        waves={1: "v:10,7 v:10,5", 2: "b:10,7 v:10,5", 3: "b:10,5 d:11,8", 4: "v:10,7 v:10,5 b:11,4"},
        triggers=lambda m: [
            intro("Echo: The trace paid off. This server is where that botnet took its orders from.",
                  "Echo: There's no Origin of ours here, so nobody is coming to help you. They have a Generator at the front that will keep building for as long as its line back to their Origin holds.",
                  "Echo: So don't fight the Generator. Get a Worker round the side and capture any Connector on that line. I've sent an Optimiser and an Overclocker to keep you moving.",
                  done="Moving in"),
            allow(P2, "Worker", "Virus"),
            hint("TaughtOptimiser", "Optimiser",
                 "The Optimiser repairs a friendly unit up to 4 squares away instead of attacking. It can't move and repair in the same turn, so settle it just behind the fighting."),
            hint("TaughtOverclocker", "Overclocker",
                 "The Overclocker's boost gives friendly units 2 to 5 squares away extra movement this turn. Workers are slow. Boost them and they reach that line a turn sooner."),
            hint("TaughtEnemyDdos", "DDOS",
                 "Those DDOS units sit on Encryptors CyberCorp owns, which makes them tougher. They hit from 3 to 5 squares but nothing closer, so the safest place to stand is right next to them.",
                 team=P2),
            hint("TaughtEnemyGenerator", "Generator",
                 "This Generator is building CyberCorp units on a schedule. It draws on their Origin through the line of Connectors running east from it. Break any one of them and it stops.",
                 team=P2),
            wave("Wave1", 3, m.wave(1), "Echo: Their Generator is awake. Fresh units at the front.", fed_by=m.line("12,6>19,6")),
            wave("Wave2", 6, m.wave(2), "Echo: More off the line. It will not stop on its own.", fed_by=m.line("12,6>19,6")),
            wave("Wave3", 9, m.wave(3), "Echo: Another batch. Where are those Workers?", fed_by=m.line("12,6>19,6")),
            wave("Wave4", 12, m.wave(4), "Echo: They can keep this up longer than you can. Cut the line.", fed_by=m.line("12,6>19,6")),
            when_taken("TheirLineCut", m.line("12,6>19,6"), P1,
                       ["Echo: Line cut. Their Generator just went dark. Hold that Connector and nothing new comes off it.",
                        "Echo: Another link gone. They'd need to retake every one of those to get it running again.",
                        "Echo: Keep going. Their Origin is at the far end of that line."]),
            victory("OriginTaken", [held(m.origins(P2)[0], P1)], P1),
            wiped_out(P1, P2), wiped_out(P2, P1),
        ],
    ),
    dict(
        file="07-slow-poison.json", name="Slow Poison", flag="SlowPoison_Complete", difficulty=4,
        description="Wear down a stronger force with Injectors while two lines are fought over",
        summary="The staging server gave up a name: the Lattice, CyberCorp's private backbone. Its garrison outguns you. Echo suggests you don't fight fair.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(20, 13),
        terrain="""
            ## 8,5>11,7  6,11>6,12  13,0>13,1  14,5>14,7  5,5>5,7
            O1 1,6
            +1 1,7>1,9  2,9>5,9  1,3>1,5  2,3>4,3
            +. 6,9>12,9  5,3>6,3  8,3>14,3
            C. 9,10  10,2
            G. 7,3
            G2 13,9
            +2 14,9>17,9  18,7>18,9  18,3>18,5  15,3>17,3
            E. 7,6  12,6
            O2 18,6
        """,
        units="""i1:3,8 i1:3,4 t1:4,7 t1:4,5 f1:6,9 f1:6,3 r1:3,6 v1:4,8 v1:4,4 w1:2,6 w1:0,6
                 b2:15,8 b2:15,4 v2:14,8 v2:14,4 v2:16,6 d2:17,8 d2:17,4 w2:17,6 v2:12,9 n2:13,10""",
        waves={1: "v:13,8 v:12,10", 2: "b:13,8 d:12,10", 3: "b:17,7 d:19,6 v:17,5"},
        triggers=lambda m: [
            intro("Echo: Welcome to the edge of the Lattice. Count their units, then count yours. Yes. I know.",
                  "Echo: So we cheat. Injectors poison every hostile unit 2 to 5 squares away, every turn, without lifting a finger.",
                  "Echo: Two lines cross this sector, north and south of the dead space. They've already run the northern one up to a Generator. The southern Generator is still up for grabs.",
                  done="Patience, then"),
            allow(P1, "Worker", "Virus", "Firewall", "Injector", "Man in the Middle", "Ransomware", "DDOS"),
            allow(P2, "Worker", "Virus", "Brute", "DDOS"),
            hint("TaughtInjector", "Injector",
                 "The Injector never attacks. Any hostile unit 2 to 5 squares from it simply loses health each turn. It has no defence at all, so one hit will finish it: never leave it exposed."),
            hint("TaughtMitm", "Man in the Middle",
                 "The Man in the Middle is fast and feeble on its own, but its strike grows with every hostile within 2 squares of it. Send it into a crowd, not after a straggler."),
            hint("TaughtRansomware2", "Ransomware",
                 "Remember the Ransomware: every hostile in a straight line from it moves slower. Slower enemies spend longer inside your Injectors' reach."),
            hint("TaughtSouthGenerator", "Generator",
                 "Capture this Generator and the two Connectors between it and your line, and you can build here, halfway to their Origin.",
                 team=NEUTRAL),
            wave("Wave1", 4, m.wave(1), "Echo: Their northern Generator is turning out units. It's fed by the line running back east along the top.",
                 fed_by=m.line("14,9>17,9") + m.line("18,7>18,9")),
            wave("Wave2", 8, m.wave(2), "Echo: More from the north. An Injector parked by that line would make it an expensive place to stand.",
                 fed_by=m.line("14,9>17,9") + m.line("18,7>18,9")),
            wave("Wave3", 11, m.wave(3), "Echo: Heavier units arriving at their Origin itself. That one you can't cut off."),
            when_taken("TheirLineCut", m.line("14,9>17,9") + m.line("18,7>18,9") + m.line("15,3>17,3") + m.line("18,3>18,5"), P1, CUT_THEIRS),
            when_taken("OurLineCut", m.line("2,9>5,9") + m.line("2,3>4,3"), P2, CUT_OURS),
            standard_endings(m),
        ],
    ),
    dict(
        file="08-forward-base.json", name="Forward Base", flag="ForwardBase_Complete", difficulty=4,
        description="A tug of war down one long line, Generator against Generator",
        summary="The Lattice is long and your Origin is a long way behind you. CyberCorp builds at the front. Time you did the same.",
        terms="Capture the enemy Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(24, 13),
        terrain="""
            ## 5,9>5,12  5,0>5,2  11,10>12,12  11,0>12,2  18,9>18,12  18,0>18,2  9,3>9,4  14,8>14,9
            O1 1,6
            +1 2,6>5,6  3,7>3,8
            C1 3,9
            +. 6,6>8,6  10,6>13,6  3,4>3,5  7,7>7,9  16,3>16,5  20,4>20,5
            G. 9,6
            C. 3,3  7,10  12,7  11,5  16,2  20,3
            E. 9,8  14,4
            G2 14,6
            +2 15,6>21,6  20,7>20,8
            C2 20,9
            O2 22,6
        """,
        units="""w1:2,7 w1:2,5 v1:4,7 v1:4,5 b1:5,6 d1:0,6 n1:4,8 n1:4,4
                 w2:21,7 w2:21,5 v2:19,7 v2:19,5 b2:15,6 d2:23,6 n2:15,7 v2:13,6 f2:13,7""",
        waves={1: "v:14,7 n:14,5", 2: "b:14,7 d:15,5 v:14,5", 3: "b:14,5 m:14,7"},
        triggers=lambda m: [
            intro("Echo: One line, end to end. Your Origin on the west, theirs on the east, and two Generators in between.",
                  "Echo: They already hold the eastern Generator and every Connector behind it. The western one is empty, three Connectors from your network.",
                  "Echo: Take it and you build at the front. Then push on: every Connector you take in the middle is one they have to take back, and every one you take behind their Generator shuts it down.",
                  done="Wiring it up"),
            allow(P1, "Worker", "Virus", "DDOS", "Brute", "Botnet", "Firewall", "Worm", "Ransomware", "Optimiser"),
            allow(P2, "Worker", "Virus", "DDOS", "Brute", "Botnet", "Firewall", "Worm"),
            hint("TaughtGenerator", "Generator",
                 "This Generator isn't yours yet. Capture it with a Worker, and make sure every Connector between it and your Origin is yours too, or it will have nothing to spend.",
                 team=NEUTRAL),
            hint("TaughtOwnGenerator", "Generator",
                 "The Generator is on your network. Select it to buy units here instead of marching them up from the Origin. Lose a Connector in the chain and it goes quiet again."),
            hint("TaughtBranch", "Compute",
                 "Compute nodes hang off the line on short branches. Capture the branch Connectors as well as the node, or its income has no way home.",
                 team=NEUTRAL),
            wave("Wave1", 4, m.wave(1), "Echo: Their Generator just lit up. That's what yours could be doing.", fed_by=m.line("15,6>21,6")),
            wave("Wave2", 8, m.wave(2), "Echo: More off their line. Seven Connectors feed that Generator. You only need one.", fed_by=m.line("15,6>21,6")),
            wave("Wave3", 12, m.wave(3), "Echo: Still building. Send a Worm to clear the way and a Worker to do the cutting.", fed_by=m.line("15,6>21,6")),
            when_taken("TheirLineCut", m.line("15,6>21,6"), P1, CUT_THEIRS),
            when_taken("OurLineCut", m.line("2,6>5,6") + m.line("6,6>8,6"), P2, CUT_OURS),
            standard_endings(m),
        ],
    ),
    dict(
        file="09-zero-day.json", name="Zero Day", flag="ZeroDay_Complete", difficulty=5,
        description="Two enemy Origins feed one Generator. Cut both lines, take both Origins",
        summary="Two CyberCorp Origins guard the last junction before the core. They cover each other. Echo has found a flaw nobody has patched, and it won't stay secret for long.",
        terms="Capture both enemy Origins, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(24, 15),
        terrain="""
            ## 10,10>11,14  10,0>11,4  17,6>23,8  7,12>7,13  7,1>7,2
            O1 1,7
            +1 2,7>4,7  1,8  1,6
            C1 1,9  1,5
            +. 5,7>7,7  9,7>12,7  5,8>5,9  5,5>5,6
            G. 8,7
            C. 5,10  5,4
            G2 13,7
            +2 14,2>14,12  15,12>20,12  15,2>20,2
            C2 17,13  17,1
            O2 21,12  21,2
            E. 12,9  12,5  16,10  16,4
        """,
        units="""w1:0,7 w1:0,8 v1:4,8 v1:4,6 b1:4,7 b1:3,6 d1:0,6 d1:3,9 n1:4,9 n1:5,8 o1:3,7 m1:4,5 k1:0,9
                 w2:21,12 v2:16,11 v2:15,11 b2:15,13 d2:19,13 n2:16,13 n2:13,12 f2:13,11
                 w2:21,2 v2:16,3 v2:15,3 b2:15,1 d2:19,1 i2:18,1 r2:13,3 f2:13,2 n2:16,1
                 v2:13,8 v2:13,6 b2:12,7""",
        waves={1: "v:12,8 m:13,9", 2: "v:12,6 m:13,5", 3: "b:12,8 d:13,9", 4: "b:12,6 d:13,5", 5: "b:20,11 b:20,3"},
        triggers=lambda m: [
            intro("Echo: Two Origins, north and south. See the line running between them? It passes a Generator in the middle, pointed straight at you.",
                  "Echo: That Generator draws on both Origins at once. Cut the northern line and the southern one still feeds it. You need both.",
                  "Echo: I've found a hole in their handshake that nobody has patched. A zero day. They will notice. Everything we've built is yours to spend here.",
                  done="Both of them"),
            allow(P1, *EVERYTHING),
            allow(P2, "Worker", "Virus", "Brute", "DDOS", "Botnet", "Worm", "Firewall"),
            hint("TaughtZeroDayGenerator", "Generator",
                 "This empty Generator is one Connector from your network. Capture it first and you have a second place to build from, three squares nearer the fight.",
                 team=NEUTRAL),
            wave("North1", 5, m.wave(1), "Echo: They've seen the hole. The Generator is building off the northern line.",
                 fed_by=m.line("14,8>14,12") + m.line("15,12>20,12")),
            wave("South1", 5, m.wave(2), "Echo: And off the southern line. Worms on both sides, heading for your Workers.",
                 fed_by=m.line("14,2>14,6") + m.line("15,2>20,2")),
            wave("North2", 9, m.wave(3), "Echo: Heavier units from the north line. Cut it anywhere along the top.",
                 fed_by=m.line("14,8>14,12") + m.line("15,12>20,12")),
            wave("South2", 9, m.wave(4), "Echo: The same again from the south.",
                 fed_by=m.line("14,2>14,6") + m.line("15,2>20,2")),
            wave("LastStand", 13, m.wave(5), "Echo: The patch is being written as we speak. Brutes at both Origins. Finish this."),
            when_taken("NorthCut", m.line("14,8>14,12") + m.line("15,12>20,12"), P1,
                       ["Echo: Northern line cut. Half that Generator's supply is gone.",
                        "Echo: Another northern link. Hold them.", "Echo: The north is coming apart. Keep at it."]),
            when_taken("SouthCut", m.line("14,2>14,6") + m.line("15,2>20,2"), P1,
                       ["Echo: Southern line cut. With both down, that Generator is finished.",
                        "Echo: Another southern link. Hold them.", "Echo: The south is coming apart. Keep at it."]),
            when_taken("OurLineCut", m.line("2,7>4,7") + m.line("5,7>7,7"), P2, CUT_OURS),
            standard_endings(m, origins_needed=2),
        ],
    ),
    dict(
        file="10-root-access.json", name="Root Access", flag="RootAccess_Complete", difficulty=5,
        description="Starve the walled core by cutting the three lines that feed it, then take it",
        summary="The core of the Lattice: one Origin behind a wall of dead space. Three lines run out through three gates. Echo says this is what you were chosen for.",
        terms="Capture the core Origin, or destroy every enemy unit.\nYou lose if your Origin is captured or all your units are destroyed.",
        size=(26, 17),
        terrain="""
            ## 13,3>23,3  13,13>23,13  13,3>13,13  23,3>23,13  7,10>8,11  7,5>8,6
            .. 13,8  18,13  18,3
            O1 1,8
            +1 2,8>4,8  1,9>1,10  1,6>1,7
            G1 5,8
            C1 1,11  1,5
            +. 6,8>9,8  4,9>4,12  4,4>4,7  9,9>9,12  9,4>9,7
            C. 4,13  4,3  9,13  9,3
            G2 10,8
            +2 11,8>17,8  18,9>18,14  18,2>18,7
            C2 18,15  18,1
            O2 18,8
            E. 8,13  8,3
            E2 16,10  16,6  20,10  20,6
        """,
        units="""w1:0,8 w1:0,7 w1:2,9 b1:6,8 b1:6,7 v1:5,9 v1:5,7 v1:3,9 d1:3,7 d1:2,7 o1:3,10 k1:3,6 m1:6,9 t1:6,6
                 n1:5,10 n1:5,6 i1:2,10 r1:2,6
                 f2:13,8 f2:18,13 f2:18,3 b2:10,9 v2:10,7 v2:11,9 d2:12,7 n2:11,7
                 b2:15,9 b2:15,7 d2:16,10 d2:16,6 d2:20,10 d2:20,6 v2:17,9 v2:17,7 v2:19,11 v2:19,5 i2:20,8
                 n2:21,9 n2:21,7 r2:16,8 w2:18,8 v2:17,15 v2:19,15 n2:17,14 v2:19,1 n2:17,2""",
        waves={1: "v:9,9 v:9,7 w:11,10", 2: "b:9,9 m:9,7 w:11,6", 3: "b:9,7 d:11,10 v:9,9",
               4: "m:19,14 v:20,14", 5: "m:19,2 v:20,2", 6: "b:19,9 b:19,7", 7: "b:17,10 d:19,8 v:17,6"},
        triggers=lambda m: [
            intro("Echo: There it is. The root of the Lattice. Every CyberCorp process answers to that Origin.",
                  "Echo: Three lines leave the wall. West, through the gate facing you, to a Generator on your doorstep. North and south, through the gaps, to the Compute that pays for everything inside.",
                  "Echo: A Firewall plugs each gate, but the lines outside the wall are in the open. Cut them and the core starves. I chose you for this before you knew my name.",
                  done="For the Open Front"),
            allow(P1, *EVERYTHING),
            allow(P2, "Worker", "Virus", "Brute", "DDOS", "Botnet", "Worm", "Firewall", "Injector"),
            hint("TaughtGate", "Firewall",
                 "A Firewall in a gate stops your units walking through it, but not a Worm, which slips past occupied squares. Otherwise it has to be destroyed.",
                 team=P2),
            wave("West1", 4, m.wave(1), "Echo: Their outer Generator is building, and one of those is a Worker. It's coming for your line.",
                 fed_by=m.line("11,8>17,8")),
            wave("West2", 8, m.wave(2), "Echo: More from the outer Generator. Its line runs back through the west gate.",
                 fed_by=m.line("11,8>17,8")),
            wave("West3", 12, m.wave(3), "Echo: That Generator again. Take a Connector between it and the gate and it stops.",
                 fed_by=m.line("11,8>17,8")),
            wave("NorthRaid", 6, m.wave(4), "Echo: Raiders leaving the north Compute, circling the wall toward your branches.",
                 fed_by=m.line("18,9>18,14")),
            wave("SouthRaid", 6, m.wave(5), "Echo: And from the south. Leave something at home.",
                 fed_by=m.line("18,2>18,7")),
            wave("Core1", 10, m.wave(6), "Echo: The core is committing its reserve. You're costing them more than they planned for."),
            wave("Core2", 14, m.wave(7), "Echo: This is everything they have left. Break it and the door is open."),
            when_taken("WestCut", m.line("11,8>17,8"), P1,
                       ["Echo: West line cut. Their outer Generator is dead weight now.",
                        "Echo: Another western link. The gate is next.", "Echo: Keep pulling that line apart."]),
            when_taken("NorthCut", m.line("18,9>18,14"), P1,
                       ["Echo: North line cut. That Compute no longer pays the core.",
                        "Echo: Another northern link gone.", "Echo: The north line is in pieces."]),
            when_taken("SouthCut", m.line("18,2>18,7"), P1,
                       ["Echo: South line cut. The core just got poorer.",
                        "Echo: Another southern link gone.", "Echo: The south line is in pieces."]),
            when_taken("OurLineCut", m.line("2,8>4,8") + m.line("6,8>9,8"), P2, CUT_OURS),
            standard_endings(m),
        ],
    ),
]

# The hand made tutorial, as it appears in campaign.json
EXISTING = [
    dict(file="01-enter-the-nexus.json", name="Enter the Nexus", flag="EnterTheNexus_Complete", difficulty=1,
         description="Learn to move, capture and attack",
         summary="As you sift through the dusty files of an old computer system, a glitch in the code catches your eye. Curiosity piqued, you delve deeper...",
         terms="Capture the Encryptor, then destroy the enemy Virus.\nYou lose if all your units are destroyed."),
]

# The campaign map is an overview chart of the whole battleground, not a battle. Each level has a
# site on it, given in map pixels (x from the left, y from the top). The first OPEN_FRONT_SITES of
# them lie in Open Front territory, the rest inside CyberCorp's Lattice, and the last one is the core.
MAP_PIXELS = (416, 224)
MAP_SITES = [(34, 176), (84, 140), (58, 84), (128, 58), (168, 112), (212, 160), (252, 96), (296, 140), (336, 76),
             (382, 118)]
OPEN_FRONT_SITES = 5


# --- Building maps -----------------------------------------------------------

def places(spec):
    if ">" in spec:
        a, b = spec.split(">")
        (x0, y0), (x1, y1) = (map(int, a.split(",")), map(int, b.split(",")))
        return [(x, y) for x in range(min(x0, x1), max(x0, x1) + 1) for y in range(min(y0, y1), max(y0, y1) + 1)]
    x, y = map(int, spec.split(","))
    return [(x, y)]


def parse_terrain(text):
    cells = {}
    for line in text.strip().splitlines():
        code, *specs = line.split()
        for spec in specs:
            for pos in places(spec):
                if code == "..":
                    cells.pop(pos, None)
                else:
                    cells[pos] = code
    return cells


def parse_units(text, team_given=True):
    out = []
    for token in text.split():
        head, where = token.split(":")
        x, y = map(int, where.split(","))
        out.append((head[0], OWNERS[head[1]] if team_given else None, x, y))
    return out


class MapRef:
    """What a level's triggers can look up about its own map."""

    def __init__(self, level):
        self.terrain_ids, self.origin_ids, self.level = {}, {P1: [], P2: []}, level

    def origins(self, team):
        return self.origin_ids[team]

    def line(self, spec):
        missing = [pos for pos in places(spec) if pos not in self.terrain_ids]
        assert not missing, f"{self.level['file']}: no terrain at {missing} for line {spec}"
        return [self.terrain_ids[pos] for pos in places(spec)]

    def wave(self, number):
        return [(code, x, y) for code, _, x, y in parse_units(self.level["waves"][number], team_given=False)]


def flatten(items):
    out = []
    for item in items:
        out.extend(flatten(item) if isinstance(item, list) else [item])
    return out


def build_map(level):
    width, height = level["size"]
    terrain = parse_terrain(level["terrain"])
    units = parse_units(level["units"])
    ref = MapRef(level)
    entities = []
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
        team = OWNERS[code[1]]
        ref.terrain_ids[(x, y)] = add(TERRAIN[code[0]], x, y, team)
        if code[0] == "O":
            ref.origin_ids[team].append(ref.terrain_ids[(x, y)])
    for code, team, x, y in units:
        add(UNITS[code], x, y, team)

    cursor = level.get("cursor")
    if not cursor:
        mine = [pos for pos, code in sorted(terrain.items()) if code == "O1"] or \
               [(x, y) for _, team, x, y in units if team == P1]
        cursor = mine[0]
    stats = {"EntitiesPurchased": 0, "EntitiesLost": 0, "TotalDamageDone": 0.0, "TotalDamageTaken": 0.0,
             "NumberOfCaptures": 0, "IncomePool": []}
    return {
        "Version": 1,
        "ImportedDefaults": True,
        "Width": width,
        "Height": height,
        "CursorStartingX": cursor[0],
        "CursorStartingY": cursor[1],
        "CameraStartingX": 0,
        "CameraStartingY": 0,
        "TeamsConfig": {
            "NumberOfTeams": 2, "StartingTeam": P1, "TurnNumber": 1, "ActiveTeams": [P1, P2],
            "TeamConfig": [{"TeamId": P1, "TeamEntity": "PLAYER", "AiProfile": "Standard"},
                           {"TeamId": P2, "TeamEntity": "AI_DEFAULT", "AiProfile": "Standard"}],
        },
        "EntityConfig": entities,
        "Stats": {"Battle": {"TotalEntitesCreated": 0, "TotalEntitiesDestroyed": 0}, P1: dict(stats), P2: dict(stats),
                  NEUTRAL: dict(stats), "TeamConfig": {}},
        "Triggers": flatten(level["triggers"](ref)),
    }


# --- Checks ------------------------------------------------------------------

def known_types():
    names = set()
    for folder in ("units", "terrain"):
        for file in os.listdir(os.path.join(TYPES, folder)):
            if file.endswith(".json"):
                names.add(json.load(open(os.path.join(TYPES, folder, file)))["Name"])
    return names

CONDITIONS = {"CURRENT_TEAM", "CURSOR_ENTITY", "CURSOR_POSITION", "ENTITY_POSITION", "ENTITY", "OTHERS_TRIGGERED",
              "TEAM_REMAINING_ENTITIES", "TURN_NUMBER", "CAMPAIGN_PROGRESS"}
ACTIONS = {"INSERT_ENTITY", "MOVE_CURSOR", "SEND_NOTIFICATION_CHARACTER", "SEND_NOTIFICATION", "TEAM_VICTORY",
           "START_AUDIO", "SUPPRESS_ENTITIES", "SET_CAMPAIGN_PROGRESS"}


def check_map(name, data, types):
    problems = []
    w, h = data["Width"], data["Height"]
    live = [e for e in data["EntityConfig"] if not e.get("Destroyed")]
    ids = [e["Id"] for e in data["EntityConfig"] if "Id" in e]
    if len(ids) != len(set(ids)):
        problems.append("duplicate entity ids")
    void, units, terrain = set(), {}, {}
    for e in live:
        pos = (e["Position"]["X"], e["Position"]["Y"])
        if e["Type"] not in types:
            problems.append(f"unknown entity type {e['Type']!r}")
        if not (0 <= pos[0] < w and 0 <= pos[1] < h):
            problems.append(f"{e['Type']} out of bounds at {pos}")
        if e["Type"] == "Void":
            void.add(pos)
        elif e["Type"] in UNITS.values():
            if pos in units:
                problems.append(f"two units on {pos}")
            units[pos] = e
        elif e["Type"] != "Ground":
            if pos in terrain:
                problems.append(f"two terrain pieces on {pos}")
            terrain[pos] = e
    for pos in units:
        if pos in void:
            problems.append(f"unit standing in the void at {pos}")
    for pos in terrain:
        if pos in void:
            problems.append(f"terrain overlapping void at {pos}")

    def spread(starts, passable):
        seen, queue = set(starts), deque(starts)
        while queue:
            x, y = queue.popleft()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nxt[0] < w and 0 <= nxt[1] < h and nxt not in seen and passable(nxt):
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    origins = {pos: e for pos, e in terrain.items() if e["Type"] == "Origin"}
    mine = [pos for pos, e in units.items() if e.get("TeamId") == P1]
    if mine:
        walkable = spread(mine[:1], lambda p: p not in void)
        for pos, e in origins.items():
            if e.get("TeamId") == P2 and pos not in walkable:
                problems.append(f"enemy Origin at {pos} cannot be walked to")
        for pos in mine:
            if pos not in walkable:
                problems.append(f"player unit at {pos} is walled off from the rest")

    # every Compute and Generator should be able to join a network that has an Origin on it,
    # and everything a team owns at the start should already be joined to its own Origin
    networked = lambda p: p in terrain and terrain[p]["Type"] in NETWORKED
    wired = spread(list(origins), networked)
    for pos, e in terrain.items():
        if e["Type"] in ("Compute", "Generator") and origins and pos not in wired:
            problems.append(f"{e['Type']} at {pos} can never be wired to an Origin")
    for team in (P1, P2):
        home = [pos for pos, e in origins.items() if e.get("TeamId") == team]
        joined = spread(home, lambda p: networked(p) and terrain[p].get("TeamId") == team)
        for pos, e in terrain.items():
            if home and e.get("TeamId") == team and e["Type"] in ("Connector", "Compute", "Generator") and pos not in joined:
                problems.append(f"{team} starts with a {e['Type']} at {pos} that is not joined to its Origin")

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
            if cond["Type"] in ("CURSOR_ENTITY", "ENTITY_POSITION") and "EntityType" in cond and cond["EntityType"] not in types:
                problems.append(f"trigger {n}: unknown entity type {cond['EntityType']!r}")
            if cond["Type"] == "OTHERS_TRIGGERED" and cond.get("Name") not in names:
                problems.append(f"trigger {n}: waits on a trigger that does not exist, {cond.get('Name')!r}")
        for action in trigger.get("Actions", []):
            if action["Type"] not in ACTIONS:
                problems.append(f"trigger {n}: unknown action {action['Type']}")
            if action["Type"] == "INSERT_ENTITY":
                pos = (action["Position"]["X"], action["Position"]["Y"])
                if action["EntityType"] not in types:
                    problems.append(f"trigger {n}: inserts unknown type {action['EntityType']!r}")
                if not (0 <= pos[0] < w and 0 <= pos[1] < h) or pos in void:
                    problems.append(f"trigger {n}: inserts a unit somewhere it cannot stand, {pos}")
            if action["Type"] == "SUPPRESS_ENTITIES":
                for kind in action["EntitySelector"].get("AllowEntities", []):
                    if kind not in types:
                        problems.append(f"trigger {n}: allows unknown type {kind!r}")
    return [f"{name}: {p}" for p in problems]


# --- Campaign index ----------------------------------------------------------

def screenshot_name(file):
    return "screenshots/" + file.replace(".json", "_screenshot.png")


def campaign_json(levels):
    out_levels, icons, connectors = [], [], []
    width, height = MAP_PIXELS

    def pct(site):                                         # the game measures Y up from the bottom edge
        return {"X": round(site[0] / width * 100, 1), "Y": round((height - site[1]) / height * 100, 1)}

    for n, level in enumerate(levels):
        previous = levels[n - 1]["flag"] if n else None
        unlock = {previous: True} if previous else {}
        out_levels.append({
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
        "Name": "Hacktics Campaign",
        "Description": "Fight for the Open Front, from your first capture to the root of the Lattice",
        "Levels": out_levels,
        "Map": {"MapFile": "campaign_map.png", "IconHighlightAnimation": {"AnimationKey": "BIG_SLOW_PULSE_REPEAT"},
                "ConnectorConfigs": connectors, "IconConfigs": icons},
    }


# --- Pictures ----------------------------------------------------------------

def load_art():
    sys.path.insert(0, os.path.join(ROOT, "PixelArt", "HackticsUnits"))
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import generate_terrain as terrain_art
    import generate_units as unit_art
    tiles = {name.capitalize(): terrain_art.TILES[name](0).image() for name in terrain_art.TILES}
    sprite_keys = {"Brute": "bruteforcer", "Man in the Middle": "maninthemiddle"}
    sprites = {name: unit_art.UNITS[sprite_keys.get(name, name.lower())](0).image() for name in UNITS.values()}
    return unit_art, tiles, sprites


def render_map(data, art, scale=2):
    """Draws a map from its json the way it looks at the start of the battle."""
    from PIL import Image
    unit_art, tiles, sprites = art
    teams = {P1: unit_art.TEAM_PREVIEW["Team 1"], P2: unit_art.TEAM_PREVIEW["Team 2"]}
    w, h = data["Width"], data["Height"]
    im = Image.new("RGBA", (w * 32, h * 32))
    live = [e for e in data["EntityConfig"] if not e.get("Destroyed")]
    order = lambda e: 0 if e["Type"] == "Ground" else 2 if e["Type"] in sprites else 1
    for e in sorted(live, key=order):
        sprite = tiles.get(e["Type"]) or sprites.get(e["Type"])
        if sprite is None:
            continue
        team = e.get("TeamId")
        if team in teams:
            sprite = unit_art.recolour(sprite, teams[team])
            if team == P2 and e["Type"] in sprites:
                sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
        im.alpha_composite(sprite, (e["Position"]["X"] * 32, (h - 1 - e["Position"]["Y"]) * 32))
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def render_campaign_map():
    """Draws the overview chart: a landmass of circuit board in dead space, Open Front ground to the
    west and the Lattice to the east, a marked site for every level and the route between them."""
    import random
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    width, height = MAP_PIXELS
    rng = np.random.default_rng(11)
    ys, xs = np.mgrid[0:height, 0:width].astype(float)
    core = MAP_SITES[-1]

    def to_segment(a, b):
        ax, ay, bx, by = *a, *b
        dx, dy = bx - ax, by - ay
        u = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (dx * dx + dy * dy or 1), 0, 1)
        return np.hypot(xs - (ax + u * dx), ys - (ay + u * dy))

    def smooth_noise(cell, strength):
        small = rng.random((height // cell + 2, width // cell + 2)).astype("float32")
        big = Image.fromarray(small).resize((width, height), Image.BICUBIC)
        return (np.asarray(big) - 0.5) * 2 * strength

    # --- the land: a band around the route, some extra bulk, ragged edges, and the core on its own island
    field = np.full((height, width), 1e9)
    for a, b in zip(MAP_SITES[:-2], MAP_SITES[1:-1]):
        field = np.minimum(field, to_segment(a, b) - 30)
    for x, y, r in ((112, 178, 34), (150, 150, 26), (252, 172, 26), (300, 66, 24), (200, 62, 22), (96, 40, 18),
                    (36, 120, 20), (330, 150, 20)):
        field = np.minimum(field, np.hypot(xs - x, ys - y) - r)
    field += smooth_noise(22, 11) + smooth_noise(7, 4)
    edge = np.minimum.reduce([xs, ys, width - 1 - xs, height - 1 - ys])
    field += np.clip(13 - edge, 0, None) * 3
    land = field < 0
    moat = np.hypot(xs - core[0], ys - core[1])
    land &= moat > 30                                      # dead space all the way round the core
    land |= moat + smooth_noise(9, 2.5) < 21
    land |= to_segment(MAP_SITES[-2], core) < 5.0          # one causeway across
    for x, y in MAP_SITES:
        land |= np.hypot(xs - x, ys - y) < 12

    def grow(mask):
        out = mask.copy()
        out[1:, :] |= mask[:-1, :]
        out[:-1, :] |= mask[1:, :]
        out[:, 1:] |= mask[:, :-1]
        out[:, :-1] |= mask[:, 1:]
        return out

    # --- dead space, with depth rings following the coast the way a sea chart does
    image = np.zeros((height, width, 3)) + (11, 11, 24)
    lines = ((xs % 52 == 26) | (ys % 52 == 26)) & ~land
    image[lines] = (17, 17, 36)
    reach = land.copy()
    for step in range(1, 14):
        wider = grow(reach)
        ring = wider & ~reach
        if step == 1:
            image[ring] = (4, 4, 10)
        elif step in (5, 9, 13):
            image[ring] = (30, 28, 58) if step == 5 else (22, 21, 46)
        reach = wider
    stars = (rng.random((height, width)) > 0.9965) & ~reach
    image[stars] = (58, 34, 104)

    # --- the land itself, tinted by whoever holds the nearest site
    nearest = np.argmin(np.stack([np.hypot(xs - x, ys - y) for x, y in MAP_SITES]), axis=0)
    ours = nearest < OPEN_FRONT_SITES
    plate = np.array((186, 197, 191.0))
    ground = np.where(ours[..., None], plate * 0.72 + np.array((222, 138, 96)) * 0.28,
                      plate * 0.72 + np.array((132, 186, 74)) * 0.28)
    ground *= 1 + smooth_noise(30, 0.05)[..., None]
    dots = (xs % 8 == 4) & (ys % 8 == 4)
    ground[dots] *= 0.9

    walker = random.Random(5)                              # board traces wandering off to small pads
    trace = np.zeros((height, width), bool)
    pads = []
    directions = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    for _ in range(90):
        x, y = walker.randrange(8, width - 8), walker.randrange(8, height - 8)
        d = walker.randrange(8)
        for leg in range(2):
            for _ in range(walker.randrange(6, 20)):
                near_site = any(abs(x - sx) < 13 and abs(y - sy) < 13 for sx, sy in MAP_SITES)
                if not land[y, x] or near_site or not (4 < x < width - 5 and 4 < y < height - 5):
                    break
                trace[y, x] = True
                x, y = x + directions[d][0], y + directions[d][1]
            d = (d + walker.choice((-1, 1))) % 8
        if land[y, x]:
            pads.append((x, y))
    ground[trace] *= 0.86
    for x, y in pads:
        ground[y - 1:y + 1, x - 1:x + 1] *= 0.7

    inner = land & ~grow(~land)                            # bevelled coast
    coast = land & ~inner
    lit = coast & (~np.roll(land, 1, 0) | ~np.roll(land, 1, 1))
    ground[coast] *= 0.78
    ground[lit] *= 1.5
    image[land] = np.clip(ground, 0, 255)[land]

    border = land & (ours != np.roll(ours, 1, 1)) | land & (ours != np.roll(ours, 1, 0))   # the front line
    dashes = ((xs + ys) // 3 % 2 == 0)
    image[border & dashes] = (236, 232, 244)
    image[grow(border) & ~border & land & dashes] = (60, 40, 96)

    canvas = Image.fromarray(image.astype("uint8"), "RGB")
    pen = ImageDraw.Draw(canvas)
    pen.fontmode = "1"                                     # hard edged lettering, no smoothing
    steel, pale = (40, 42, 50), (208, 216, 210)

    for a, b in zip(MAP_SITES, MAP_SITES[1:]):             # the campaign route, site to site
        length = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])))
        for n in range(length + 1):
            if n % 5 < 3:
                x, y = a[0] + (b[0] - a[0]) * n / length, a[1] + (b[1] - a[1]) * n / length
                pen.point((round(x), round(y)), steel)

    font = ImageFont.load_default()                        # region names, spaced out like a chart

    def label(text, x, y, colour):
        for ch in text:
            pen.text((x, y), ch, fill=colour, font=font)
            x += 8
    label("OPEN FRONT", 50, 190, (122, 70, 52))
    label("THE LATTICE", 222, 118, (64, 104, 44))
    label("DEAD SPACE", 300, 196, (52, 44, 96))

    def disc(x, y, r, colour):
        pen.ellipse((x - r, y - r, x + r, y + r), fill=colour)

    for n, (x, y) in enumerate(MAP_SITES):                 # a marked site for every battle
        colour = (217, 128, 89) if n < OPEN_FRONT_SITES else (150, 205, 40)
        last = n == len(MAP_SITES) - 1
        if last:                                           # the core gets a wall with three gates
            pen.rectangle((x - 13, y - 13, x + 13, y + 13), outline=steel, width=2)
            for gx, gy in ((x - 13, y), (x, y - 13), (x, y + 13)):
                pen.rectangle((gx - 2, gy - 2, gx + 2, gy + 2), fill=tuple(int(c) for c in image[y, x - 8]))
        disc(x, y, 8, steel)
        disc(x, y, 7, colour)
        disc(x, y, 5, pale)
        disc(x, y, 2, (147, 74, 221) if last else steel)
        pen.point((x - 3, y - 3), (255, 255, 255))
    hx, hy = MAP_SITES[0]                                  # home marker on the first site
    pen.polygon([(hx - 4, hy - 11), (hx, hy - 15), (hx + 4, hy - 11)], fill=steel)

    cx, cy = 26, 30                                        # compass
    pen.line((cx, cy - 9, cx, cy + 9), fill=(120, 110, 170))
    pen.line((cx - 9, cy, cx + 9, cy), fill=(120, 110, 170))
    pen.polygon([(cx, cy - 12), (cx - 3, cy - 4), (cx + 3, cy - 4)], fill=(190, 180, 230))
    pen.text((cx - 2, cy - 25), "N", fill=(190, 180, 230), font=font)

    pen.rectangle((0, 0, width - 1, height - 1), outline=steel)       # frame with ticks
    pen.rectangle((1, 1, width - 2, height - 2), outline=(82, 86, 98))
    for x in range(16, width, 16):
        pen.line((x, 2, x, 4), fill=(142, 148, 162))
        pen.line((x, height - 5, x, height - 3), fill=(142, 148, 162))
    for y in range(16, height, 16):
        pen.line((2, y, 4, y), fill=(142, 148, 162))
        pen.line((width - 5, y, width - 3, y), fill=(142, 148, 162))
    return canvas


# --- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate everything but write nothing")
    args = parser.parse_args()

    types = known_types()
    problems, outputs = [], {}
    for level in LEVELS:
        data = build_map(level)
        problems += check_map(level["file"], data, types)
        outputs[os.path.join(CAMPAIGN, level["file"])] = data
    problems += check_map("01-enter-the-nexus.json", json.load(open(os.path.join(CAMPAIGN, "01-enter-the-nexus.json"))), types)

    levels = EXISTING + LEVELS
    assert len(levels) == len(MAP_SITES)
    index = campaign_json(levels)

    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Checked {len(levels)} levels: no problems found")
    if args.check:
        return

    for path, data in outputs.items():
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    with open(os.path.join(CAMPAIGN, "campaign.json"), "w") as fh:
        json.dump(index, fh, indent=4)
        fh.write("\n")

    art = load_art()
    os.makedirs(os.path.join(CAMPAIGN, "screenshots"), exist_ok=True)
    for level in levels:
        data = json.load(open(os.path.join(CAMPAIGN, level["file"])))
        render_map(data, art).save(os.path.join(CAMPAIGN, screenshot_name(level["file"])))
    render_campaign_map().save(os.path.join(CAMPAIGN, "campaign_map.png"))
    print(f"Wrote {len(outputs)} maps, campaign.json, {len(levels)} previews and the campaign map to {CAMPAIGN}")


if __name__ == "__main__":
    main()
