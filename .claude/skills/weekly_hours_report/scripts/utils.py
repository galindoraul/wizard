"""Shared utilities for weekly hours report."""
import unicodedata
from datetime import date
from calendar import monthrange

MONTHS = {"Jan":1,"January":1,"Feb":2,"February":2,"Mar":3,"March":3,"Apr":4,"April":4,"May":5,"Jun":6,"June":6,"Jul":7,"July":7,"Aug":8,"August":8,"Sep":9,"Sept":9,"September":9,"Oct":10,"October":10,"Nov":11,"November":11,"Dec":12,"December":12}
MONTH_NAMES_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def normalize_value(value):
    if not value: return ""
    s=str(value); s=unicodedata.normalize("NFD",s); s="".join(c for c in s if unicodedata.category(c)!="Mn")
    return s.lower().replace(" ","").strip()

def get_month_number(month):
    n=MONTHS.get(month)
    if not n: raise ValueError(f"Invalid month: {month}")
    return n

def get_month_name(month_number, short=True):
    return MONTH_NAMES_SHORT[month_number-1] if short else ["January","February","March","April","May","June","July","August","September","October","November","December"][month_number-1]

def get_week_of_month(d):
    first=date(d.year,d.month,1); offset=first.weekday(); return (d.day+offset-1)//7+1

def build_month_context(year, month):
    month_num=month if isinstance(month,int) else get_month_number(month)
    month_name=get_month_name(month_num,True); days_in_month=monthrange(year,month_num)[1]; weeks_map={}
    for day in range(1,days_in_month+1):
        d=date(year,month_num,day)
        if d.weekday()>=5: continue
        wn=get_week_of_month(d); weeks_map.setdefault(wn,[]).append(day)
    weeks=[]
    for wn in sorted(weeks_map):
        workdays=weeks_map[wn]; start,end=workdays[0],workdays[-1]
        label=f"{month_name} {start}" if start==end else f"{month_name} {start}-{end}"
        weeks.append({"weekNumber":wn,"workdays":workdays,"label":label})
    return {"year":year,"month":month_num,"monthName":month_name,"weeks":weeks,"weekCount":len(weeks)}

def get_month_workdays(year, month_num):
    days=monthrange(year,month_num)[1]; out=[]
    for day in range(1,days+1):
        d=date(year,month_num,day)
        if d.weekday()<5: out.append(d)
    return out

def get_day_name(d, short=True):
    idx=d.weekday(); names=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"] if short else ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]; return names[idx]

def group_consecutive(days):
    if not days: return []
    days=sorted(days); ranges=[]; start=end=days[0]
    for d in days[1:]:
        if d==end+1: end=d
        else: ranges.append({"start":start,"end":end}); start=end=d
    ranges.append({"start":start,"end":end}); return ranges
