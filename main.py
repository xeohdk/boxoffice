import datetime
from zoneinfo import ZoneInfo
import urllib.parse
import requests
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 계산 및 달력(Date Input) 생성
# -----------------------------------------------------------------------------
kst_tz = ZoneInfo("Asia/Seoul")
now_kst = datetime.datetime.now(kst_tz)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 달력 선택 범위 제한 (오늘 날짜 선택 불가)
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday_kst,
    max_value=yesterday_kst,
    help="오늘 날짜는 아직 집계 전이므로 어제 날짜까지만 선택이 가능합니다."
)

target_dt = selected_date.strftime("%Y%m%d")
display_date = selected_date.strftime("%Y년 %m월 %d일")

st.caption(f"📅 현재 조회 기준일: {display_date} ({target_dt})")

# -----------------------------------------------------------------------------
# 3. KOBIS API 키 불러오기 (사이드바 및 Secrets 지원)
# -----------------------------------------------------------------------------
st.sidebar.header("🔑 API 키 설정")

api_key = ""

# Secrets 설정이 되어 있다면 가져오기
try:
    if "KOBIS_KEY" in st.secrets and st.secrets["KOBIS_KEY"].strip():
        api_key = st.secrets["KOBIS_KEY"].strip()
        st.sidebar.success("✅ Secrets에서 API 키를 불러왔습니다.")
except Exception:
    pass

# Secrets가 없거나 비어있는 경우 사이드바에서 키 입력받기
if not api_key:
    api_key_input = st.sidebar.text_input(
        "KOBIS API 키 입력",
        type="password",
        help="영화진흥위원회 오픈API에서 발급받은 키를 입력하세요."
    )
    if api_key_input:
        api_key = api_key_input.strip()

# 키가 둘 다 입력되지 않은 경우 안내문 표시 후 중단
if not api_key:
    st.info("💡 **API 키 입력이 필요합니다.**")
    st.warning("왼쪽 사이드바(Sidebar)에서 KOBIS API 키를 직접 입력하거나, Streamlit Cloud의 Secrets 항목에 `KOBIS_KEY`를 설정해 주세요.")
    
    with st.expander("📌 KOBIS API 키 발급 및 Secrets 저장 방법 안내"):
        st.markdown(
            "1. **[KOBIS 오픈API 웹사이트](https://www.kobis.or.kr/kobisopenapi/)** 회원가입 후 키를 발급받으세요.\n"
            "2. **임시 테스트:** 왼쪽 사이드바의 입력창에 키를 입력하세요.\n"
            "3. **배포 서버 영구 저장 (Streamlit Cloud):**\n"
            "   - 앱 화면 우측 하단 **Manage app** > **Settings** > **Secrets** 클릭\n"
            "   - 아래 내용을 입력 후 Save 클릭:\n"
            "   ```toml\n"
            "   KOBIS_KEY = \"발급받은_인증키_문자열\"\n"
            "   ```"
        )
    st.stop()

# -----------------------------------------------------------------------------
# 4. KOBIS API 요청 (User-Agent 헤더 추가 및 로딩 표시)
# -----------------------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

with st.spinner("🎬 영화진흥위원회에서 데이터를 불러오는 중입니다..."):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            st.error(f"🚨 **서버 응답 오류 (상태 코드: {response.status_code})**")
            st.info("KOBIS 서버가 일시적으로 응답하지 않거나 요청이 차단되었습니다. 잠시 후 다시 시도해 주세요.")
            st.stop()
            
        data = response.json()
    except requests.exceptions.Timeout:
        st.error("🚨 **요청 시간이 초과되었습니다.**")
        st.info("KOBIS 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()
    except Exception:
        st.error("🚨 **네트워크 통신 중 오류가 발생했습니다.**")
        st.info("인터넷 연결 상태 및 KOBIS 키 설정 상태를 확인해 주세요.")
        st.stop()

# -----------------------------------------------------------------------------
# 5. API 오류 응답 및 빈 데이터 검증
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 **KOBIS API 호출 오류가 발생했습니다.**")
    st.warning(f"오류 메시지: {fault.get('message', '알 수 없는 오류')}")
