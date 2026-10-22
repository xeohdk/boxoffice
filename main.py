import datetime
from zoneinfo import ZoneInfo
import urllib.parse
import requests
import urllib3
import pandas as pd
import streamlit as st

# KOBIS 서버 SSL 연결 경고 메시지 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
# 3. KOBIS API 키 불러오기 (Secrets 우선 사용, 없으면 메인 화면 입력창 제공)
# -----------------------------------------------------------------------------
api_key = ""

# Secrets에서 KOBIS_KEY 읽기 시도
try:
    if "KOBIS_KEY" in st.secrets and str(st.secrets["KOBIS_KEY"]).strip():
        api_key = str(st.secrets["KOBIS_KEY"]).strip()
except Exception:
    pass

# Secrets에 키가 없는 경우 메인 화면에 입력창 표시
if not api_key:
    st.info("💡 비밀 금고(Secrets)에 API 키가 등록되지 않아 수동 입력 모드로 작동 중입니다.")
    api_key_input = st.text_input(
        "🔑 KOBIS API 키를 입력해 주세요",
        type="password",
        help="영화진흥위원회 오픈API에서 발급받은 키를 입력한 뒤 엔터를 누르세요."
    )
    if api_key_input:
        api_key = api_key_input.strip()

    with st.expander("📌 Streamlit Cloud에 API 키(Secrets) 영구 저장하는 방법"):
        st.markdown(
            "1. Streamlit Cloud 앱 화면 우측 하단 **Manage app** 클릭\n"
            "2. **Settings** > **Secrets** 메뉴 선택\n"
            "3. 아래와 같이 입력 후 **Save** 클릭:\n"
            "```toml\n"
            "KOBIS_KEY = \"발급받은_인증키_문자열\"\n"
            "```"
        )

# API 키가 없으면 안내 문구 표시 후 실행 중단
if not api_key:
    st.warning("⚠️ **API 키를 입력하셔야 박스오피스 데이터를 불러올 수 있습니다.**")
    st.stop()

# -----------------------------------------------------------------------------
# 4. KOBIS API 요청 (SSL 오류 방지 및 헤더 추가)
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
        response = requests.get(
            url, 
            params=params, 
            headers=headers, 
            timeout=15, 
            verify=False  # SSL 검증 오류 방지
        )
        
        if response.status_code != 200:
            st.error(f"🚨 **서버 응답 오류 (상태 코드: {response.status_code})**")
            st.info("KOBIS 서버 응답 장애가 발생했습니다. 잠시 후 다시 시도해 주세요.")
            st.stop()
            
        data = response.json()
    except requests.exceptions.Timeout:
        st.error("🚨 **요청 시간이 초과되었습니다.**")
        st.info("KOBIS 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()
    except Exception as e:
        st.error(f"🚨 **네트워크 통신 중 오류가 발생했습니다:** {e}")
        st.info("인터넷 연결 상태 및 API 키 설정을 확인해 주세요.")
        st.stop()

# -----------------------------------------------------------------------------
# 5. API 오류 응답 및 빈 데이터 검증
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 **KOBIS API 호출 오류가 발생했습니다.**")
    st.warning(f"오류 메시지: {fault.get('message', '알 수 없는 오류')}")
    st.info(
        "**[확인 방법]**\n\n"
        "1. 입력하신 `KOBIS_
