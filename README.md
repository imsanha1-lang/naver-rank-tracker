# 네이버 지도 순위 추적 (GitHub Actions · 무료)

내 PC나 커서가 꺼져 있어도, **GitHub 서버가 매일 낮 12시(한국시간)에 자동으로**
네이버 지도에서 내 매장의 검색 순위를 기록합니다. 결과는 GitHub Pages로 만든
무료 사이트에서 언제든 확인할 수 있습니다.

```
매일 12:00 KST → GitHub Actions 가 순위 수집 → rankings.json 에 저장(자동 커밋)
                                        ↓
                     GitHub Pages 대시보드(index.html)가 그래프로 표시
```

## 구성 파일
| 파일 | 역할 |
|------|------|
| `.github/workflows/track.yml` | 매일 12시 자동 실행 + 수동 실행 |
| `track.py` | 대상 목록을 읽어 순위 수집 → 결과 저장 |
| `scraper.py` | 네이버 지도 순위 스크래퍼 (headless) |
| `docs/index.html` | 대시보드 (GitHub Pages로 배포) |
| `docs/data/targets.json` | 추적할 (키워드 + 매장명) 목록 ← **여기를 편집** |
| `docs/data/rankings.json` | 수집된 순위 기록 (자동 갱신) |

---

## 설치 방법 (딱 한 번만)

### 1. GitHub 저장소 만들기
1. https://github.com 가입/로그인
2. 우측 상단 **＋ → New repository**
3. 이름 입력(예: `naver-rank-tracker`), **Public** 선택 → **Create repository**

### 2. 이 폴더를 저장소에 올리기
이 폴더(`naver-rank-tracker-gh`)에서 아래 명령을 실행합니다. (PowerShell)
```powershell
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/본인아이디/저장소이름.git
git push -u origin main
```
> git이 없다면 https://git-scm.com/download/win 에서 설치하세요.

### 3. GitHub Actions 권한 켜기 (자동 커밋용)
저장소 페이지 → **Settings → Actions → General**
→ 맨 아래 **Workflow permissions** 에서 **Read and write permissions** 선택 → Save

### 4. GitHub Pages 켜기 (사이트 배포)
저장소 페이지 → **Settings → Pages**
→ **Source: Deploy from a branch**
→ Branch: **main**, 폴더: **/docs** 선택 → Save
→ 잠시 뒤 `https://본인아이디.github.io/저장소이름/` 주소가 생깁니다.

### 5. 추적할 매장 등록
`docs/data/targets.json` 파일을 아래처럼 편집합니다. (GitHub 웹에서 연필 아이콘으로 편집 가능)
```json
[
  { "keyword": "강남역 미용실", "place_name": "OOO헤어" },
  { "keyword": "성수동 카페",   "place_name": "OO커피" }
]
```
> 대시보드 하단 "매장 관리"에서 목록을 만들고 **[JSON 복사]** 한 뒤 이 파일에 붙여넣어도 됩니다.

---

## 사용
- **자동**: 매일 낮 12시(KST)에 알아서 수집·기록됩니다. (PC 꺼져 있어도 OK)
- **수동 실행**: 저장소 → **Actions 탭 → "네이버 순위 수집" → Run workflow** 버튼
- **결과 보기**: GitHub Pages 주소로 접속

## 자주 묻는 것
- **PC를 꺼도 되나요?** 네. GitHub 서버에서 돌기 때문에 내 PC/커서와 무관합니다.
- **비용은?** Public 저장소면 GitHub Actions·Pages 모두 무료입니다.
- **순위가 계속 "미노출"로 나와요.** 네이버가 화면 구조를 바꿨거나, 데이터센터 IP를 차단한 경우입니다.
  `scraper.py` 의 `NAME_SELECTORS` / `AD_SELECTORS` 선택자를 최신 구조에 맞게 수정하세요.
- **차단 위험**: 네이버는 클라우드(데이터센터) 접속을 가정용 IP보다 강하게 차단합니다.
  자주 막히면 실행 주기를 늘리거나 프록시가 필요할 수 있습니다.

## 로컬에서 테스트
```powershell
pip install -r requirements.txt
python track.py          # docs/data/targets.json 을 읽어 수집 후 rankings.json 갱신
python scraper.py "강남역 미용실" "박승철헤어스투디오"   # 단건 테스트
```
