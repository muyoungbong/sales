import os,json
from pathlib import Path
from datetime import datetime,timedelta
from urllib.parse import urlencode
from urllib.request import urlopen,Request
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data.json'
KEYWORDS=['AI','인공지능','생성형','LLM','RAG','Agent','NLP','상담','Voice','데이터셋','학습데이터','객체인식','영상분석','딥페이크','헬스케어','의료','모빌리티','자율주행','산불','재난','데이터 가공','지능형 서비스','SI','시스템 구축','플랫폼 구축','시스템 고도화','통합관리시스템','ISP','데이터베이스','DB 구축','GIS','유지관리','통합관제','대시보드','앱','웹 서비스','디지털트윈','스마트공장','스마트시티','Physical AI']
BID_API='https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc'
def fetch_json(url,params):
 req=Request(url+'?'+urlencode(params),headers={'User-Agent':'G2B-Sales-Dashboard/1.0'})
 with urlopen(req,timeout=25) as r:return json.loads(r.read().decode('utf-8'))
def items_of(obj):
 body=(obj.get('response') or {}).get('body') or {};items=body.get('items') or []
 if isinstance(items,dict):items=items.get('item') or items.get('items') or []
 return items if isinstance(items,list) else [items]
def grade(title):
 t=title.lower();dc=sum(x.lower() in t for x in ['ai','인공지능','데이터','rag','플랫폼','gis','시스템','db','재난','관제','isp']);ij=sum(x.lower() in t for x in ['llm','agent','상담','voice','nlp','챗봇','개인화','생성형'])
 def cv(n):return 'S+' if n>=4 else 'S' if n>=3 else 'A+' if n>=2 else 'A' if n>=1 else 'B'
 return cv(dc),cv(ij)
def normalize_bid(it,no):
 title=it.get('bidNtceNm') or '';agency=it.get('dminsttNm') or it.get('ntceInsttNm') or '';budget=it.get('presmptPrce') or it.get('asignBdgtAmt') or 0
 try:budget=int(float(str(budget).replace(',','')))
 except:budget=0
 dc,ij=grade(title);close=it.get('bidClseDt') or ''
 return {'no':no,'name':title,'agency':agency,'market':'나라장터 신규','budget':budget,'basis':'입찰공고','expected':close,'datacook':dc,'indij':ij,'strategy':'검토 필요','next':'RFP/자격조건/공동수급 여부 확인','stage':'본공고','status':'미접촉','progress':0,'bidNo':it.get('bidNtceNo','')}
def update_bids():
 key=os.getenv('DATA_GO_KR_API_KEY')
 if not key:raise RuntimeError('DATA_GO_KR_API_KEY 환경변수가 없습니다.')
 end=datetime.now();start=end-timedelta(days=int(os.getenv('LOOKBACK_DAYS','3')))
 params={'serviceKey':key,'pageNo':1,'numOfRows':100,'inqryDiv':1,'type':'json','inqryBgnDt':start.strftime('%Y%m%d%H%M'),'inqryEndDt':end.strftime('%Y%m%d%H%M')}
 raw=items_of(fetch_json(BID_API,params));hits=[it for it in raw if any(k.lower() in (it.get('bidNtceNm') or '').lower() for k in KEYWORDS)]
 data=json.loads(DATA.read_text(encoding='utf-8'));existing={x.get('bidNo') for x in data['pipeline'] if x.get('bidNo')};added=0;next_no=max([x.get('no',0) for x in data['pipeline']]+[0])+1
 for it in hits:
  bid=it.get('bidNtceNo')
  if bid and bid not in existing:data['pipeline'].append(normalize_bid(it,next_no));next_no+=1;added+=1
 data['updatedAt']=datetime.now().astimezone().isoformat();DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');return {'added':added,'matched':len(hits),'fetched':len(raw)}
class Handler(SimpleHTTPRequestHandler):
 def do_POST(self):
  if self.path=='/api/update':
   try:result=update_bids();body=json.dumps(result,ensure_ascii=False).encode();self.send_response(200)
   except Exception as e:body=json.dumps({'error':str(e)},ensure_ascii=False).encode();self.send_response(500)
   self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  else:self.send_error(404)
if __name__=='__main__':
 os.chdir(ROOT);port=int(os.getenv('PORT','8000'));print(f'http://localhost:{port}');ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
