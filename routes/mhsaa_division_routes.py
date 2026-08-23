from __future__ import annotations
import json,re,ssl,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any,Callable
from flask import Blueprint,jsonify,request,Response
OFFICIAL_FOOTBALL_REGIONS_URL="https://www.misshsaa.com/2024/11/19/2025-27-football-regions/"
MAIS_DIRECTORY_URL="https://home.msais.org/test2/directory_demo.php"
SUPPORTED_CLASSES=("1A","2A","3A","4A","5A","6A","7A")
class _P(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.r=None;self.c=None
 def handle_starttag(self,t,a):
  t=t.lower()
  if t=='tr':self.r=[]
  elif self.r is not None and t in {'td','th'}:self.c=[]
 def handle_data(self,d):
  if self.c is not None:self.c.append(d)
 def handle_endtag(self,t):
  t=t.lower()
  if self.r is not None and self.c is not None and t in {'td','th'}:self.r.append(' '.join(''.join(self.c).split()));self.c=None
  elif t=='tr' and self.r is not None:
   if self.r:self.rows.append(self.r)
   self.r=None;self.c=None
def _path(d,c):return d/f"mhsaa_2025_27_football_{c.lower()}.json"
def _profile(c):return {'id':f'mhsaa-football-{c.lower()}-2025-27','name':f'MHSAA 2025-27 Football {c}','association':'MHSAA','state':'MS','source_type':'manifest','source_url':OFFICIAL_FOOTBALL_REGIONS_URL,'field_mapping':{'official_name':'official_name','broadcast_name':'broadcast_name','state':'state','classification':'classification','region':'region','source_data':'source_data'},'defaults':{'state':'MS','classification':c},'options':{'create_venues':True,'venue_sport':'Football','update_existing_fields':['classification','region','district','state']}}
def _write(p,x):p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');q.replace(p)
def _fetch():
 req=urllib.request.Request(OFFICIAL_FOOTBALL_REGIONS_URL,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'text/html,application/xhtml+xml','Accept-Language':'en-US,en;q=0.8'})
 with urllib.request.urlopen(req,timeout=25,context=ssl.create_default_context()) as r:return r.read().decode(r.headers.get_content_charset() or 'utf-8',errors='replace')
def _parse(body):
 p=_P();p.feed(body);g={c:[] for c in SUPPORTED_CLASSES};seen=set()
 for row in p.rows:
  if len(row)<3:continue
  school=' '.join(str(row[0]).split()).strip();n=re.sub(r'[^0-9]','',str(row[1]));region=re.sub(r'[^0-9]','',str(row[2]))
  if not school or n not in {str(i) for i in range(1,8)} or not region:continue
  c=f'{n}A';k=(school.casefold(),c,region)
  if k in seen:continue
  seen.add(k);g[c].append({'official_name':school,'broadcast_name':school,'state':'MS','classification':c,'region':region,'source_data':{'association':'MHSAA','provider':'MHSAA','source_url':OFFICIAL_FOOTBALL_REGIONS_URL,'cycle':'2025-27','sport':'Football'}})
 total=sum(map(len,g.values()));missing=[c for c,v in g.items() if not v]
 if total<150 or missing:raise ValueError(f'MHSAA_PARSE_INCOMPLETE total={total} missing={missing}')
 return g
def _refresh(d):
 g=_parse(_fetch())
 for c,schools in g.items():
  p=_path(d,c)
  if c=='5A' and p.exists():continue
  _write(p,{'classification':c,'cycle':'2025-27','sport':'Football','source':{'provider':'MHSAA','title':'2025-27 Football Regions','url':OFFICIAL_FOOTBALL_REGIONS_URL},'schools':schools})
 return g
def _manifest(d,c):
 raw=json.loads(_path(d,c).read_text(encoding='utf-8'))
 if not isinstance(raw,dict) or not isinstance(raw.get('schools'),list):raise ValueError('INVALID_MANIFEST')
 return raw
def _scope(d,s):
 classes=SUPPORTED_CLASSES if s=='STATEWIDE' else (s,);rows=[];missing=[]
 for c in classes:
  if not _path(d,c).exists():missing.append(c);continue
  rows.extend(_manifest(d,c)['schools'])
 if missing:raise FileNotFoundError(', '.join(missing))
 return rows
def _valid(s):s=str(s or '').upper();return s if s=='STATEWIDE' or s in SUPPORTED_CLASSES else None

class _MaisParser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.depth=0;self.buf=[];self.names=[]
 def handle_starttag(self,t,a):
  if t.lower() in {'button','a'}:self.depth+=1;self.buf=[]
 def handle_data(self,d):
  if self.depth:self.buf.append(d)
 def handle_endtag(self,t):
  if t.lower() in {'button','a'} and self.depth:
   name=' '.join(''.join(self.buf).split()).strip();self.depth-=1;self.buf=[]
   if _looks_like_mais_school(name):self.names.append(name)
def _looks_like_mais_school(name):
 n=' '.join(str(name or '').split()).strip()
 if not n or len(n)<3 or len(n)>90:return False
 low=n.casefold()
 if low in {'school','search','clear','submit','member school directory','home'}:return False
 if len(n)==1 and n.isalpha():return False
 terms=('school','academy','christian','chr.','prep','preparatory','catholic','institute','college','mra','wcca','msaisnet')
 return any(t in low for t in terms)
def _mais_path(d):return d/'mais_member_schools.json'
def _mais_profile():return {'id':'mais-member-schools','name':'MAIS Member School Directory','association':'MAIS','state':'MS','source_type':'manifest','source_url':MAIS_DIRECTORY_URL,'field_mapping':{'official_name':'official_name','broadcast_name':'broadcast_name','state':'state','classification':'classification','region':'region','source_data':'source_data'},'defaults':{'state':'MS'},'options':{'create_venues':True,'venue_sport':'Football','update_existing_fields':['state']}}
def _fetch_mais():
 req=urllib.request.Request(MAIS_DIRECTORY_URL,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'text/html,application/xhtml+xml','Accept-Language':'en-US,en;q=0.8'})
 with urllib.request.urlopen(req,timeout=25,context=ssl.create_default_context()) as x:body=x.read().decode(x.headers.get_content_charset() or 'utf-8',errors='replace')
 p=_MaisParser();p.feed(body);seen=set();out=[]
 for name in p.names:
  k=name.casefold()
  if k in seen:continue
  seen.add(k);out.append({'official_name':name,'broadcast_name':name,'state':'MS','classification':'','region':'','source_data':{'association':'MAIS','provider':'MAIS Member School Directory','source_url':MAIS_DIRECTORY_URL,'branding_status':'not_provided_by_directory'}})
 if len(out)<40:raise ValueError(f'MAIS_DIRECTORY_PARSE_INCOMPLETE total={len(out)}')
 return out
def _load_mais(d):
 raw=json.loads(_mais_path(d).read_text(encoding='utf-8'));rows=raw.get('schools')
 if not isinstance(rows,list):raise ValueError('INVALID_MAIS_MANIFEST')
 return rows


class _BrandingPageParser(HTMLParser):
 def __init__(self,base):super().__init__(convert_charrefs=True);self.base=base;self.in_title=False;self.title=[];self.metas=[];self.images=[];self.links=[]
 def handle_starttag(self,t,attrs):
  t=t.lower();a={str(k).lower():str(v or '') for k,v in attrs}
  if t=='title':self.in_title=True
  elif t=='meta':self.metas.append(a)
  elif t=='img':self.images.append(a)
  elif t=='link':self.links.append(a)
 def handle_endtag(self,t):
  if t.lower()=='title':self.in_title=False
 def handle_data(self,d):
  if self.in_title:self.title.append(d)
def _safe_branding_url(value):
 from urllib.parse import urlparse
 import ipaddress,socket
 u=urlparse(str(value or '').strip())
 if u.scheme not in {'http','https'} or not u.hostname:raise ValueError('INVALID_BRANDING_URL')
 if u.hostname.casefold() in {'localhost','127.0.0.1','::1'}:raise ValueError('LOCAL_BRANDING_URL_BLOCKED')
 for info in socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM):
  ip=ipaddress.ip_address(info[4][0])
  if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:raise ValueError('PRIVATE_BRANDING_URL_BLOCKED')
 return u.geturl()
def _inspect_branding_page(url):
 from urllib.parse import urljoin
 safe=_safe_branding_url(url);req=urllib.request.Request(safe,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'text/html,application/xhtml+xml'})
 with urllib.request.urlopen(req,timeout=20,context=ssl.create_default_context()) as x:
  final=x.geturl();body=x.read(1500000).decode(x.headers.get_content_charset() or 'utf-8',errors='replace')
 p=_BrandingPageParser(final);p.feed(body);title=' '.join(''.join(p.title).split());desc=''
 for m in p.metas:
  key=(m.get('property') or m.get('name') or '').casefold()
  if key in {'description','og:description','twitter:description'} and m.get('content'):desc=m['content'];break
 logos=[]
 def add(v,label):
  u=urljoin(final,str(v or '').strip())
  if u.startswith(('http://','https://')) and u not in [x['url'] for x in logos]:logos.append({'url':u,'label':label})
 for m in p.metas:
  key=(m.get('property') or m.get('name') or '').casefold()
  if key in {'og:image','twitter:image','twitter:image:src'}:add(m.get('content'),key)
 for x in p.images:
  hint=' '.join([x.get('alt',''),x.get('class',''),x.get('id','')]).casefold()
  if any(k in hint for k in ('logo','mascot','crest','mark')):add(x.get('src'),'page image')
 for x in p.links:
  if 'icon' in x.get('rel','').casefold():add(x.get('href'),'site icon')
 colors=[];seen=set()
 for token in re.findall(r'#[0-9a-fA-F]{6}\\b',body):
  c=token.upper()
  if c in seen:continue
  seen.add(c);rgb=tuple(int(c[j:j+2],16) for j in (1,3,5))
  if max(rgb)-min(rgb)<18 and (max(rgb)<45 or min(rgb)>220):continue
  colors.append(c)
  if len(colors)>=8:break
 mascot='';combined=' '.join([title,desc])
 patterns=[r"home of the\\s+([A-Z][A-Za-z0-9&' -]{2,35})",r"([A-Z][A-Za-z0-9&' -]{2,30})\\s+Athletics"]
 for pat in patterns:
  m=re.search(pat,combined,re.I)
  if m:mascot=' '.join(m.group(1).split()).strip(' -|');break
 return {'requested_url':safe,'final_url':final,'title':title,'description':desc,'logo_candidates':logos[:8],'color_candidates':colors,'mascot_candidate':mascot}


def _fetch_branding_image(url):
 safe=_safe_branding_url(url)
 req=urllib.request.Request(safe,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'image/*,*/*;q=0.8'})
 with urllib.request.urlopen(req,timeout=20,context=ssl.create_default_context()) as x:
  final=x.geturl();content_type=str(x.headers.get('Content-Type') or '').split(';',1)[0].strip().lower()
  if content_type not in {'image/png','image/jpeg','image/webp'}:
   raise ValueError('UNSUPPORTED_BRANDING_IMAGE')
  body=x.read(8*1024*1024+1)
  if len(body)>8*1024*1024:raise ValueError('BRANDING_IMAGE_TOO_LARGE')
 return final,content_type,body


class _DiscoveryParser(HTMLParser):
 def __init__(self,base):
  super().__init__(convert_charrefs=True);self.base=base;self.in_title=False;self.title=[];self.text=[];self.links=[];self.metas=[];self.images=[]
 def handle_starttag(self,t,attrs):
  t=t.lower();a={str(k).lower():str(v or '') for k,v in attrs}
  if t=='title':self.in_title=True
  elif t=='a':
   href=a.get('href','')
   if href:self.links.append({'href':urllib.parse.urljoin(self.base,href),'text':''})
  elif t=='meta':self.metas.append(a)
  elif t=='img':self.images.append(a)
 def handle_endtag(self,t):
  if t.lower()=='title':self.in_title=False
 def handle_data(self,d):
  clean=' '.join(str(d).split())
  if not clean:return
  self.text.append(clean)
  if self.in_title:self.title.append(clean)
  if self.links:self.links[-1]['text']=(self.links[-1].get('text','')+' '+clean).strip()

def _fetch_html(url,limit=1500000):
 safe=_safe_branding_url(url)
 req=urllib.request.Request(safe,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'text/html,application/xhtml+xml','Accept-Language':'en-US,en;q=0.8'})
 with urllib.request.urlopen(req,timeout=20,context=ssl.create_default_context()) as x:
  final=x.geturl();ctype=str(x.headers.get('Content-Type') or '').lower()
  if 'text/html' not in ctype and 'application/xhtml+xml' not in ctype:raise ValueError('NOT_HTML')
  body=x.read(limit+1)
  if len(body)>limit:body=body[:limit]
  return final,body.decode(x.headers.get_content_charset() or 'utf-8',errors='replace')

def _name_tokens(name):
 return [x.casefold() for x in re.findall(r'[A-Za-z0-9]+',str(name or '')) if len(x)>2 and x.casefold() not in {'school','high','academy','christian','the'}]

def _candidate_matches_school(title,body,name,city=''):
 hay=(' '.join([title,body[:12000]])).casefold()
 tokens=_name_tokens(name)
 if tokens and sum(1 for t in tokens if t in hay) >= max(1,min(2,len(tokens))):return True
 if city and str(city).casefold() in hay and tokens and any(t in hay for t in tokens):return True
 return False

def _discover_mhsaa_website(name):
 try:final,body=_fetch_html('https://www.misshsaa.com/school-web-sites/')
 except Exception:return ''
 parser=_DiscoveryParser(final);parser.feed(body);tokens=_name_tokens(name);best=''
 for link in parser.links:
  text=str(link.get('text') or '').casefold()
  if tokens and all(t in text for t in tokens[:2]):
   href=str(link.get('href') or '')
   if href.startswith(('http://','https://')) and 'misshsaa.com' not in urllib.parse.urlparse(href).netloc.casefold():return href
   best=href or best
 return best

def _candidate_domain_stems(name):
 raw=''.join(ch.lower() if ch.isalnum() else ' ' for ch in str(name or ''))
 words=[w for w in raw.split() if w not in {'the','of'}]
 # Prefer the full institutional name; then remove common trailing school terms.
 stems=[]
 def add(parts):
  stem=''.join(parts)
  if len(stem)>=4 and stem not in stems:stems.append(stem)
 add(words)
 trim=list(words)
 while trim and trim[-1] in {'school','academy','christian','preparatory','prep','institute'}:
  trim=trim[:-1];add(trim)
 if len(words)>=2:add([words[0],words[-1]])
 return stems[:5]

def _discover_domain_probe(name,city,state):
 hosts=[]
 for stem in _candidate_domain_stems(name):
  for host in (f'{stem}.com',f'{stem}.org',f'{stem}.net'):
   hosts.append(host)
  # Common school-domain convention.
  if len(stem)>5:
   for host in (f'www.{stem}.com',f'www.{stem}.org'):
    hosts.append(host)
 for host in hosts[:18]:
  for scheme in ('https','http'):
   url=f'{scheme}://{host}/'
   try:
    f,b=_fetch_html(url,600000);p=_DiscoveryParser(f);p.feed(b);title=' '.join(p.title);text=' '.join(p.text)
    if _candidate_matches_school(title,text,name,city):return f
   except Exception:continue
 return ''

def _search_result_links(search_url):
 try:final,body=_fetch_html(search_url,900000)
 except Exception:return []
 p=_DiscoveryParser(final);p.feed(body);out=[]
 for link in p.links[:120]:
  href=str(link.get('href') or '').strip()
  if 'uddg=' in href:
   try:href=urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('uddg',[''])[0]
   except Exception:pass
  if href.startswith(('http://','https://')) and href not in out:out.append(href)
 return out

def _discover_web_search(name,city,state):
 # First try predictable official-school domains. This handles many private schools
 # without relying on a search engine and every candidate is identity-verified.
 direct=_discover_domain_probe(name,city,state)
 if direct:return direct
 q=' '.join(x for x in [name,city,state,'official school athletics'] if x)
 searches=[
  'https://www.bing.com/search?q='+urllib.parse.quote_plus(q),
  'https://html.duckduckgo.com/html/?q='+urllib.parse.quote_plus(q),
 ]
 blocked=('facebook.com','instagram.com','x.com','twitter.com','maxpreps.com','hudl.com','niche.com','greatschools.org','wikipedia.org','youtube.com','bing.com','duckduckgo.com')
 seen=set()
 for search_url in searches:
  for href in _search_result_links(search_url):
   if href in seen:continue
   seen.add(href)
   host=urllib.parse.urlparse(href).netloc.casefold()
   if not host or any(x in host for x in blocked):continue
   try:
    f,b=_fetch_html(href,600000);p=_DiscoveryParser(f);p.feed(b);title=' '.join(p.title);text=' '.join(p.text)
    if _candidate_matches_school(title,text,name,city):return f
   except Exception:continue
 return ''

def _same_domain(base,url):
 try:
  a=urllib.parse.urlparse(base).netloc.casefold().removeprefix('www.')
  b=urllib.parse.urlparse(url).netloc.casefold().removeprefix('www.')
  return bool(a and a==b)
 except Exception:return False

def _extract_address(text):
 raw=str(text or '')
 # Normalize HTML/page text into sentence-like chunks while preserving likely address boundaries.
 chunks=[re.sub(r'\s+',' ',x).strip(' ,;|-') for x in re.split(r'[\n\r•|]+',raw) if str(x).strip()]
 suffix=r'(?:Road|Rd\.?|Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Highway|Hwy\.?|Parkway|Pkwy\.?|Way|Circle|Cir\.?|Court|Ct\.?|Trail|Trl\.?)'
 street_pat=rf'(\d{{1,6}}\s+[A-Za-z0-9 .#\'-]{{2,60}}?\s{suffix})'
 full_pat=re.compile(rf'{street_pat}\s*,?\s*([A-Za-z .\'-]{{2,40}})\s*,?\s*([A-Z]{{2}})\s+(\d{{5}}(?:-\d{{4}})?)',re.I)

 # Prefer a compact full address within one chunk.
 for chunk in chunks:
  m=full_pat.search(chunk)
  if m:
   return {'address1':' '.join(m.group(1).split()),'city':' '.join(m.group(2).split()),'state':m.group(3).upper(),'postal_code':m.group(4)}

 # Fall back to scanning the complete text, but only keep the street portion beginning at the street number.
 compact=re.sub(r'\s+',' ',raw)
 m=full_pat.search(compact)
 if m:
  return {'address1':' '.join(m.group(1).split()),'city':' '.join(m.group(2).split()),'state':m.group(3).upper(),'postal_code':m.group(4)}

 # Last resort: street-only candidate, intentionally excluding any prose before the first street number.
 street_only=re.search(street_pat,compact,re.I)
 if street_only:
  return {'address1':' '.join(street_only.group(1).split())}
 return {}

def _extract_phone(text):
 m=re.search(r'(?<!\d)(?:\+?1[ .-]?)?\(?([2-9]\d{2})\)?[ .-](\d{3})[ .-](\d{4})(?!\d)',str(text or ''))
 return f'{m.group(1)}.{m.group(2)}.{m.group(3)}' if m else ''

def _extract_socials(links):
 out={}
 for x in links:
  href=str(x.get('href') or '');low=href.casefold()
  if 'facebook.com/' in low and 'share' not in low:out.setdefault('facebook',href)
  elif ('twitter.com/' in low or 'x.com/' in low):out.setdefault('x',href)
  elif 'instagram.com/' in low:out.setdefault('instagram',href)
  elif 'youtube.com/' in low or 'youtu.be/' in low:out.setdefault('youtube',href)
 return out

def _discover_site_pages(home_url,home_parser):
 keys=('athletics','athletic','sports','contact','facilities','facility','football','about')
 scored=[]
 for link in home_parser.links:
  href=str(link.get('href') or '');txt=(' '.join([str(link.get('text') or ''),href])).casefold()
  if not _same_domain(home_url,href):continue
  score=sum(1 for k in keys if k in txt)
  if score:scored.append((score,href))
 seen=set();out=[]
 for _,href in sorted(scored,key=lambda x:-x[0]):
  clean=href.split('#',1)[0]
  if clean in seen:continue
  seen.add(clean);out.append(clean)
  if len(out)>=8:break
 return out

def _auto_enrich_school(payload):
 name=str(payload.get('official_name') or payload.get('broadcast_name') or '').strip()
 city=str(payload.get('city') or '').strip();state=str(payload.get('state') or 'MS').strip().upper()
 association=str(payload.get('association') or '').strip().upper()
 supplied=str(payload.get('website') or '').strip()
 supplied_sources=payload.get('websites') or []
 if isinstance(supplied_sources,str):
  supplied_sources=[x.strip() for x in re.split(r'[\n,;]+',supplied_sources) if x.strip()]
 if not isinstance(supplied_sources,list):supplied_sources=[]
 source_url=str(payload.get('source_url') or '').strip()
 if not name:raise ValueError('SCHOOL_NAME_REQUIRED')

 association_hosts=('misshsaa.com','msais.org')
 candidates=[]
 def add_candidate(url,method):
  u=str(url or '').strip()
  if not u:return
  host=urllib.parse.urlparse(u).netloc.casefold()
  if any(h in host for h in association_hosts):return
  if u not in [x[0] for x in candidates]:candidates.append((u,method))

 add_candidate(supplied,'provided_school_website')
 for u in supplied_sources:add_candidate(u,'operator_added_source')
 if association=='MHSAA':
  add_candidate(_discover_mhsaa_website(name),'mhsaa_directory')
 add_candidate(_discover_web_search(name,city,state),'web_discovery')

 if not candidates:raise ValueError('OFFICIAL_WEBSITE_NOT_FOUND')

 verified=[]
 for candidate_url,method in candidates:
  try:
   f,b=_fetch_html(candidate_url);p=_DiscoveryParser(f);p.feed(b);title=' '.join(p.title);text=' '.join(p.text)
   if _candidate_matches_school(title,text,name,city):
    verified.append({'url':f,'title':title,'text':text,'parser':p,'method':method})
  except Exception:
   continue
 if not verified:raise ValueError('DISCOVERED_SITE_IDENTITY_MISMATCH')

 # The first verified source becomes the canonical school website. All verified operator
 # sources are still crawled and merged for enrichment.
 first=verified[0];final=first['url'];discovery=first['method'];hp=first['parser']
 pages=[]
 seen_pages=set()
 def add_page(url,title,text,parser):
  key=str(url).split('#',1)[0]
  if key in seen_pages:return
  seen_pages.add(key);pages.append({'url':url,'title':title,'text':text,'parser':parser})

 for row in verified:
  add_page(row['url'],row['title'],row['text'],row['parser'])
  for url in _discover_site_pages(row['url'],row['parser']):
   try:
    f,b=_fetch_html(url,900000);p=_DiscoveryParser(f);p.feed(b)
    add_page(f,' '.join(p.title),' '.join(p.text),p)
   except Exception:continue
 all_text=' '.join(p['text'] for p in pages)
 address={}
 for p in pages:
  address=_extract_address(p['text'])
  if address:break
 phone=_extract_phone(all_text);socials={}
 for p in pages:
  for k,v in _extract_socials(p['parser'].links).items():socials.setdefault(k,v)
 athletics_url='';football_url=''
 for p in pages:
  low=(p['title']+' '+p['url']).casefold()
  if not athletics_url and ('athletic' in low or '/sports' in low):athletics_url=p['url']
  if not football_url and 'football' in low:football_url=p['url']
 mascot=''
 patterns=[r"\bGo\s+([A-Z][A-Za-z0-9&' -]{2,30})[!\.]",r"\bHome of the\s+([A-Z][A-Za-z0-9&' -]{2,35})",r"\bour\s+([A-Z][A-Za-z0-9&' -]{2,30})\s+(?:teams|athletes)"]
 for pat in patterns:
  m=re.search(pat,all_text,re.I)
  if m:
   candidate=' '.join(m.group(1).split()).strip(' -|')
   if 2<len(candidate)<36:mascot=candidate;break
 brand=_inspect_branding_page(athletics_url or final);logo_urls={x['url'] for x in brand.get('logo_candidates',[])}
 for p in pages:
  for img in p['parser'].images:
   hint=' '.join([img.get('alt',''),img.get('class',''),img.get('id','')]).casefold();src=urllib.parse.urljoin(p['url'],img.get('src',''))
   if src.startswith(('http://','https://')) and any(k in hint for k in ('logo','mascot','crest','mark')) and src not in logo_urls:
    brand.setdefault('logo_candidates',[]).append({'url':src,'label':'crawled official page'});logo_urls.add(src)
    if len(brand['logo_candidates'])>=12:break
 confidence={'website':'verified','address':'verified' if address else 'missing','mascot':'high' if mascot else 'missing','athletics_url':'high' if athletics_url else 'missing','logo':'review' if brand.get('logo_candidates') else 'missing','colors':'review' if brand.get('color_candidates') else 'missing'}
 return {'school_name':name,'association':association,'website':final,'discovery_method':discovery,'address':address,'phone':phone,'socials':socials,'athletics_url':athletics_url,'football_url':football_url,'mascot_candidate':mascot or brand.get('mascot_candidate',''),'color_candidates':brand.get('color_candidates',[])[:8],'logo_candidates':brand.get('logo_candidates',[])[:12],'pages_checked':[{'url':p['url'],'title':p['title']} for p in pages],'verified_sources':[{'url':x['url'],'method':x['method']} for x in verified],'confidence':confidence}


def _strip_html(value):
 return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',str(value or ''))).strip()

def _bing_rss_search(query,limit=8):
 url='https://www.bing.com/search?format=rss&q='+urllib.parse.quote_plus(query)
 try:
  safe=_safe_branding_url(url)
  req=urllib.request.Request(safe,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'application/rss+xml,application/xml,text/xml,*/*;q=0.8'})
  with urllib.request.urlopen(req,timeout=18,context=ssl.create_default_context()) as x:
   body=x.read(900000)
  root=ET.fromstring(body)
  out=[]
  for item in root.findall('.//item')[:limit]:
   title=_strip_html(item.findtext('title') or '')
   link=(item.findtext('link') or '').strip()
   desc=_strip_html(item.findtext('description') or '')
   if link.startswith(('http://','https://')):
    out.append({'title':title,'url':link,'snippet':desc,'engine':'bing-rss'})
  return out
 except Exception:
  return []

def _ddg_search_results(query,limit=8):
 url='https://html.duckduckgo.com/html/?q='+urllib.parse.quote_plus(query)
 try:
  final,body=_fetch_html(url,900000)
 except Exception:
  return []
 p=_DiscoveryParser(final);p.feed(body);out=[];seen=set()
 for link in p.links:
  href=str(link.get('href') or '').strip()
  if 'uddg=' in href:
   try:href=urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('uddg',[''])[0]
   except Exception:pass
  if not href.startswith(('http://','https://')) or href in seen:continue
  seen.add(href)
  text=' '.join(str(link.get('text') or '').split())
  if text:
   out.append({'title':text,'url':href,'snippet':'','engine':'duckduckgo'})
  if len(out)>=limit:break
 return out

def _research_search(query,limit=8):
 rows=_bing_rss_search(query,limit)
 if len(rows)<3:
  for x in _ddg_search_results(query,limit):
   if x['url'] not in [y['url'] for y in rows]:rows.append(x)
   if len(rows)>=limit:break
 return rows[:limit]

def _source_rank(url,official_host=''):
 host=urllib.parse.urlparse(str(url or '')).netloc.casefold().removeprefix('www.')
 official=official_host.casefold().removeprefix('www.')
 if official and (host==official or host.endswith('.'+official)):return 100,'official'
 if host.endswith('.edu') or host.endswith('.k12.ms.us'):return 90,'official/public'
 if 'misshsaa.com' in host or 'msais.org' in host:return 85,'association'
 if any(x in host for x in ('maxpreps.com','hudl.com','ahsfhs.org')):return 55,'sports-database'
 if any(x in host for x in ('facebook.com','instagram.com','x.com','twitter.com')):return 45,'social'
 return 65,'secondary'

def _clean_candidate_text(value):
 value=' '.join(str(value or '').split()).strip(' ,;:-|')
 return value[:120]

def _extract_venue_names(text):
 raw=' '.join(str(text or '').split())
 patterns=[
  r'\bStadium\s*:\s*([A-Z][A-Za-z0-9 .&\'-]{2,60}?(?:Field|Stadium|Complex|Park))\b',
  r'\b(?:football\s+(?:team\s+)?(?:plays|play|hosts?)\s+(?:home\s+games\s+)?at)\s+([A-Z][A-Za-z0-9 .&\'-]{2,60}?(?:Field|Stadium|Complex|Park))\b',
  r'\bLocation\s*:\s*([A-Z][A-Za-z0-9 .&\'-]{2,60}?(?:Field|Stadium|Complex|Park))(?=\s+(?:with|at|for|$)|[.,;])',
  r'\bat\s+([A-Z][A-Za-z0-9 .&\'-]{2,60}?(?:Field|Stadium|Complex|Park))\b',
 ]
 out=[]
 for pat in patterns:
  for m in re.finditer(pat,raw,re.I):
   v=_clean_candidate_text(m.group(1))
   # Strip leading generic words accidentally captured.
   v=re.sub(r'^(?:the|their|our)\s+','',v,flags=re.I)
   if v and v.casefold() not in [x.casefold() for x in out]:out.append(v)
 return out[:6]

def _extract_mascots(text):
 raw=' '.join(str(text or '').split())
 patterns=[
  r'\bMascot\s*:\s*([A-Z][A-Za-z0-9 &\'-]{2,35})',
  r'\bTeam\s+Name\s*:\s*(?:[A-Z][A-Za-z0-9 .&\'-]{2,60}\s+)?([A-Z][A-Za-z0-9&\'-]{2,30})',
  r'\bHome\s+of\s+the\s+([A-Z][A-Za-z0-9 &\'-]{2,35})',
  r'\bGo\s+([A-Z][A-Za-z0-9&\'-]{2,30})[!.]',
 ]
 out=[]
 for pat in patterns:
  for m in re.finditer(pat,raw,re.I):
   v=_clean_candidate_text(m.group(1))
   v=re.split(r'\s{2,}|[|;]',v)[0].strip()
   if 2<len(v)<36 and v.casefold() not in [x.casefold() for x in out]:out.append(v)
 return out[:5]

_COLOR_NAMES=('Red','Blue','Navy','Royal Blue','Scarlet','White','Black','Gold','Maroon','Green','Orange','Purple','Silver','Gray','Grey','Crimson','Cardinal','Teal','Yellow')
def _extract_named_colors(text):
 raw=' '.join(str(text or '').split())
 out=[]
 m=re.search(r'\bColors?\s*:\s*([A-Za-z,& /-]{3,80})',raw,re.I)
 if m:
  segment=m.group(1)
  segment=re.split(r'\b(?:Coach|Stadium|Mascot|Record|Address|Location)\b',segment,flags=re.I)[0]
  for name in _COLOR_NAMES:
   if re.search(r'\b'+re.escape(name)+r'\b',segment,re.I) and name not in out:out.append(name)
 return out[:5]

def _candidate_key(value):
 if isinstance(value,dict):
  return json.dumps(value,sort_keys=True).casefold()
 return re.sub(r'[^a-z0-9]+','',str(value).casefold())

def _add_field_candidate(store,field,value,source,rank,source_type,evidence=''):
 if not value:return
 bucket=store.setdefault(field,[])
 key=_candidate_key(value)
 for row in bucket:
  if row['key']==key:
   row['score']+=max(10,rank//5);row['corroborations']+=1
   if source not in [x['url'] for x in row['sources']]:
    row['sources'].append({'url':source,'type':source_type,'evidence':evidence[:260]})
   return
 bucket.append({'key':key,'value':value,'score':rank,'corroborations':1,'sources':[{'url':source,'type':source_type,'evidence':evidence[:260]}]})


def _fetch_xml_urls(url,limit=250):
 try:
  safe=_safe_branding_url(url)
  req=urllib.request.Request(safe,headers={'User-Agent':'Mozilla/5.0 CSRN/1.0','Accept':'application/xml,text/xml,*/*;q=0.8'})
  with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as x:
   body=x.read(1200000)
  root=ET.fromstring(body)
  urls=[]
  for loc in root.findall('.//{*}loc'):
   value=(loc.text or '').strip()
   if value.startswith(('http://','https://')):urls.append(value)
   if len(urls)>=limit:break
  return urls
 except Exception:
  return []

def _official_site_research_urls(website):
 if not website:return []
 parsed=urllib.parse.urlparse(website)
 root=f'{parsed.scheme}://{parsed.netloc}'
 sitemap_candidates=[root+'/sitemap.xml',root+'/sitemap_index.xml']
 urls=[];seen=set()
 for sitemap in sitemap_candidates:
  for u in _fetch_xml_urls(sitemap,300):
   # If this is a nested sitemap, inspect it too.
   if u.lower().endswith('.xml') and len(urls)<300:
    for child in _fetch_xml_urls(u,300):
     if child not in seen:seen.add(child);urls.append(child)
   elif u not in seen:
    seen.add(u);urls.append(u)
 keywords=('football','athletic','sports','facility','facilities','stadium','field','camp','summer','venue')
 scored=[]
 for u in urls:
  low=u.casefold()
  score=sum(1 for k in keywords if k in low)
  if score:scored.append((score,u))
 # Add conventional pages even when absent from sitemap.
 for path in ('/athletics','/sports','/facilities','/football','/summercamps','/summer-camps'):
  u=root+path
  if u not in seen:scored.append((1,u))
 out=[]
 for _,u in sorted(scored,key=lambda x:-x[0]):
  if u not in out:out.append(u)
  if len(out)>=24:break
 return out

def _research_official_venue_pages(name,city,website,fields,results):
 if not website:return
 official_host=urllib.parse.urlparse(website).netloc
 for url in _official_site_research_urls(website):
  try:
   final,body=_fetch_html(url,1000000);p=_DiscoveryParser(final);p.feed(body)
   title=' '.join(p.title);text=' '.join(p.text)
   if not _candidate_matches_school(title,text,name,city):continue
   rank,stype=_source_rank(final,official_host)
   results.append({'query':'official-site venue crawl','title':title,'url':final,'snippet':'','rank':rank,'source_type':stype})
   addr=_extract_address(text)
   if addr:_add_field_candidate(fields,'school_address',addr,final,rank,stype,title)
   for v in _extract_venue_names(text):
    _add_field_candidate(fields,'venue_name',v,final,rank,stype,title)
   for v in _extract_mascots(text):
    _add_field_candidate(fields,'mascot',v,final,rank,stype,title)
   for v in _extract_named_colors(text):
    _add_field_candidate(fields,'named_colors',v,final,rank,stype,title)
  except Exception:
   continue


def _school_identity_tokens(name,city,state):
 stop={'school','high','academy','the','of','and','inc'}
 name_tokens=[x for x in re.findall(r'[a-z0-9]+',str(name).casefold()) if len(x)>2 and x not in stop]
 city_tokens=[x for x in re.findall(r'[a-z0-9]+',str(city).casefold()) if len(x)>2]
 state_tokens=[str(state or '').casefold()]
 return name_tokens,city_tokens,state_tokens

def _identity_gate(title,text,url,name,city,state,official_host='',known_mascots=None):
 host=urllib.parse.urlparse(str(url or '')).netloc.casefold().removeprefix('www.')
 official=official_host.casefold().removeprefix('www.')
 if official and (host==official or host.endswith('.'+official)):
  return True,100,'official-domain'
 hay=(' '.join([str(title or ''),str(text or '')])).casefold()
 name_tokens,city_tokens,state_tokens=_school_identity_tokens(name,city,state)
 name_hits=sum(1 for x in name_tokens if re.search(r'\b'+re.escape(x)+r'\b',hay))
 city_hit=bool(city_tokens) and any(re.search(r'\b'+re.escape(x)+r'\b',hay) for x in city_tokens)
 state_hit=bool(state and (re.search(r'\b'+re.escape(str(state).casefold())+r'\b',hay) or ('mississippi' in hay if str(state).upper()=='MS' else False)))
 mascot_hit=any(re.search(r'\b'+re.escape(str(x).casefold())+r'\b',hay) for x in (known_mascots or []) if x)
 strong_name=(name_hits>=max(1,min(2,len(name_tokens))))
 # External pages must prove school identity. A school-name match alone is not enough.
 if strong_name and city_hit:return True,85,'name+city'
 if strong_name and state_hit and mascot_hit:return True,80,'name+state+mascot'
 if strong_name and city_hit and state_hit:return True,90,'name+city+state'
 return False,0,'identity-unproven'

def _discover_linked_athletics_sites(website,name,city):
 if not website:return []
 try:
  final,body=_fetch_html(website,1000000);p=_DiscoveryParser(final);p.feed(body)
 except Exception:return []
 base_host=urllib.parse.urlparse(final).netloc.casefold().removeprefix('www.')
 candidates=[]
 for link in p.links:
  href=str(link.get('href') or '').strip();txt=' '.join(str(link.get('text') or '').split())
  if not href:continue
  u=urllib.parse.urljoin(final,href)
  if not u.startswith(('http://','https://')):continue
  host=urllib.parse.urlparse(u).netloc.casefold().removeprefix('www.')
  blob=(u+' '+txt).casefold()
  if any(k in blob for k in ('athletic','sports','teams','football','schedule')):
   score=0
   if host!=base_host:score+=3
   if 'athletic' in blob:score+=3
   if 'sports' in blob:score+=2
   if 'teams' in blob:score+=1
   candidates.append((score,u))
 out=[]
 for _,u in sorted(candidates,key=lambda x:-x[0]):
  if u not in out:out.append(u)
  if len(out)>=12:break
 return out

def _verified_corpus_urls(website,name,city):
 urls=[]
 def add(u):
  u=str(u or '').strip()
  if u and u not in urls:urls.append(u)
 add(website)
 for u in _discover_linked_athletics_sites(website,name,city):add(u)
 for u in _official_site_research_urls(website):add(u)
 return urls[:40]

def _build_verified_corpus(name,city,state,website,supplied):
 official_host=urllib.parse.urlparse(str(website or '')).netloc
 seeds=[]
 for u in [website,*(supplied or [])]:
  if u and u not in seeds:seeds.append(u)
 for u in _verified_corpus_urls(website,name,city):
  if u not in seeds:seeds.append(u)
 pages=[];seen=set()
 for url in seeds:
  if url in seen:continue
  seen.add(url)
  try:
   final,body=_fetch_html(url,1000000);p=_DiscoveryParser(final);p.feed(body)
   title=' '.join(p.title);text=' '.join(p.text)
   ok,identity_score,reason=_identity_gate(title,text,final,name,city,state,official_host)
   if not ok:continue
   rank,stype=_source_rank(final,official_host)
   pages.append({'url':final,'title':title,'text':text,'parser':p,'rank':max(rank,identity_score),'source_type':stype,'identity_reason':reason})
   # A verified athletics page can expose another athletics host.
   for link in p.links:
    href=urllib.parse.urljoin(final,str(link.get('href') or ''))
    label=(' '.join(str(link.get('text') or '').split())+' '+href).casefold()
    if href.startswith(('http://','https://')) and any(k in label for k in ('athletic','sports','team','football')):
     if href not in seen and len(seeds)<60:seeds.append(href)
  except Exception:continue
 return pages

def _extract_fields_from_verified_page(page,fields):
 url=page['url'];rank=page['rank'];stype=page['source_type'];title=page['title'];text=page['text']
 addr=_extract_address(text)
 if addr:_add_field_candidate(fields,'school_address',addr,url,rank,stype,title)
 for v in _extract_venue_names(text):_add_field_candidate(fields,'venue_name',v,url,rank,stype,title)
 for v in _extract_mascots(text):_add_field_candidate(fields,'mascot',v,url,rank,stype,title)
 for v in _extract_named_colors(text):_add_field_candidate(fields,'named_colors',v,url,rank,stype,title)

def _research_queries(name,city,state,website=''):
 place=' '.join(x for x in [city,state] if x).strip()
 rows=[
  ('identity',f'"{name}" {place} official school athletics'),
  ('venue',f'"{name}" {place} football field stadium venue'),
  ('venue',f'"{name}" {place} "football camp" field'),
  ('branding',f'"{name}" {place} mascot colors athletics'),
  ('contact',f'"{name}" {place} address contact athletics director'),
 ]
 host=urllib.parse.urlparse(str(website or '')).netloc
 if host:
  rows.insert(1,('venue',f'site:{host} "{name}" football field stadium'))
  rows.insert(2,('venue',f'site:{host} "Location:" "Field" football'))
 return rows

def _search_assisted_research(payload):
 name=str(payload.get('official_name') or payload.get('broadcast_name') or '').strip()
 city=str(payload.get('city') or '').strip();state=str(payload.get('state') or 'MS').strip().upper()
 website=str(payload.get('website') or '').strip()
 supplied=payload.get('websites') or []
 if isinstance(supplied,str):supplied=[x.strip() for x in re.split(r'[\n,;]+',supplied) if x.strip()]
 if not isinstance(supplied,list):supplied=[]
 if not name:raise ValueError('SCHOOL_NAME_REQUIRED')

 # If the school website is not already known, use the existing discovery path first.
 if not website:
  association=str(payload.get('association') or '').strip().upper()
  if association=='MHSAA':website=_discover_mhsaa_website(name) or ''
  if not website:website=_discover_web_search(name,city,state) or ''

 official_host=urllib.parse.urlparse(website).netloc if website else ''
 fields={};results=[];rejected=[]

 # PHASE 1: Build a verified corpus from the official school site, linked athletics
 # sites, operator-provided official sources, and relevant official-site pages.
 corpus=_build_verified_corpus(name,city,state,website,supplied)
 for page in corpus:
  _extract_fields_from_verified_page(page,fields)
  results.append({'query':'verified corpus','title':page['title'],'url':page['url'],'snippet':'','rank':page['rank'],'source_type':page['source_type'],'identity':page['identity_reason']})

 known_mascots=[x['value'] for x in fields.get('mascot',[]) if x.get('value')]

 # PHASE 2: Only search externally for fields that remain weak/missing. Every external
 # result must pass the strict school-identity gate BEFORE extraction.
 weak_fields={k for k in ('venue_name','school_address','mascot','named_colors') if not fields.get(k) or max(x['score'] for x in fields.get(k,[]))<100}
 queries=_research_queries(name,city,state,website)
 if weak_fields:
  seen={x['url'] for x in results}
  for qtype,query in queries:
   # Skip unrelated query classes when their field is already strong.
   if qtype=='venue' and 'venue_name' not in weak_fields:continue
   if qtype=='branding' and not ({'mascot','named_colors'} & weak_fields):continue
   if qtype=='contact' and 'school_address' not in weak_fields:continue
   for row in _research_search(query,8):
    url=row['url']
    if url in seen:continue
    seen.add(url)
    rank,stype=_source_rank(url,official_host)
    title=row.get('title','');snippet=row.get('snippet','')
    ok,identity_score,reason=_identity_gate(title,snippet,url,name,city,state,official_host,known_mascots)
    page_text=snippet;page_title=title;final=url
    # Search snippets can prove enough to justify fetching, but candidates are only
    # extracted after the fetched page itself passes identity.
    try:
     f,b=_fetch_html(url,900000);p=_DiscoveryParser(f);p.feed(b)
     final=f;page_title=' '.join(p.title);page_text=' '.join(p.text)
     ok,identity_score,reason=_identity_gate(page_title,page_text,final,name,city,state,official_host,known_mascots)
    except Exception:
     # Never extract from an un-fetched external snippet.
     ok=False;reason='fetch-failed'
    if not ok:
     rejected.append({'url':url,'title':title,'reason':reason,'query':qtype})
     continue
    effective=max(rank,identity_score)
    page={'url':final,'title':page_title,'text':page_text,'rank':effective,'source_type':stype,'identity_reason':reason}
    _extract_fields_from_verified_page(page,fields)
    results.append({'query':qtype,'title':page_title,'url':final,'snippet':'','rank':effective,'source_type':stype,'identity':reason})

 # Rank and expose only candidates that survived identity gating.
 output={}
 for field,rows in fields.items():
  rows.sort(key=lambda x:(x['score'],x['corroborations']),reverse=True)
  cleaned=[]
  for x in rows[:8]:
   confidence='review'
   if x['score']>=100 or x['corroborations']>=2:confidence='high'
   if any(s['type']=='official' for s in x['sources']) and x['corroborations']>=2:confidence='verified'
   cleaned.append({'value':x['value'],'score':x['score'],'corroborations':x['corroborations'],'confidence':confidence,'sources':x['sources']})
  output[field]=cleaned

 return {
  'school_name':name,'official_website':website,'queries':[q for _,q in queries],
  'fields':output,'search_results':sorted(results,key=lambda x:x['rank'],reverse=True)[:40],
  'verified_corpus_count':len(corpus),'rejected_external_count':len(rejected),
  'rejected_external':rejected[:20]
 }

def create_mhsaa_division_blueprint(*,require_auth:Callable,get_import_service:Callable[[],Any],imports_dir:Path)->Blueprint:
 routes=Blueprint('mhsaa_division_routes',__name__)
 @routes.get('/api/imports/associations')
 @require_auth
 def associations():return jsonify({'associations':[{'id':'MHSAA','name':'Mississippi High School Activities Association','state':'MS','sports':['Football'],'classifications':['STATEWIDE','7A','6A','5A','4A','3A','2A','1A']},{'id':'MAIS','name':'Mid-South Association of Independent Schools','state':'MS','sports':['Football'],'classifications':['STATEWIDE'],'branding':'manual_or_school_source'}]})
 @routes.post('/api/imports/association/MAIS/refresh')
 @require_auth
 def refresh_mais():
  try:
   schools=_fetch_mais();_write(_mais_path(imports_dir),{'association':'MAIS','source':{'provider':'MAIS Member School Directory','url':MAIS_DIRECTORY_URL},'schools':schools})
  except Exception as e:return jsonify({'error':'MAIS_REFRESH_FAILED','message':'The official MAIS member-school directory could not be refreshed. Existing local MAIS data was left unchanged.','detail':str(e)}),502
  return jsonify({'association':'MAIS','total_schools':len(schools),'classifications':['STATEWIDE'],'source_url':MAIS_DIRECTORY_URL,'message':f'MAIS refresh complete: {len(schools)} member schools. MAIS does not publish dependable mascot, colors, logo, or football classification in this directory, so CSRN will not guess those fields.'})
 @routes.post('/api/imports/association/MHSAA/refresh')
 @require_auth
 def refresh():
  try:g=_refresh(imports_dir)
  except Exception as e:return jsonify({'error':'MHSAA_REFRESH_FAILED','message':'The official MHSAA list could not be refreshed. Existing local manifests were left unchanged.','detail':str(e)}),502
  return jsonify({'association':'MHSAA','classifications':list(SUPPORTED_CLASSES),'total_schools':sum(len(v) for v in g.values()),'counts':{k:len(v) for k,v in g.items()},'source_url':OFFICIAL_FOOTBALL_REGIONS_URL})
 @routes.get('/api/imports/association/<association>/<scope>/candidates')
 @require_auth
 def candidates(association,scope):
  association=str(association).upper()
  if association not in {'MHSAA','MAIS'}:return jsonify({'error':'ASSOCIATION_NOT_CONFIGURED','message':f'{association} is not configured for automated import yet.'}),404
  if association=='MAIS':
   if str(scope).upper()!='STATEWIDE':return jsonify({'error':'UNSUPPORTED_MAIS_SCOPE','message':'MAIS currently uses Statewide because its member directory does not expose a dependable football-class field.'}),400
   try:rows=_load_mais(imports_dir)
   except FileNotFoundError:return jsonify({'error':'MAIS_MANIFEST_MISSING','message':'Local MAIS data is missing. Select Refresh Association List first.'}),404
   svc=get_import_service();res=svc.analyze(_mais_profile(),rows)
   if not res.ok:return jsonify({'error':res.code,'message':'Could not analyze MAIS member schools.'}),400
   d=res.data;out=[]
   for item in d.get('schools',[]):
    x=item.get('candidate') or {};out.append({'official_name':x.get('official_name',''),'broadcast_name':x.get('broadcast_name',''),'classification':'','region':'','status':item.get('status',''),'matches':item.get('matches',[]),'school_id':item.get('school_id','')})
   out.sort(key=lambda x:str(x.get('official_name') or '').casefold())
   return jsonify({'association':'MAIS','scope':'STATEWIDE','found':d.get('found',0),'new':d.get('new',0),'existing':d.get('existing',0),'possible_duplicates':d.get('possible_duplicates',0),'invalid':d.get('invalid',0),'schools':out})
  scope=_valid(scope)
  if not scope:return jsonify({'error':'UNSUPPORTED_SCOPE','message':'Choose Statewide or 1A through 7A.'}),400
  try:rows=_scope(imports_dir,scope)
  except FileNotFoundError as e:return jsonify({'error':'MANIFEST_MISSING','message':f'Local MHSAA data is missing for {e}. Select Refresh Association List first.'}),404
  svc=get_import_service();out=[];tot={'found':0,'new':0,'existing':0,'possible_duplicates':0,'invalid':0};by={}
  for row in rows:by.setdefault(str(row.get('classification') or ''),[]).append(row)
  for c,items in by.items():
   r=svc.analyze(_profile(c),items)
   if not r.ok:return jsonify({'error':r.code,'message':f'Could not analyze MHSAA {c}.'}),400
   d=r.data
   for k in tot:tot[k]+=int(d.get(k,0))
   for item in d.get('schools',[]):
    x=item.get('candidate') or {};out.append({'official_name':x.get('official_name',''),'broadcast_name':x.get('broadcast_name',''),'classification':x.get('classification',c),'region':x.get('region',''),'status':item.get('status',''),'matches':item.get('matches',[]),'school_id':item.get('school_id','')})
  out.sort(key=lambda x:(-int(re.sub(r'[^0-9]','',str(x.get('classification') or '0')) or 0),int(re.sub(r'[^0-9]','',str(x.get('region') or '999')) or 999),str(x.get('official_name') or '').casefold()))
  return jsonify({'association':'MHSAA','scope':scope,**tot,'schools':out})
 @routes.post('/api/imports/association/<association>/<scope>/selected')
 @require_auth
 def selected(association,scope):
  association=str(association).upper()
  if association not in {'MHSAA','MAIS'}:return jsonify({'error':'ASSOCIATION_NOT_CONFIGURED','message':f'{association} is not configured yet.'}),404
  if association=='MAIS':
   if str(scope).upper()!='STATEWIDE':return jsonify({'error':'UNSUPPORTED_MAIS_SCOPE','message':'MAIS currently uses Statewide.'}),400
   p=request.get_json(silent=True) or {};names=p.get('schools') or []
   if not isinstance(names,list) or not names:return jsonify({'error':'NO_SCHOOLS_SELECTED','message':'Select at least one school.'}),400
   wanted={str(n).strip().casefold() for n in names if str(n).strip()}
   try:allrows=_load_mais(imports_dir)
   except FileNotFoundError:return jsonify({'error':'MAIS_MANIFEST_MISSING','message':'Refresh the MAIS association list first.'}),404
   rows=[x for x in allrows if str(x.get('official_name') or '').strip().casefold() in wanted]
   if not rows:return jsonify({'error':'SELECTED_SCHOOLS_NOT_FOUND','message':'Selected MAIS schools were not found.'}),400
   res=get_import_service().apply(_mais_profile(),rows,create_venues=bool(p.get('create_venues',True)),allow_possible_duplicates=False)
   if not res.ok:return jsonify({'error':res.code,'message':'MAIS selected-school import failed.'}),400
   d=res.data;return jsonify({'association':'MAIS','scope':'STATEWIDE','selected':len(rows),'imported':d.get('imported',0),'enriched_existing':d.get('enriched_existing',0),'skipped_existing':d.get('skipped_existing',0),'created_ids':d.get('created_ids',[]),'possible_duplicates':d.get('possible_duplicates',[]),'invalid':d.get('invalid',[])})
  scope=_valid(scope)
  if not scope:return jsonify({'error':'UNSUPPORTED_SCOPE','message':'Choose Statewide or 1A through 7A.'}),400
  p=request.get_json(silent=True) or {};names=p.get('schools') or []
  if not isinstance(names,list) or not names:return jsonify({'error':'NO_SCHOOLS_SELECTED','message':'Select at least one school.'}),400
  wanted={str(n).strip().casefold() for n in names if str(n).strip()}
  try:rows=_scope(imports_dir,scope)
  except FileNotFoundError as e:return jsonify({'error':'MANIFEST_MISSING','message':f'Local MHSAA data is missing for {e}. Refresh first.'}),404
  rows=[x for x in rows if str(x.get('official_name') or '').strip().casefold() in wanted]
  if not rows:return jsonify({'error':'SELECTED_SCHOOLS_NOT_FOUND','message':'Selected schools were not found in the current association list.'}),400
  svc=get_import_service();by={};result={'imported':0,'enriched_existing':0,'skipped_existing':0,'created_ids':[],'possible_duplicates':[],'invalid':[]}
  for x in rows:by.setdefault(str(x.get('classification') or ''),[]).append(x)
  for c,items in by.items():
   r=svc.apply(_profile(c),items,create_venues=bool(p.get('create_venues',True)),allow_possible_duplicates=False)
   if not r.ok:return jsonify({'error':r.code,'message':f'Import failed while applying MHSAA {c} selections.'}),400
   d=r.data
   for k in ('imported','enriched_existing','skipped_existing'):result[k]+=int(d.get(k,0))
   for k in ('created_ids','possible_duplicates','invalid'):result[k].extend(d.get(k,[]))
  return jsonify({'association':'MHSAA','scope':scope,'selected':len(rows),**result})
 # R1 backward compatibility
 @routes.post('/api/imports/mhsaa/<classification>/refresh')
 @require_auth
 def legacy_refresh(classification):
  c=_valid(classification)
  if not c or c=='STATEWIDE':return jsonify({'error':'UNSUPPORTED_SCOPE'}),400
  try:
   if c=='5A' and _path(imports_dir,c).exists():return jsonify({'classification':c,'schools':len(_manifest(imports_dir,c)['schools']),'preserved':True})
   g=_refresh(imports_dir);return jsonify({'classification':c,'schools':len(g[c]),'preserved':False})
  except Exception as e:return jsonify({'error':'MHSAA_REFRESH_FAILED','message':'Unable to refresh official MHSAA list.','detail':str(e)}),502
 @routes.get('/api/imports/mhsaa/<classification>/analyze')
 @require_auth
 def legacy_analyze(classification):
  c=_valid(classification)
  if not c or c=='STATEWIDE':return jsonify({'error':'UNSUPPORTED_SCOPE'}),400
  try:rows=_scope(imports_dir,c)
  except FileNotFoundError:return jsonify({'error':'MANIFEST_MISSING','message':f'{c} has not been refreshed yet.'}),404
  r=get_import_service().analyze(_profile(c),rows)
  if not r.ok:return jsonify({'error':r.code}),400
  d=r.data;schools=[]
  for item in d.get('schools',[]):
   x=item.get('candidate') or {};schools.append({'official_name':x.get('official_name',''),'broadcast_name':x.get('broadcast_name',''),'classification':x.get('classification',c),'region':x.get('region',''),'status':item.get('status',''),'matches':item.get('matches',[])})
  return jsonify({'classification':c,'found':d.get('found',0),'new':d.get('new',0),'existing':d.get('existing',0),'possible_duplicates':d.get('possible_duplicates',0),'invalid':d.get('invalid',0),'schools':schools})
 @routes.post('/api/imports/mhsaa/<classification>')
 @require_auth
 def legacy_apply(classification):
  c=_valid(classification)
  if not c or c=='STATEWIDE':return jsonify({'error':'UNSUPPORTED_SCOPE'}),400
  try:rows=_scope(imports_dir,c)
  except FileNotFoundError:return jsonify({'error':'MANIFEST_MISSING','message':f'{c} has not been refreshed yet.'}),404
  p=request.get_json(silent=True) or {};r=get_import_service().apply(_profile(c),rows,create_venues=bool(p.get('create_venues',True)),allow_possible_duplicates=True)
  if not r.ok:return jsonify({'error':r.code}),400
  d=r.data;return jsonify({'classification':c,'imported':d.get('imported',0),'enriched_existing':d.get('enriched_existing',0),'skipped_existing':d.get('skipped_existing',0),'created_ids':d.get('created_ids',[]),'total_schools':d.get('total_schools',0)})
 @routes.post('/api/imports/branding/inspect')
 @require_auth
 def inspect_branding():
  p=request.get_json(silent=True) or {};url=str(p.get('url') or '').strip()
  if not url:return jsonify({'error':'BRANDING_URL_REQUIRED','message':'Enter the official school or athletics website URL first.'}),400
  try:data=_inspect_branding_page(url)
  except ValueError as e:return jsonify({'error':str(e),'message':'That branding source URL is not allowed or could not be resolved.'}),400
  except Exception as e:return jsonify({'error':'BRANDING_INSPECTION_FAILED','message':'The branding source could not be inspected. Try the school official homepage or athletics page.','detail':str(e)}),502
  return jsonify(data)
 @routes.post('/api/imports/branding/image')
 @require_auth
 def fetch_branding_image():
  p=request.get_json(silent=True) or {};url=str(p.get('url') or '').strip()
  if not url:return jsonify({'error':'BRANDING_IMAGE_URL_REQUIRED','message':'Choose a logo candidate first.'}),400
  try:final,content_type,body=_fetch_branding_image(url)
  except ValueError as e:return jsonify({'error':str(e),'message':'That candidate image could not be acquired safely.'}),400
  except Exception as e:return jsonify({'error':'BRANDING_IMAGE_FETCH_FAILED','message':'The selected logo candidate could not be downloaded.','detail':str(e)}),502
  response=Response(body,mimetype=content_type)
  response.headers['X-CSRN-Branding-Source']=final
  response.headers['Cache-Control']='no-store'
  return response
 @routes.post('/api/imports/enrichment/auto')
 @require_auth
 def auto_enrich():
  payload=request.get_json(silent=True) or {}
  try:data=_auto_enrich_school(payload)
  except ValueError as e:
   code=str(e);messages={'SCHOOL_NAME_REQUIRED':'School name is required before enrichment.','OFFICIAL_WEBSITE_NOT_FOUND':'CSRN could not confidently discover an official school website. Enter a verified website once, then run enrichment again.','DISCOVERED_SITE_IDENTITY_MISMATCH':'A candidate website was found but could not be confidently matched to this school, so no data was applied.'}
   return jsonify({'error':code,'message':messages.get(code,'Automatic enrichment could not complete safely.')}),400
  except Exception as e:return jsonify({'error':'AUTO_ENRICHMENT_FAILED','message':'Automatic school enrichment failed. Existing school data was not changed.','detail':str(e)}),502
  return jsonify(data)
 @routes.post('/api/imports/enrichment/research')
 @require_auth
 def research_enrichment():
  payload=request.get_json(silent=True) or {}
  try:data=_search_assisted_research(payload)
  except ValueError as e:return jsonify({'error':str(e),'message':'School name is required before search-assisted research.'}),400
  except Exception as e:return jsonify({'error':'SEARCH_ASSISTED_RESEARCH_FAILED','message':'Search-assisted school research failed. Existing school data was not changed.','detail':str(e)}),502
  return jsonify(data)
 return routes
