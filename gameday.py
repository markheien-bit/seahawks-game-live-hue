"""Seahawks game-day lights.

  python gameday.py --pair              one-time setup: press the bridge's link button first, then run this
  python gameday.py                     live: SEA, today's game, all reachable lights
  python gameday.py --team KC           follow a different NFL team (ESPN abbreviation)
  python gameday.py --delay 20          hold every reaction 20 s (if the lights spoil plays on your TV)
  python gameday.py --replay EVENT TEAM dry run: print what WOULD have fired for a finished/in-progress game (no lights)
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
POLL=10           # seconds between feed checks
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

def live(delay,demo=False):
    lights,ids=reachable()
    if not os.path.exists(saved): json.dump({i:lights[i]["state"] for i in ids},open(saved,"w"))
    if os.path.exists(stop): os.remove(stop)
    log(f"{len(ids)} lights. Ctrl+C to stop and restore.")
    try:
        if demo:
            ambient_step(ids,1); time.sleep(10); log("demo TOUCHDOWN"); wild(ids,15); return
        event,name,side=find_game(TEAM)
        if not event: log("No",TEAM,"game on today's scoreboard."); return
        log("Tracking:",name,"| event",event,"| reaction delay",delay,"s")
        seen=None; score=0; step=0; next_poll=0; queue=[]; state=""
        while not os.path.exists(stop):
            now=time.time()
            if now>=next_poll:
                next_poll=now+POLL
                try:
                    s=get(ESPN+"summary?event="+event)
                    st=s["header"]["competitions"][0]["status"]["type"]["name"]
                    if st!=state: state=st; log("game status:",st)
                    plays=all_plays(s)
                    if seen is None:                      # started mid-game: don't replay history
                        seen=set(plays); score=max([p.get(side,0) for _,p in plays.values()] or [0])
                    for pid,(poss,p) in sorted(plays.items(),key=lambda kv:int(kv[1][1].get("sequenceNumber",0))):
                        if pid in seen: continue
                        seen.add(pid)
                        hit=classify(poss,p,TEAM,side,score); score=max(score,p.get(side,score))
                        if hit: queue.append((now+delay,hit,p.get("text","").strip()[:90]))
                    if st=="STATUS_FINAL" and not queue:
                        comp=s["header"]["competitions"][0]["competitors"]
                        won=[c for c in comp if c["team"]["abbreviation"]==TEAM][0].get("winner")
                        log("FINAL.","SEAHAWKS WIN!" if won else "")
                        if won: wild(ids,60)
                        return
                except Exception as e: log("feed hiccup:",e)
            due=[q for q in queue if q[0]<=time.time()]
            if due:
                queue=[q for q in queue if q not in due]
                secs=max(q[1][0] for q in due)
                for q in due: log("BIG PLAY:",q[1][1],"|",q[2])
                wild(ids,secs); step+=1; ambient_step(ids,step)
            else:
                step+=1; ambient_step(ids,step)
                t=time.time()+5                        # slow loop: ~6 s per step, 2.5 s fades
                while time.time()<t and not os.path.exists(stop) and time.time()<next_poll: time.sleep(0.5)
    except KeyboardInterrupt: log("stopping")
    finally: restore()

if __name__=="__main__":
    a=sys.argv[1:]
    if "--team" in a: TEAM=a[a.index("--team")+1].upper()
    if a[:1]==["--pair"]: pair()
    elif not BRIDGE and a[:1]!=["--replay"]: sys.exit("No bridge configured. Run: python gameday.py --pair")
    elif a[:1]==["--replay"]: replay(a[1],a[2])
    elif a[:1]==["--demo"]: live(0,demo=True)
    else: live(float(a[a.index("--delay")+1]) if "--delay" in a else 0)
