# 2027 데이터쿡·인디제이 영업 웹 대시보드

## 실행
```bash
python server.py
```
브라우저: `http://localhost:8000`

## 나라장터 자동 업데이트
공공데이터포털에서 **조달청_나라장터 입찰공고정보서비스** 활용신청 후 API 키를 발급받습니다.

Windows PowerShell:
```powershell
$env:DATA_GO_KR_API_KEY="발급받은_디코딩키"
python server.py
```

macOS/Linux:
```bash
export DATA_GO_KR_API_KEY="발급받은_디코딩키"
python server.py
```

화면의 **신규공고 업데이트** 버튼은 최근 3일 용역 공고를 조회하고 키워드 후보를 `data.json`에 추가합니다. 조회기간은 `LOOKBACK_DAYS` 환경변수로 조절할 수 있습니다.

## 자동 실행
운영 서버에서는 cron, Windows 작업 스케줄러, GitHub Actions 또는 클라우드 스케줄러로 `/api/update`를 주기적으로 호출하면 됩니다.

## 사전규격
공식 **조달청_나라장터 사전규격정보서비스**도 같은 방식으로 연동할 수 있습니다. 현재 샘플은 입찰공고 API를 먼저 연결해 두었습니다.

## 보안
API 키는 HTML/JavaScript에 넣지 말고 서버 환경변수에만 저장하세요.
