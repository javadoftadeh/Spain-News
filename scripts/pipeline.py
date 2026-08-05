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
OUT=ROOT/'data/news.json'; POSTED=ROOT/'data/posted.json'
FEEDS=[
 {'source':'RTVE Noticias','url':'https://www.rtve.es/api/noticias.rss'},
 {'source':'RTVE España','url':'https://www.rtve.es/api/noticias/espana.rss'},
 {'source':'RTVE Economía','url':'https://www.rtve.es/api/noticias/economia.rss'},
 {'source':'RTVE Ciencia','url':'https://www.rtve.es/api/noticias/ciencia-tecnologia.rss'},
 {'source':'RTVE Cultura','url':'https://www.rtve.es/api/noticias/cultura.rss'},
 {'source':'EL PAÍS','url':'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada'},
 {'source':'EL PAÍS España','url':'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada'},
 {'source':'EL PAÍS Economía','url':'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada'},
 {'source':'La Vanguardia','url':'https://www.lavanguardia.com/rss/home.xml'},
]
CATS={
 'politica':['gobierno','congreso','elecciones','partido','ministro','política','ley','tribunal','cataluña'],
 'economia':['economía','mercado','empleo','paro','inflación','empresa','precio','vivienda','bolsa','pib'],
 'migracion':['migración','inmigración','extranjero','residencia','visado','asilo','frontera','nacionalidad'],
 'sociedad':['sociedad','salud','sanidad','educación','violencia','suceso','incendio','calor','tráfico'],
 'ciencia':['ciencia','tecnología','inteligencia artificial','investigación','espacio','eclipse','clima','energía'],
 'cultura':['cultura','cine','música','libro','arte','televisión','serie','festival'],
 'deportes':['deporte','fútbol','liga','real madrid','barcelona','selección','tenis','baloncesto','ciclismo'],
 'turismo':['turismo','viaje','aeropuerto','hotel','vacaciones','turista'],
}
LABEL={'politica':'سیاست','economia':'اقتصاد','migracion':'مهاجرت و اقامت','sociedad':'جامعه','ciencia':'علم و فناوری','cultura':'فرهنگ','deportes':'ورزش','turismo':'گردشگری'}
ICON={'politica':'🏛','economia':'💶','migracion':'🛂','sociedad':'👥','ciencia':'🔬','cultura':'🎭','deportes':'⚽','turismo':'✈️'}
ALERT=['urgente','última hora','dimite','fallece','muere','incendio','evacuación','emergencia','ataque','explosión','terremoto','inundación','crisis','alerta']

def clean(v): return re.sub(r'\s+',' ',BeautifulSoup(v or '','html.parser').get_text(' ',strip=True)).strip()
def canon(u):
 p=urlsplit(u); return urlunsplit((p.scheme,p.netloc,p.path,'',''))
def parsedate(e):
 try:
  x=date_parser.parse(e.get('published') or e.get('updated')); return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
 except Exception: return datetime.now(timezone.utc)
def norm(t):
 stop={'el','la','los','las','un','una','de','del','y','en','a','por','para','con','que'}
 return {w for w in re.sub(r'[^\wáéíóúüñ ]',' ',t.lower()).split() if w not in stop and len(w)>2}
def classify(t):
 s={k:sum(w in t.lower() for w in v) for k,v in CATS.items()}; b=max(s,key=s.get); return b if s[b] else 'sociedad'
def score(t,d,c):
 age=max(0,(datetime.now(timezone.utc)-d.astimezone(timezone.utc)).total_seconds()/3600)
 return max(25,min(96,45+max(0,25-int(age/3))+min(21,sum(7 for w in ALERT if w in t.lower()))+(5 if c in {'migracion','politica','economia'} else 0)))
def image(e):
 m=e.get('media_content') or e.get('media_thumbnail') or []
 if m and isinstance(m,list) and m[0].get('url'): return m[0]['url']
 for x in e.get('enclosures',[]):
  if str(x.get('type','')).startswith('image/'): return x.get('href','')
 return ''

def collect():
 rows=[]; statuses=[]; cut=datetime.now(timezone.utc)-timedelta(hours=72)
 for f in FEEDS:
  p=feedparser.parse(f['url'],request_headers={'User-Agent':'SpainNewsFA/2.0'})
  statuses.append({'source':f['source'],'ok':bool(p.entries),'count':len(p.entries)})
  for e in p.entries[:35]:
   title=clean(e.get('title')); url=canon(e.get('link','')); published=parsedate(e)
   if not title or not url or published.astimezone(timezone.utc)<cut: continue
   summary=clean(e.get('summary') or e.get('description'))[:650]; full=f'{title} {summary}'; cat=classify(full)
   rows.append({'id':hashlib.sha1(url.encode()).hexdigest()[:12],'source':f['source'],'title':title,'summary':summary,'url':url,'image':image(e),'published_at':published.isoformat(),'category':cat,'priority':score(full,published,cat)})
 unique=[]; urls=set(); titles=[]
 for x in sorted(rows,key=lambda z:(z['priority'],z['published_at']),reverse=True):
  n=norm(x['title']); dup=x['url'] in urls or any(len(n&p)/max(1,len(n|p))>=.76 for p in titles)
  if dup: continue
  urls.add(x['url']); titles.append(n); unique.append(x)
 return unique[:100],statuses

def choose_model(key):
 preferred=os.getenv('GEMINI_MODEL','').strip()
 try:
  r=requests.get('https://generativelanguage.googleapis.com/v1beta/models',headers={'x-goog-api-key':key},timeout=30); r.raise_for_status()
  available=[m['name'].replace('models/','') for m in r.json().get('models',[]) if 'generateContent' in m.get('supportedGenerationMethods',[])]
 except Exception as e:
  print('Model list failed:',e); available=[]
 for m in [preferred,'gemini-3.1-flash-lite','gemini-3.5-flash-lite','gemini-2.5-flash-lite','gemini-2.5-flash']:
  if m and (not available or m in available): print('Gemini model:',m); return m
 return available[0] if available else 'gemini-2.5-flash-lite'

SCHEMA={'type':'OBJECT','properties':{
 'title_fa':{'type':'STRING'},'lead_fa':{'type':'STRING'},
 'key_points_fa':{'type':'ARRAY','items':{'type':'STRING'}},
 'analysis_fa':{'type':'STRING'},'audience_impact_fa':{'type':'STRING'},
 'category':{'type':'STRING','enum':list(CATS)},'priority':{'type':'INTEGER','minimum':1,'maximum':100},
 'urgency':{'type':'STRING','enum':['breaking','important','normal']},
 'hashtags_fa':{'type':'ARRAY','items':{'type':'STRING'}}},
 'required':['title_fa','lead_fa','key_points_fa','analysis_fa','audience_impact_fa','category','priority','urgency','hashtags_fa']}

def editorialize(x,key,model):
 prompt=f'''تو سردبیر ارشد یک رسانه فارسی درباره اسپانیا هستی. خبر را ترجمه تحت‌اللفظی نکن؛ آن را دقیق، بی‌طرف، کوتاه و روزنامه‌ای بازنویسی کن.
قواعد: هیچ واقعیت یا عددی را اختراع نکن. تیتر حداکثر ۸۵ نویسه. لید دو جمله کوتاه. ۲ تا ۴ نکته مهم. تحلیل جدا و بدون پیش‌بینی قطعی. اثر بر فارسی‌زبانان/مهاجران فقط اگر مستقیم است؛ وگرنه بنویس «اثر مستقیم مشخصی گزارش نشده است.» urgency فقط برای فوریت واقعی breaking باشد. هشتگ‌ها فارسی، کم و با # باشند. خروجی فقط JSON مطابق schema.
عنوان: {x['title']}\nمتن RSS: {x['summary']}\nمنبع: {x['source']}\nدسته اولیه: {x['category']}\nامتیاز اولیه: {x['priority']}'''
 payload={'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'temperature':.15,'responseMimeType':'application/json','responseSchema':SCHEMA}}
 for attempt in range(4):
  try:
   r=requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':key,'Content-Type':'application/json'},json=payload,timeout=75)
   if r.status_code==429: time.sleep(8*(attempt+1)); continue
   r.raise_for_status(); obj=json.loads(r.json()['candidates'][0]['content']['parts'][0]['text']); x.update(obj); x['ai_translated']=True; x['editorial_version']=2; return x
  except Exception as e:
   print(f'Gemini attempt {attempt+1} failed:',e); time.sleep(4*(attempt+1))
 x.update({'title_fa':x['title'],'lead_fa':x['summary'],'key_points_fa':[],'analysis_fa':'','audience_impact_fa':'','urgency':'normal','hashtags_fa':['#اخبار_اسپانیا'],'ai_translated':False,'editorial_version':2}); return x

def trim(t,n):
 t=re.sub(r'\s+',' ',t or '').strip(); return t if len(t)<=n else t[:n-1].rstrip()+'…'
def flist(v): return [str(i).strip() for i in v] if isinstance(v,list) else []
def ftime(v):
 try: return date_parser.parse(v).astimezone(timezone(timedelta(hours=2))).strftime('%H:%M')
 except Exception: return '--:--'
def format_post(x):
 cat=x.get('category','sociedad'); urgency=x.get('urgency','normal')
 head='🚨 <b>فوری | رصد اسپانیا</b>' if urgency=='breaking' else ('🔴 <b>مهم | رصد اسپانیا</b>' if urgency=='important' else '🇪🇸 <b>رصد اسپانیا</b>')
 parts=[head,f"🕰 <b>به‌روزرسانی:</b> {ftime(x.get('published_at',''))} به وقت مادرید",'',f"<b>{html.escape(trim(x.get('title_fa') or x['title'],120))}</b>",'',html.escape(trim(x.get('lead_fa') or x.get('summary',''),520))]
 pts=flist(x.get('key_points_fa'))[:4]
 if pts: parts+=['','📋 <b>جزئیات مهم</b>']+[f"• {html.escape(trim(p,220))}" for p in pts]
 if x.get('analysis_fa'): parts+=['','🧭 <b>تحلیل خبر</b>',html.escape(trim(x['analysis_fa'],430))]
 impact=trim(x.get('audience_impact_fa',''),300)
 if impact and impact!='اثر مستقیم مشخصی گزارش نشده است.': parts+=['','🎯 <b>اثر برای فارسی‌زبانان اسپانیا</b>',html.escape(impact)]
 tags=flist(x.get('hashtags_fa'))[:3]; tags=[t if t.startswith('#') else '#'+t for t in tags]
 if '#اخبار_اسپانیا' not in tags: tags.insert(0,'#اخبار_اسپانیا')
 parts+=['','━━━━━━━━━━━━━━',f"{ICON.get(cat,'📰')} <b>دسته:</b> {LABEL.get(cat,'خبر')}",f"📊 <b>اهمیت:</b> {int(x.get('priority',50))}/۱۰۰",f"📰 <b>منبع:</b> {html.escape(x.get('source',''))}",f"🔗 <a href=\"{html.escape(x['url'])}\">مشاهده خبر اصلی</a>",'',' '.join(tags),'@spainnewsfa']
 return '\n'.join(parts)[:4050]

def publish(items):
 token=os.getenv('TELEGRAM_BOT_TOKEN'); channel=os.getenv('TELEGRAM_CHANNEL_ID')
 if not token or not channel: return []
 posted=json.loads(POSTED.read_text('utf-8')) if POSTED.exists() else []; sent=[]
 threshold=int(os.getenv('TELEGRAM_MIN_PRIORITY','78')); limit=int(os.getenv('TELEGRAM_MAX_POSTS','3'))
 for x in sorted(items,key=lambda z:(z.get('urgency')=='breaking',z.get('priority',0),z.get('published_at','')),reverse=True):
  if x['id'] in posted or x.get('priority',0)<threshold or len(sent)>=limit or not x.get('ai_translated'): continue
  r=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':channel,'text':format_post(x),'parse_mode':'HTML','disable_web_page_preview':False},timeout=30)
  if r.ok: posted.append(x['id']); sent.append(x['id']); time.sleep(2)
  else: print('Telegram error:',r.text)
 POSTED.write_text(json.dumps(posted[-1500:],ensure_ascii=False,indent=2),'utf-8'); return sent

def main():
 items,feeds=collect(); old={}
 if OUT.exists():
  try: old={x['id']:x for x in json.loads(OUT.read_text('utf-8')).get('items',[])}
  except Exception as e: print('Old data error:',e)
 key=os.getenv('GEMINI_API_KEY','').strip(); model=choose_model(key) if key else ''; max_ai=int(os.getenv('MAX_AI_TRANSLATIONS','6')); done=[]; count=0
 for x in items:
  o=old.get(x['id'])
  if o and o.get('editorial_version')==2 and o.get('ai_translated'):
   for k in ['title_fa','lead_fa','key_points_fa','analysis_fa','audience_impact_fa','category','priority','urgency','hashtags_fa','ai_translated','editorial_version']:
    if k in o: x[k]=o[k]
  elif key and count<max_ai: x=editorialize(x,key,model); count+=1; time.sleep(5)
  else: x.update({'title_fa':x['title'],'lead_fa':x['summary'],'key_points_fa':[],'analysis_fa':'','audience_impact_fa':'','urgency':'normal','hashtags_fa':['#اخبار_اسپانیا'],'ai_translated':False,'editorial_version':2})
  done.append(x)
 done.sort(key=lambda z:(z.get('priority',0),z.get('published_at','')),reverse=True)
 OUT.write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'editorial_version':2,'featured_ids':[x['id'] for x in done if x.get('ai_translated')][:5],'items':done,'feeds':feeds},ensure_ascii=False,indent=2),'utf-8')
 sent=publish(done); print(f'saved={len(done)} ai_processed={count} telegram_sent={len(sent)}')
if __name__=='__main__': main()
