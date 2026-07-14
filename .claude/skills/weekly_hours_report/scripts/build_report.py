"""Build weekly hours report from PTO and Team data."""
import re
from datetime import date
from utils import normalize_value, build_month_context, get_month_workdays, get_week_of_month, get_day_name, group_consecutive, get_month_number

ABSENCE_TYPES = {"pto","pto(pa)","ml","ml(pa)"}

def parse_backups(text):
    if not text.strip():
        return []
    out=[]
    for line in text.split("\n"):
        line = re.sub(r"\(.*?\)","",line).strip()
        if not line:
            continue
        m = re.match(r"^[A-Za-zÀ-ÿ\s]+", line)
        if not m:
            continue
        name = m.group(0).strip()
        norm = normalize_value(name)
        rest = line[len(m.group(0)):].strip()
        for rng in rest.split(","):
            rng=rng.strip()
            if not rng:
                continue
            parts = [p.strip() for p in rng.split("-")]
            try:
                start=int(parts[0]); end=int(parts[1]) if len(parts)>1 else start
            except:
                continue
            out.append({"backupName":norm,"originalBackupName":name,"startDay":start,"endDay":end})
    return out

def parse_team_changes(notes):
    changes=[]
    for m in re.finditer(r"TEAM:\s*(.+?)\s*\|\s*(.+?)\s+(\d+)-(\d+)", notes):
        changes.append({"product":m.group(1).strip(),"pilar":m.group(2).strip(),"fromDay":int(m.group(3)),"toDay":int(m.group(4))})
    return changes

def get_bench_days(team_changes, year, month):
    bench=set()
    for ch in team_changes:
        if "bench" not in ch["product"].lower():
            continue
        for day in range(ch["fromDay"], ch["toDay"]+1):
            try:
                d=date(year,month,day)
            except:
                continue
            if d.month!=month or d.weekday()>=5:
                continue
            bench.add(day)
    return bench

def build_comments(weeks):
    from collections import defaultdict
    mp=defaultdict(list)
    for w in weeks:
        for a in w["absences"]:
            t=a["type"]
            if normalize_value(t) in ("h","holiday"):
                continue
            mp[t].append(a["dayNumber"])
    comments=[]
    for typ, days in mp.items():
        ranges=group_consecutive(sorted(days))
        rng_txt=",".join(f"{r['start']}" if r["start"]==r["end"] else f"{r['start']}-{r['end']}" for r in ranges)
        comments.append(f"• {typ}: {rng_txt}")
    return "\n".join(comments)

def build_team_note(changes):
    if not changes:
        return ""
    return "\n".join(f"• Team change: {c['product']} | {c['pilar']} (days {c['fromDay']}-{c['toDay']})" for c in changes)

def build_report(pto_data, team_data, month, year):
    master={normalize_value(c["short_name"]):c for c in team_data if c["short_name"]}
    month_num=get_month_number(month)
    ctx=build_month_context(year, month)
    workdays=get_month_workdays(year, month_num)
    q1,q2,q3=[],[],[]
    for norm_name,data in pto_data.items():
        emp=master.get(norm_name)
        if not emp:
            print(f"WARN {data['employeeName']} not in team allocation, skipping")
            continue
        if "bench" in emp["team"].lower():
            continue
        weekly={}
        for d in workdays:
            wn=get_week_of_month(d)
            weekly.setdefault(wn,{"weekNumber":wn,"absences":[],"totalAbsenceHours":0,"totalWorkedHours":0,"backups":[]})
            weekly[wn]["totalWorkedHours"]+=8
        absence_map={}; holiday_days=set()
        for a in data["absences"]:
            nt=normalize_value(a["type"])
            absence_map[a["dayNumber"]]=a["type"]
            if nt in ("h","holiday"):
                holiday_days.add(a["dayNumber"])
        for a in data["absences"]:
            d=date(year,month_num,a["dayNumber"]); wn=get_week_of_month(d)
            if wn not in weekly: continue
            w=weekly[wn]; nt=normalize_value(a["type"])
            if nt in ("h","holiday"):
                w["absences"].append(a); w["totalWorkedHours"]-=8; continue
            if nt in ABSENCE_TYPES:
                w["absences"].append(a); w["totalAbsenceHours"]+=8; w["totalWorkedHours"]-=8; continue
            w["totalWorkedHours"]-=8
        team_changes=parse_team_changes(data["notesText"])
        bench_days=get_bench_days(team_changes, year, month_num)
        bench_hrs=0
        for day in bench_days:
            if day in absence_map: continue
            d=date(year,month_num,day); wn=get_week_of_month(d)
            w=weekly.get(wn)
            if w: w["totalWorkedHours"]-=8; bench_hrs+=8
        backup_ranges=parse_backups(data["backupsText"])
        absence_days_set={a["dayNumber"] for a in data["absences"] if normalize_value(a["type"]) in ABSENCE_TYPES}
        # A backup covers real absence days only. Ranges may span weekends/holidays
        # (e.g. "2-6" over a holiday on the 3rd) — those days aren't worked, so warn
        # on any unexpected weekday but never credit or crash on them.
        for br in backup_ranges:
            for day in range(br["startDay"], br["endDay"]+1):
                try: d=date(year,month_num,day)
                except: continue
                if d.weekday()>=5 or day in holiday_days: continue
                if day not in absence_days_set:
                    print(f"WARN {emp['short_name']}: backup {br['originalBackupName']} on day {day} without PTO/ML, skipping that day")
        bc={}
        for br in backup_ranges:
            be=master.get(br["backupName"])
            if not be:
                print(f"WARN backup {br['originalBackupName']} not found, skipping"); continue
            for day in range(br["startDay"], br["endDay"]+1):
                if day not in absence_days_set: continue  # only cover real PTO/ML days (excludes weekends & holidays)
                try: d=date(year,month_num,day)
                except: continue
                if d.weekday()>=5: continue
                wn=get_week_of_month(d)
                bc.setdefault(br["backupName"],{}).setdefault(wn,{"backupName":be["short_name"],"totalHours":0,"workdays":set(),"employeeData":be})
                bc[br["backupName"]][wn]["totalHours"]+=8
                bc[br["backupName"]][wn]["workdays"].add(day)
        for bn,wm in bc.items():
            for wn,cd in wm.items():
                if wn not in weekly: continue
                w=weekly[wn]; wds=sorted(cd["workdays"])
                w["backups"].append({"name":cd["employeeData"]["short_name"],"role":cd["employeeData"]["job_role"],"wave":cd["employeeData"]["wave"],"product":cd["employeeData"]["team"],"pilar":cd["employeeData"]["module"],"startDay":min(wds),"endDay":max(wds),"hours":cd["totalHours"],"workdays":wds})
        all_weeks=sorted(weekly.values(),key=lambda x:x["weekNumber"])
        week_details=[]
        for w in all_weeks:
            wds=[d for d in workdays if get_week_of_month(d)==w["weekNumber"]]
            days=[]
            for d in wds:
                dn=d.day; raw=absence_map.get(dn)
                if not raw:
                    if dn in bench_days:
                        days.append({"dayNumber":dn,"dayName":get_day_name(d),"status":"Bench","hours":0})
                    else:
                        days.append({"dayNumber":dn,"dayName":get_day_name(d),"status":"","hours":8})
                    continue
                nt=normalize_value(raw)
                if nt in ("h","holiday"):
                    days.append({"dayNumber":dn,"dayName":get_day_name(d),"status":"H","hours":0})
                elif nt in ABSENCE_TYPES:
                    days.append({"dayNumber":dn,"dayName":get_day_name(d),"status":raw,"hours":0})
                else:
                    days.append({"dayNumber":dn,"dayName":get_day_name(d),"status":"","hours":0})
            meta=next((x for x in ctx["weeks"] if x["weekNumber"]==w["weekNumber"]),None)
            week_details.append({"weekNumber":w["weekNumber"],"label":meta["label"] if meta else f"Week {w['weekNumber']}","totalHours":w["totalWorkedHours"],"days":days})
        week_hours=[w["totalWorkedHours"] for w in all_weeks]
        total_abs=sum(w["totalAbsenceHours"] for w in all_weeks)
        total_work=sum(w["totalWorkedHours"] for w in all_weeks)
        comments="\n".join(filter(None,[build_team_note(team_changes), build_comments(all_weeks)]))
        employee={"fullName":emp["short_name"],"role":emp["job_role"],"wave":emp["wave"],"product":emp["team"],"pilar":emp["module"],"tag":f"{emp['short_name']} - {emp['team']} - {emp['module']}","weekHours":week_hours,"weekDetails":week_details,"absHrs":total_abs,"workHrs":total_work,"benchHrs":bench_hrs,"comments":comments,"isBench":False,"isBackup":False,"isSeparator":False,"hasIncompleteData":False}
        role=emp["job_role"]
        target = q1 if "QA 1" in role else q2 if "QA 2" in role else q3 if "QA 3" in role else None
        if target is not None:
            target.append(employee)
            backup_map={}
            for wi,w in enumerate(all_weeks):
                for b in w["backups"]:
                    key=b["name"]
                    if key not in backup_map:
                        backup_map[key]={"name":b["name"],"role":b["role"],"wave":b["wave"],"product":b["product"],"pilar":b["pilar"],"weeklyHours":[0]*ctx["weekCount"],"totalHours":0,"allWorkdays":[],"coveredDaysByWeek":{}}
                    bm=backup_map[key]
                    bm["weeklyHours"][wi]+=b["hours"]; bm["totalHours"]+=b["hours"]
                    bm["coveredDaysByWeek"].setdefault(wi,set()).update(b["workdays"])
                    for day in b["workdays"]:
                        if day not in bm["allWorkdays"]: bm["allWorkdays"].append(day)
            for bm in backup_map.values():
                wds=[]
                for wi in range(ctx["weekCount"]):
                    wds_w=[d for d in workdays if get_week_of_month(d)==all_weeks[wi]["weekNumber"]] if wi < len(all_weeks) else []
                    covered=bm["coveredDaysByWeek"].get(wi,set())
                    wds.append({"weekNumber": all_weeks[wi]["weekNumber"] if wi < len(all_weeks) else wi+1,
                                "label": week_details[wi]["label"] if wi < len(week_details) else f"Week {wi+1}",
                                "totalHours": bm["weeklyHours"][wi],
                                "days":[{"dayNumber":d.day,"dayName":get_day_name(d),"status":"","hours":8 if d.day in covered else 0} for d in wds_w]})
                ranges=group_consecutive(sorted(bm["allWorkdays"]))
                rng_txt=",".join(f"{r['start']}-{r['end']}" if r["end"]-r["start"]+1>=4 else ",".join(str(x) for x in range(r["start"],r["end"]+1)) for r in ranges)
                comment=f"• Covered {emp['short_name']} {'day' if len(bm['allWorkdays'])==1 else 'days'} {rng_txt}"
                backup_row={"fullName":f"↳ {bm['name']}","role":bm["role"],"wave":bm["wave"],"product":bm["product"],"pilar":bm["pilar"],"tag":f"{bm['name']} - {bm['product']} - {bm['pilar']}","weekHours":bm["weeklyHours"],"weekDetails":wds,"absHrs":-1,"workHrs":bm["totalHours"],"benchHrs":-1,"comments":comment,"isBench":False,"isBackup":True,"isSeparator":False,"hasIncompleteData":False,"coveringFor":emp["short_name"]}
                target.append(backup_row)
    def sort_emps(lst):
        principals=[e for e in lst if not e["isBackup"]]
        backups=[e for e in lst if e["isBackup"]]
        principals.sort(key=lambda x:(x["product"],x["fullName"]))
        res=[]
        for p in principals:
            res.append(p); res.extend([b for b in backups if b.get("coveringFor")==p["fullName"]])
        return res
    return {"q1":sort_emps(q1),"q2":sort_emps(q2),"q3":sort_emps(q3)}
