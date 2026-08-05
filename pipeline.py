#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, os, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import feedparser, requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/news.json"
POSTED=ROOT/"data/posted.json"

FEEDS=[
 {"source":"RTVE Noticias","url":"https://www.rtve.es/api/noticias.rss"},
 {"source":"RTVE España","url":"https://www.rtve.es/api/noticias/espana.rss"},
 {"source":"RTVE Economía","url":"https://www.rtve.es/api/noticias/economia.rss"},
 {"source":"RTVE Ciencia","url":"https://www.rtve.es/api/noticias/ciencia-tecnologia.rss"},
 {"source":"RTVE Cultura","url":"https://www.rtve.es/api/noticias/cultura.rss"},
 {"source":"EL PAÍS","url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
 {"source":"EL PAÍS España","url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada"},
 {"source":"EL PAÍS Economía","url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"},
 {"source":"La Vanguardia","url":"https://www.lavanguardia.com/rss/home.xml"},
]
CATS={
 "politica":["gobierno","congreso","elecciones","partido","ministro","política","ley","tribunal","cataluña","migración"],
 "economia":["economía","mercado","empleo","paro","inflación","empresa","precio","vivienda","bolsa","pib","turismo"],
 "sociedad":["sociedad","salud","sanidad","educación","violencia","suceso","incendio","calor","tráfico","familia"],
 "ciencia":["ciencia","tecnología","inteligencia artificial","investigación","espacio","eclipse","clima","energía"],
 "cultura":["cultura","cine","música","libro","arte","televisión","serie","festival"],
 "deportes":["deporte","fútbol","liga","real madrid","barcelona","selección","tenis","baloncesto","ciclismo"],
}
ALERT=["urgente","última hora","dimite","fallece","muere","incendio","evacuación","emergencia","ataque","explosión","terremoto","inundación","crisis"]

def clean(v): return re.sub(r"\s+"," ",BeautifulSoup(v or "","html.parser").get_text(" ",strip=True)).strip()
def canon(u):
 p=urlsplit(u);return urlunsplit((p.scheme,p.netloc,p.path,"",""))
def dt(e):
 try:
  x=date_parser.parse(e.get("published") or e.get("updated"))
  return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
 except: return datetime.now(timezone.utc)
def classify(t):
 s={k:sum(w in t.lower() for w in v) for k,v in CATS.items()};return max(s,key=s.get) if max(s.values()) else "sociedad"
def score(t,d):
 age=max(0,(datetime.now(timezone.utc)-d.astimezone(timezone.utc)).total_seconds()/3600)
 return min(99,max(30,48+max(0,24-int(age/3))+sum(7 for w in ALERT if w in t.lower())))
def norm(t): return set(re.sub(r"[^\wáéíóúüñ ]"," ",t.lower()).split())

def translate_ai(item):
 key=os.getenv("OPENAI_API_KEY")
 if not key:
  item["title_fa"]=item["title"];item["summary_fa"]=item["summary"];item["impact_fa"]="";item["ai_translated"]=False;return item
 prompt=f"""خبر زیر از رسانه اسپانیایی است. فقط JSON معتبر با کلیدهای title_fa، summary_fa، impact_fa برگردان.
ترجمه فارسی باید روان، دقیق و بی‌طرف باشد. summary_fa دو یا سه جمله و impact_fa یک جمله کوتاه درباره اهمیت خبر برای فارسی‌زبانان ساکن اسپانیا باشد.
نام‌ها، اعداد و عدم قطعیت خبر را حفظ کن و چیزی اضافه نکن.
عنوان: {item['title']}
خلاصه: {item['summary']}
منبع: {item['source']}"""
 try:
  r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json={"model":os.getenv("OPENAI_MODEL","gpt-5-mini"),"input":prompt,"text":{"format":{"type":"json_object"}}},timeout=60)
  r.raise_for_status();data=r.json()
  text=data.get("output_text")
  if not text:
   text="".join(c.get("text","") for o in data.get("output",[]) for c in o.get("content",[]) if c.get("type")=="output_text")
  obj=json.loads(text);item.update(obj);item["ai_translated"]=True
 except Exception as e:
  print("translation failed:",e);item["title_fa"]=item["title"];item["summary_fa"]=item["summary"];item["impact_fa"]="";item["ai_translated"]=False
 return item

def collect():
 rows=[];cut=datetime.now(timezone.utc)-timedelta(hours=72);statuses=[]
 for f in FEEDS:
  p=feedparser.parse(f["url"],request_headers={"User-Agent":"SpainNewsFA/1.0"});statuses.append({"source":f["source"],"ok":bool(p.entries),"count":len(p.entries)})
  for e in p.entries[:30]:
   title=clean(e.get("title"));url=canon(e.get("link",""));published=dt(e)
   if not title or not url or published.astimezone(timezone.utc)<cut:continue
   summary=clean(e.get("summary") or e.get("description"))[:450];full=f"{title} {summary}"
   rows.append({"id":hashlib.sha1(url.encode()).hexdigest()[:12],"source":f["source"],"title":title,"summary":summary,"url":url,"published_at":published.isoformat(),"category":classify(full),"priority":score(full,published)})
 unique=[];urls=set();titles=[]
 for x in sorted(rows,key=lambda z:(z["priority"],z["published_at"]),reverse=True):
  n=norm(x["title"])
  if x["url"] in urls or any(len(n&p)/max(1,len(n|p))>=.78 for p in titles):continue
  urls.add(x["url"]);titles.append(n);unique.append(x)
 return unique[:80],statuses

def format_post(x):
 label={"politica":"سیاست","economia":"اقتصاد","sociedad":"جامعه","ciencia":"علم و فناوری","cultura":"فرهنگ","deportes":"ورزش"}.get(x["category"],"خبر")
 icon="🔴" if x["priority"]>=85 else "🟠" if x["priority"]>=75 else "🔵"
 impact=f"\n\n<b>چرا مهم است؟</b>\n{html.escape(x.get('impact_fa',''))}" if x.get("impact_fa") else ""
 return f"""{icon} <b>{html.escape(x.get('title_fa') or x['title'])}</b>

{html.escape(x.get('summary_fa') or x.get('summary',''))}{impact}

🏷 <b>{label}</b>  |  📊 اهمیت: <b>{x['priority']}/100</b>
📰 منبع: {html.escape(x['source'])}

<a href="{html.escape(x['url'])}">مشاهده خبر اصلی</a>
#اخبار_اسپانیا #{label.replace(' ','_')}"""

def publish(items):
 token=os.getenv("TELEGRAM_BOT_TOKEN");channel=os.getenv("TELEGRAM_CHANNEL_ID")
 if not token or not channel:return []
 posted=json.loads(POSTED.read_text("utf-8")) if POSTED.exists() else []
 sent=[]
 threshold=int(os.getenv("TELEGRAM_MIN_PRIORITY","78"));limit=int(os.getenv("TELEGRAM_MAX_POSTS","3"))
 for x in sorted(items,key=lambda z:z["priority"],reverse=True):
  if x["id"] in posted or x["priority"]<threshold or len(sent)>=limit:continue
  r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":channel,"text":format_post(x),"parse_mode":"HTML","disable_web_page_preview":False},timeout=30)
  if r.ok:posted.append(x["id"]);sent.append(x["id"])
  else:print("Telegram error:",r.text)
 POSTED.write_text(json.dumps(posted[-1000:],ensure_ascii=False,indent=2),"utf-8")
 return sent

if __name__=="__main__":
 items,feeds=collect()
 old={}
 if OUT.exists():
  try:old={x["id"]:x for x in json.loads(OUT.read_text("utf-8")).get("items",[])}
  except:pass
 translated=[]
 max_ai=int(os.getenv("MAX_AI_TRANSLATIONS","12"))
 for i,x in enumerate(items):
  if x["id"] in old and old[x["id"]].get("ai_translated"):x.update({k:old[x["id"]].get(k) for k in ("title_fa","summary_fa","impact_fa","ai_translated")})
  elif i<max_ai:x=translate_ai(x);time.sleep(.25)
  else:x["title_fa"]=x["title"];x["summary_fa"]=x["summary"];x["impact_fa"]="";x["ai_translated"]=False
  translated.append(x)
 data={"generated_at":datetime.now(timezone.utc).isoformat(),"items":translated,"feeds":feeds}
 OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),"utf-8")
 sent=publish(translated)
 print(f"saved={len(translated)} telegram_sent={len(sent)}")
