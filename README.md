# Seahawks Game Live Hue

Philips Hue lights that follow a live NFL game.

During normal play the house slowly loops the Seahawks colours — College Navy, Action Green, Wolf Grey. When Seattle makes a big play, every light goes fast and wild for a few seconds, then settles back into the loop.

One Python file, standard library only. No cloud account, no subscription — it talks to the Hue Bridge directly over the local network and reads ESPN's public play-by-play feed.

## What counts as a big play

| Play | Burst |
|---|---|
| Touchdown | 30 s |
| Interception / fumble recovery | 20 s |
| Safety, two-point conversion, blocked kick | 15 s |
| Field goal | 12 s |
| Run or catch of 20+ yards | 12 s |
| Kick return of 35+ yards / punt return of 20+ yards | 12 s |
| Sack | 10 s |
| Opponent missed field goal | 8 s |
| Final whistle, Seahawks win | 60 s |

The other team's big plays do nothing.

## Setup

Requires Python 3.9+ and a Hue Bridge on the same network as the computer.

1. Press the round link button on top of the Hue Bridge.
2. Within 30 seconds:

   ```
   python gameday.py --pair
   ```

   This registers a local app key and writes `hue_key.json` and `config.json` next to the script. Both are git-ignored — **never commit them**; the key controls your lights. Revoke it any time in the Hue app under Settings → Bridge → Apps.

## Use

```
python gameday.py                 # follow today's Seahawks game on every reachable light
python gameday.py --team KC       # follow another team (ESPN abbreviation)
python gameday.py --delay 20      # hold every reaction 20 s
python gameday.py --team KC --dry # watch a live game and print triggers, no lights
python gameday.py --demo          # 10 s of the loop, one touchdown burst, restore
python gameday.py --replay 401872932 BUF   # dry run against any game: print what would have fired, no lights
```

Start it any time before or during the game. It saves each light's state on start and restores it on exit — press **Ctrl+C** to stop, or let it finish on the final whistle.

### About the delay

ESPN's feed usually trails the live action by 20–60 seconds. On cable or antenna the burst lands a little after the play. On a streaming service, which is itself delayed, it can land right on the play — or slightly *before* you see it. If the lights start spoiling plays, add `--delay`.

## How it works

- Two ESPN endpoints, deduplicated by play id. The **scoreboard** endpoint's `situation.lastPlay` is checked every 4 seconds: it carries only the newest play, but in testing it showed a new play up to ~20 seconds before the full feed did. The **summary** play-by-play is checked every 15 seconds as a backstop, so a play the fast feed skips (no-huddle, or a play that lands during a burst) still fires.
- Scores are detected from the change in the team's running score, so a touchdown fires however ESPN labels the play. Everything else is classified from the play type, yardage, and which team had possession.
- Lights are driven through the bridge's local REST API. That API is limited to roughly 10 commands a second, so the "wild" mode hits a random handful of lights each beat rather than all of them — it reads as faster than cycling every light in order.
- Colours are CIE xy values. The literal hex conversions of navy and green look washed-out on a bulb, so both are pushed deeper and more saturated than the official swatches.

## Changing the colours

Edit `NAVY`, `GREEN`, `GREY` (ambient loop) and `WILD` (burst palette) near the top of `gameday.py`. Each entry is `([x, y], brightness 1–254)`. The colours are the only team-specific thing in the script.

---

Not affiliated with the Seattle Seahawks, the NFL, ESPN, or Signify / Philips Hue.
