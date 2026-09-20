"""Seahawks game-day lights.

  python gameday.py --pair              one-time setup: press the bridge's link button first, then run this
  python gameday.py                     live: SEA, today's game, all reachable lights
  python gameday.py --at-kickoff        wait (lights untouched) until the game starts, flash 20 s for kickoff, then go live
  python gameday.py --team KC           follow a different NFL team (ESPN abbreviation)
  python gameday.py --delay 20          hold every reaction 20 s (if the lights spoil plays on your TV)
  python gameday.py --replay EVENT TEAM dry run: print what WOULD have fired for a finished/in-progress game (no lights)
  python gameday.py --team KC --dry     watch a live game and print triggers, no lights
  python gameday.py --demo              10 s ambient, then one touchdown burst, then restore

Stop with Ctrl+C (lights are restored), or create a file named STOP next to this script.
"""
import json,sys,os,time,random,urllib.request

S=os.path.dirname(os.path.abspath(__file__))
def _cfg():
    try: return json.load(open(os.path.join(S,"config.json")))
    except Exception: return {}
BRIDGE=os.environ.get("HUE_BRIDGE_IP") or _cfg().get("bridge_ip","")   # set by --pair, or edit config.json
TEAM="SEA"
ESPN="https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
FAST_POLL=4       # seconds between scoreboard checks (newest play, arrives first)
FULL_POLL=15      # seconds between full play-by-play checks (backstop: catches anything the fast feed skipped)
NAVY=([0.157,0.08],65); GREEN=([0.26,0.64],190); GREY=([0.3041,0.3248],170)
PAL=[NAVY,GREEN,NAVY,GREY,GREEN]
WILD=[([0.26,0.64],254),([0.157,0.08],254),([0.3127,0.329],254),([0.26,0.64],254)]  # green, electric blue, white
saved=os.path.join(S,"gameday_saved.json"); stop=os.path.join(S,"STOP")

def log(*a): print(time.strftime("%H:%M:%S"),*a,flush=True)
def get(url):
    return json.load(urllib.request.urlopen(url,timeout=10))

# ---------- big-play detection ----------
def all_plays(summary):
    dr=summary.get("drives") or {}
    drives=list(dr.get("previous") or [])
    cur=dr.get("current")
    if cur: drives.append(cur)
    out={}
    for d in drives:
        poss=(d.get("team") or {}).get("abbreviation","")
        for p in d.get("plays") or []:
            out[p["id"]]=(poss,p)
    return out

def classify(poss,p,team,side,last_score):
    """Return (seconds_of_wild, label) or None. side = 'awayScore' / 'homeScore' for our team."""
    typ=(p.get("type") or {}).get("text",""); txt=p.get("text","") or ""; yd=p.get("statYardage",0) or 0
    gained=p.get(side,last_score)-last_score
    if gained>=6: return 30,"TOUCHDOWN"
    if gained==3: return 12,"FIELD GOAL"
    if gained==2: return 15,"SAFETY / 2-PT"
    if "NULLIFIED" in txt.upper() or "No Play" in txt: return None
    if poss==team:                                   # we have the ball
        if typ in ("Rush","Pass Reception") and yd>=20: return 12,f"{yd}-yd {typ.lower()}"
        if typ=="Kickoff" and yd>=35: return 12,f"{yd}-yd kick return"
    else:                                            # we're on defence / coverage
        if "Interception" in typ: return 20,"INTERCEPTION"
        if typ=="Fumble Recovery (Opponent)": return 20,"FUMBLE RECOVERY"
        if typ=="Sack": return 10,"SACK"
        if "Blocked" in typ: return 15,typ.upper()
        if typ=="Punt" and yd>=20: return 12,f"{yd}-yd punt return"
        if "Missed" in typ or "Field Goal Missed" in typ: return 8,"OPPONENT MISSED FG"
    return None

def find_game(team):
    for e in get(ESPN+"scoreboard")["events"]:
        c=e["competitions"][0]
        for t in c["competitors"]:
            if t["team"]["abbreviation"]==team:
                return e["id"],e["name"],("homeScore" if t["homeAway"]=="home" else "awayScore")
    return None,None,None

# ---------- lights ----------
def key(): return json.load(open(os.path.join(S,"hue_key.json")))[0]["success"]["username"]
def put(path,body):
    r=urllib.request.Request(f"http://{BRIDGE}/api/{key()}{path}",data=json.dumps(body).encode(),method="PUT")
    try: urllib.request.urlopen(r,timeout=3).read()
    except Exception: pass
def reachable():
    l=get(f"http://{BRIDGE}/api/{key()}/lights")
    return l,[i for i in l if l[i]["state"].get("reachable")]
def ambient_step(ids,step):
    for n,i in enumerate(ids):
        c,br=PAL[(n+step)%len(PAL)]
        put(f"/lights/{i}/state",{"on":True,"xy":c,"bri":br,"transitiontime":25}); time.sleep(0.06)
def wild(ids,seconds):
    end=time.time()+seconds; beat=0
    while time.time()<end and not os.path.exists(stop):
        beat+=1
        for i in random.sample(ids,min(5,len(ids))):
            c,br=random.choice(WILD)
            put(f"/lights/{i}/state",{"on":True,"xy":c,"bri":br if beat%3 else random.choice([30,254]),"transitiontime":0}); time.sleep(0.05)
        if beat%5==0: put("/groups/0/action",{"alert":"select"})
        time.sleep(0.05)
def restore():
    if not os.path.exists(saved): return
    for i,s in json.load(open(saved)).items():
        body={"on":True,"bri":s.get("bri",254),"transitiontime":10}
        if s.get("colormode")=="ct": body["ct"]=s["ct"]
        elif "xy" in s: body["xy"]=s["xy"]
        put(f"/lights/{i}/state",body); time.sleep(0.1)
        if not s["on"]: put(f"/lights/{i}/state",{"on":False}); time.sleep(0.1)
    os.remove(saved); log("lights restored")

# ---------- modes ----------
def pair():
    """Find the bridge, register an app key (link button must have been pressed in the last 30 s)."""
    ip=BRIDGE
    if not ip:
        found=get("https://discovery.meethue.com/")
        if not found: sys.exit("No bridge found. Put its IP in config.json as {\"bridge_ip\": \"x.x.x.x\"} and retry.")
        ip=found[0]["internalipaddress"]
    r=urllib.request.Request(f"http://{ip}/api",data=json.dumps({"devicetype":"gameday-lights#pc"}).encode(),method="POST")
    res=json.load(urllib.request.urlopen(r,timeout=5))
    if "success" not in res[0]: sys.exit(f"Bridge said: {res[0]}  (press the link button, then run --pair again within 30 s)")
    json.dump(res,open(os.path.join(S,"hue_key.json"),"w")); json.dump({"bridge_ip":ip},open(os.path.join(S,"config.json"),"w"))
    print("Paired with bridge at",ip)

def replay(event,team):
    s=get(ESPN+"summary?event="+event)
    comp=s["header"]["competitions"][0]
    side=[("homeScore" if t["homeAway"]=="home" else "awayScore") for t in comp["competitors"] if t["team"]["abbreviation"]==team][0]
    score=0
    for pid,(poss,p) in sorted(all_plays(s).items(),key=lambda kv:int(kv[1][1].get("sequenceNumber",0))):
        hit=classify(poss,p,team,side,score); score=max(score,p.get(side,score))
        if hit: print(f"Q{p['period']['number']} {p['clock']['displayValue']:>5}  {hit[0]:>2}s  {hit[1]:<22} {p.get('text','').strip()[:80]}")

def fast_play(event,team):
    """Newest play from the scoreboard endpoint, which runs up to ~20 s ahead of the full summary.
    Returns (status, our_score, play_id, poss_abbr, play_dict) - play fields are None between plays."""
    for e in get(ESPN+"scoreboard")["events"]:
        if e["id"]!=event: continue
        c=e["competitions"][0]; abbr={t["team"]["id"]:t["team"]["abbreviation"] for t in c["competitors"]}
        ours=int([t.get("score") or 0 for t in c["competitors"] if t["team"]["abbreviation"]==team][0])
        st=c["status"]["type"]["name"]; lp=(c.get("situation") or {}).get("lastPlay")
        if not lp or not lp.get("id"): return st,ours,None,None,None
        typ=(lp.get("type") or {}).get("text","")
        # punts sit in the punting team's drive; everything else belongs to lastPlay.team
        tid=((lp.get("start") or {}).get("team") or {}).get("id") if typ=="Punt" else (lp.get("team") or {}).get("id")
        return st,ours,str(lp["id"]),abbr.get(tid,""),lp
    return None,0,None,None,None

def live(delay,demo=False,dry=False,kickoff=False):
    global put
    if dry: put=lambda *a,**k: None; ids=["0"]
    else:
        lights,ids=reachable()
        if not os.path.exists(saved): json.dump({i:lights[i]["state"] for i in ids},open(saved,"w"))
    if os.path.exists(stop): os.remove(stop)
    log(f"{len(ids)} lights. Ctrl+C to stop and restore." if not dry else "DRY RUN - no lights, printing triggers only.")
    try:
        if demo:
            ambient_step(ids,1); time.sleep(10); log("demo TOUCHDOWN"); wild(ids,15); return
        event,name,side=find_game(TEAM)
        if not event: log("No",TEAM,"game on today's scoreboard."); return
        log("Tracking:",name,"| event",event,"| reaction delay",delay,"s")
        if kickoff:
            if delay: time.sleep(delay)
            log("KICKOFF - flashing"); wild(ids,20)
        seen=None; score=0; step=0; next_fast=0; next_full=0; queue=[]; state=""; last_fire=0
        def consider(pid,poss,p,src):
            nonlocal score,last_fire
            if pid in seen: return
            seen.add(pid)
            hit=classify(poss,p,TEAM,side,score); score=max(score,p.get(side,score))
            if not hit: return
            is_score=hit[1] in ("TOUCHDOWN","FIELD GOAL","SAFETY / 2-PT")
            if not is_score and time.time()-last_fire<40: return      # same play seen twice via the two feeds
            last_fire=time.time(); queue.append((time.time()+delay,hit,f"[{src}] "+(p.get("text") or "").strip()[:90]))
        while not os.path.exists(stop):
            now=time.time()
            if now>=next_full:                                         # full play-by-play: complete, but slower
                next_full=now+FULL_POLL
                try:
                    s=get(ESPN+"summary?event="+event); plays=all_plays(s)
                    if seen is None:                                   # started mid-game: don't replay history
                        seen=set(plays); score=max([p.get(side,0) for _,p in plays.values()] or [0])
                    for pid,(poss,p) in sorted(plays.items(),key=lambda kv:int(kv[1][1].get("sequenceNumber",0))):
                        consider(pid,poss,p,"summary")
                except Exception as e: log("summary feed hiccup:",e)
            if now>=next_fast and seen is not None:                    # scoreboard lastPlay: newest play only, but first
                next_fast=now+FAST_POLL
                try:
                    st,ours,pid,poss,lp=fast_play(event,TEAM)
                    if st and st!=state: state=st; log("game status:",st)
                    if pid:
                        p=dict(lp); p[side]=ours; consider(pid,poss,p,"scoreboard")
                    if st=="STATUS_FINAL" and not queue:
                        comp=get(ESPN+"summary?event="+event)["header"]["competitions"][0]["competitors"]
                        won=[c for c in comp if c["team"]["abbreviation"]==TEAM][0].get("winner")
                        log("FINAL.",TEAM+" WIN!" if won else "")
                        if won: wild(ids,60)
                        return
                except Exception as e: log("scoreboard feed hiccup:",e)
            due=[q for q in queue if q[0]<=time.time()]
            if due:
                queue=[q for q in queue if q not in due]
                secs=max(q[1][0] for q in due)
                for q in due: log("BIG PLAY:",q[1][1],"|",q[2])
                wild(ids,secs if not dry else 0); step+=1; ambient_step(ids,step)
            else:
                step+=1; ambient_step(ids,step)
                t=time.time()+5                                        # slow loop: ~6 s per step, 2.5 s fades
                while time.time()<t and not os.path.exists(stop) and time.time()<min(next_fast,next_full): time.sleep(0.25)
    except KeyboardInterrupt: log("stopping")
    finally:
        if not dry: restore()

if __name__=="__main__":
    a=sys.argv[1:]
    if "--team" in a: TEAM=a[a.index("--team")+1].upper()
    if a[:1]==["--pair"]: pair()
    elif not BRIDGE and a[:1]!=["--replay"] and "--dry" not in a: sys.exit("No bridge configured. Run: python gameday.py --pair")
    elif a[:1]==["--replay"]: replay(a[1],a[2])
    elif a[:1]==["--demo"]: live(0,demo=True)
    elif "--dry" in a: live(0,dry=True)
    else:
        if "--at-kickoff" in a:                       # leave the lights alone until the game actually starts
            event,name,_=find_game(TEAM)
            if not event: sys.exit(f"No {TEAM} game on today's scoreboard.")
            log("Waiting for kickoff:",name,"- lights untouched until then. Ctrl+C to cancel.")
            waited=False
            while True:
                try:
                    if fast_play(event,TEAM)[0] not in ("STATUS_SCHEDULED",None): break
                    waited=True                       # only flash if we really saw the game go from scheduled to live
                except Exception as e: log("feed hiccup:",e)
                time.sleep(8)
        live(float(a[a.index("--delay")+1]) if "--delay" in a else 0, kickoff=("--at-kickoff" in a and waited))
