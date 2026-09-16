import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data.json"

BID_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
SPEC_URL = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoServcPPSSrch"
PLAN_URL = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService/getOrderPlanSttusListServcPPSSrch"

KEYWORDS = [
    "AI", "인공지능", "생성형", "LLM", "RAG", "Agent", "에이전트", "NLP", "상담", "콜봇", "Voice", "음성",
    "데이터셋", "학습데이터", "데이터 가공", "데이터 정제", "데이터 품질", "데이터 표준", "데이터 플랫폼",
    "객체인식", "영상분석", "딥페이크", "헬스케어", "의료", "모빌리티", "자율주행", "산불", "재난",
    "지능형", "시스템 구축", "시스템 개발", "시스템 고도화", "플랫폼 구축", "통합관리", "정보화전략계획",
    "ISP", "ISMP", "데이터베이스", "DB 구축", "GIS", "공간정보", "유지관리", "운영 유지", "통합관제",
    "대시보드", "앱 구축", "웹 구축", "웹서비스", "디지털트윈", "스마트공장", "스마트시티", "Physical AI"
]

DC_STRONG = [
    "ai", "인공지능", "데이터", "rag", "플랫폼", "gis", "공간정보", "db", "데이터베이스", "재난", "산불",
    "관제", "isp", "ismp", "시스템 구축", "시스템 고도화", "통합관리", "대시보드", "학습데이터", "데이터 품질"
]
IJ_STRONG = [
    "llm", "agent", "에이전트", "상담", "콜봇", "voice", "음성", "nlp", "챗봇", "개인화", "생성형", "의료 ai", "헬스케어"
]

GRADE_SCORE = {"S+": 5, "S": 4, "A+": 3, "A": 2, "B+": 1, "B": 0}


def now_kst():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        return datetime.now()


def fetch_json(url, params, retries=2):
    params = dict(params)
    params["serviceKey"] = unquote(os.environ["DATA_GO_KR_API_KEY"]).strip()
    params.setdefault("type", "json")
    last = None
    for attempt in range(retries + 1):
        try:
            req = Request(url + "?" + urlencode(params), headers={"User-Agent": "DataCook-G2B-Sales/2.0"})
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"API 호출 실패: {last}")


def body_of(payload):
    response = payload.get("response") or {}
    header = response.get("header") or {}
    code = str(header.get("resultCode", "00"))
    if code not in ("00", "0", "03", ""):
        raise RuntimeError(f"OpenAPI {code}: {header.get('resultMsg', '')}")
    return response.get("body") or {}


def items_of(payload):
    body = body_of(payload)
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item") or items.get("items") or items
    if not items:
        return []
    return items if isinstance(items, list) else [items]


def contains_target(text):
    t = (text or "").lower()
    return any(k.lower() in t for k in KEYWORDS)


def grade(text, strong_words):
    t = (text or "").lower()
    score = sum(1 for w in strong_words if w.lower() in t)
    if score >= 5:
        return "S+"
    if score >= 3:
        return "S"
    if score >= 2:
        return "A+"
    if score >= 1:
        return "A"
    return "B"


def as_int(*values):
    for v in values:
        if v not in (None, ""):
            try:
                return int(float(str(v).replace(",", "")))
            except Exception:
                pass
    return 0


def parse_dt(value):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y%m%d%H%M", "%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19] if "-" in fmt else s[:14], fmt)
        except Exception:
            continue
    return None


def dday(deadline):
    dt = parse_dt(deadline)
    if not dt:
        return None
    today = now_kst().replace(tzinfo=None).date()
    return (dt.date() - today).days


def deadline_label(raw):
    dt = parse_dt(raw)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else (str(raw) if raw else "")


def priority_for(dc, ij, d_day, source):
    best = max(GRADE_SCORE.get(dc, 0), GRADE_SCORE.get(ij, 0))
    if d_day is not None and d_day < 0:
        return "마감"
    if d_day is not None and d_day < 7:
        return "⚠️ 마감임박"
    if best >= 5:
        return "🔥 S+ 최우선"
    if best >= 4:
        return "🔥 S 우선"
    if source == "발주계획" and best >= 3:
        return "🟢 선행영업"
    return "관심"


def score_for(dc, ij, d_day, source, budget):
    best = max(GRADE_SCORE.get(dc, 0), GRADE_SCORE.get(ij, 0))
    stage_bonus = {"발주계획": 30, "사전규격": 20, "본공고": 10}.get(source, 0)
    budget_bonus = 15 if budget >= 1_000_000_000 else 8 if budget >= 100_000_000 else 0
    urgency = 0
    if d_day is not None:
        if d_day < 0:
            urgency = -100
        elif d_day < 7:
            urgency = -15
        elif d_day <= 21:
            urgency = 8
    return best * 20 + stage_bonus + budget_bonus + urgency


def next_action(source, d_day):
    if source == "발주계획":
        return "담당부서·기존사업자·예상 주관SI 확인 및 사전영업"
    if source == "사전규격":
        return "규격서/RFP 확인, 담당기관 접촉, 컨소시엄 선점"
    if d_day is not None and d_day < 7:
        return "마감임박: 기존 준비 여부 확인 후 GO/NO-GO"
    return "RFP·자격조건·공동수급·기존사업자 확인"


def normalize(source, raw, no):
    if source == "본공고":
        name = raw.get("bidNtceNm") or ""
        agency = raw.get("dminsttNm") or raw.get("ntceInsttNm") or ""
        budget = as_int(raw.get("asignBdgtAmt"), raw.get("presmptPrce"), raw.get("bsisAmt"))
        ident = raw.get("bidNtceNo") or ""
        deadline_raw = raw.get("bidClseDt") or ""
        expected = deadline_label(deadline_raw)
        market = "나라장터 입찰공고"
    elif source == "사전규격":
        name = raw.get("prdctClsfcNoNm") or raw.get("prdctNm") or raw.get("bfSpecNm") or ""
        agency = raw.get("orderInsttNm") or raw.get("dminsttNm") or raw.get("ntceInsttNm") or ""
        budget = as_int(raw.get("asignBdgtAmt"), raw.get("presmptPrce"))
        ident = raw.get("bfSpecRgstNo") or ""
        deadline_raw = raw.get("opninRgstClseDt") or ""
        expected = deadline_label(deadline_raw)
        market = "나라장터 사전규격"
    else:
        name = raw.get("bizNm") or raw.get("orderPlanNm") or ""
        agency = raw.get("orderInsttNm") or raw.get("dminsttNm") or ""
        budget = as_int(raw.get("sumOrderAmt"), raw.get("orderAmt"), raw.get("asignBdgtAmt"), raw.get("bdgtAmt"))
        ident = raw.get("orderPlanUntyNo") or raw.get("orderPlanNo") or ""
        deadline_raw = ""
        expected = raw.get("orderBgnYm") or raw.get("orderYm") or raw.get("orderPlanYm") or ""
        market = "나라장터 발주계획"

    text = " ".join([name, agency, raw.get("bsnsTyNm", ""), raw.get("prcrmntMethd", "")])
    dc = grade(text, DC_STRONG)
    ij = grade(text, IJ_STRONG)
    d_day = dday(deadline_raw)
    priority = priority_for(dc, ij, d_day, source)
    return {
        "no": no,
        "name": name,
        "agency": agency,
        "market": market,
        "budget": budget,
        "basis": source,
        "expected": expected,
        "deadline": deadline_label(deadline_raw),
        "dDay": d_day,
        "datacook": dc,
        "indij": ij,
        "priority": priority,
        "priorityScore": score_for(dc, ij, d_day, source, budget),
        "strategy": "공동검토" if GRADE_SCORE.get(ij, 0) >= 3 else "데이터쿡 중심",
        "next": next_action(source, d_day),
        "stage": source,
        "status": "미접촉",
        "progress": 0,
        "sourceId": ident,
    }


def collect_recent(url, source, lookback_days):
    end = now_kst().replace(second=0, microsecond=0)
    start = end - timedelta(days=lookback_days)
    common = {
        "pageNo": 1,
        "numOfRows": 999,
        "inqryBgnDt": start.strftime("%Y%m%d%H%M"),
        "inqryEndDt": end.strftime("%Y%m%d%H%M"),
    }
    if source == "본공고":
        common["inqryDiv"] = 1
    elif source == "사전규격":
        common["inqryDiv"] = 1
    else:
        common["orderBgnYm"] = f"{end.year}01"
        common["orderEndYm"] = f"{end.year + 1}12"

    try:
        rows = items_of(fetch_json(url, common))
        return rows
    except Exception as broad_error:
        print(f"[{source}] 전체조회 실패, 키워드조회로 전환: {broad_error}")

    # 전체 조회가 막힌 오퍼레이션에 대비한 fallback.
    # API 호출량을 과도하게 쓰지 않도록 핵심 키워드만 서버 검색 후 로컬에서 다시 넓게 필터한다.
    fallback_keywords = ["AI", "인공지능", "데이터", "시스템", "플랫폼", "유지관리", "GIS", "재난", "상담", "자율주행", "스마트"]
    uniq = {}
    for kw in fallback_keywords:
        params = dict(common)
        if source == "사전규격":
            params["prdctClsfcNoNm"] = kw
        elif source == "발주계획":
            params["bizNm"] = kw
        else:
            params["bidNtceNm"] = kw
        try:
            for row in items_of(fetch_json(url, params)):
                key = row.get("bidNtceNo") or row.get("bfSpecRgstNo") or row.get("orderPlanUntyNo") or json.dumps(row, ensure_ascii=False, sort_keys=True)
                uniq[str(key)] = row
        except Exception as e:
            print(f"[{source}] '{kw}' 실패: {e}")
    return list(uniq.values())


def update_all():
    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise RuntimeError("GitHub Secret DATA_GO_KR_API_KEY가 없습니다.")

    lookback = int(os.getenv("LOOKBACK_DAYS", "3"))
    data = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else {"pipeline": []}
    pipeline = data.setdefault("pipeline", [])

    # 기존 자동수집 건 식별. 수동으로 넣은 2027 예산 파이프라인은 유지한다.
    existing = {(x.get("stage"), x.get("sourceId")) for x in pipeline if x.get("sourceId")}
    next_no = max([int(x.get("no", 0)) for x in pipeline] + [0]) + 1
    stats = {}

    for source, url in (("발주계획", PLAN_URL), ("사전규격", SPEC_URL), ("본공고", BID_URL)):
        try:
            raw_rows = collect_recent(url, source, lookback)
        except Exception as e:
            print(f"[{source}] 수집 실패: {e}")
            stats[source] = {"fetched": 0, "matched": 0, "added": 0, "error": str(e)}
            continue

        matched = []
        for raw in raw_rows:
            title = raw.get("bizNm") or raw.get("prdctClsfcNoNm") or raw.get("bidNtceNm") or ""
            agency = raw.get("orderInsttNm") or raw.get("dminsttNm") or raw.get("ntceInsttNm") or ""
            if contains_target(title + " " + agency):
                matched.append(raw)

        added = 0
        for raw in matched:
            row = normalize(source, raw, next_no)
            key = (source, row.get("sourceId"))
            if row.get("sourceId") and key in existing:
                # 기존 자동수집 건의 D-Day/우선순위/마감일만 최신화한다.
                for old in pipeline:
                    if old.get("stage") == source and old.get("sourceId") == row.get("sourceId"):
                        for k in ("budget", "expected", "deadline", "dDay", "datacook", "indij", "priority", "priorityScore", "next"):
                            old[k] = row[k]
                        break
                continue
            pipeline.append(row)
            if row.get("sourceId"):
                existing.add(key)
            next_no += 1
            added += 1
        stats[source] = {"fetched": len(raw_rows), "matched": len(matched), "added": added}

    # 모든 기존 항목의 D-Day를 매 실행 시 재계산한다.
    for row in pipeline:
        if row.get("deadline"):
            row["dDay"] = dday(row["deadline"])
            row["priority"] = priority_for(row.get("datacook", "B"), row.get("indij", "B"), row.get("dDay"), row.get("stage", ""))
            row["priorityScore"] = score_for(row.get("datacook", "B"), row.get("indij", "B"), row.get("dDay"), row.get("stage", ""), int(row.get("budget") or 0))

    # S+/S 및 선행단계가 위로 오도록 기본 정렬정보를 보존한다.
    pipeline.sort(key=lambda x: (-int(x.get("priorityScore", 0)), int(x.get("dDay")) if x.get("dDay") is not None and x.get("dDay") >= 0 else 99999, int(x.get("no", 0))))
    data["updatedAt"] = now_kst().isoformat()
    data["automation"] = {
        "sources": ["발주계획", "사전규격", "본공고"],
        "lookbackDays": lookback,
        "stats": stats,
        "note": "사전규격/발주계획 API는 같은 서비스키를 사용하더라도 각 데이터셋 활용신청 승인이 필요합니다."
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    update_all()
