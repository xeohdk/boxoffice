import datetime
from zoneinfo import ZoneInfo
import urllib.parse
import requests
import urllib3
import pandas as pd
import streamlit as st

# SSL 경고 비활성화
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
# 2. 한국 시간(KST) 기준 '어제' 날짜 계산 및 달력 생성
# -----------------------------------------------------------------------------
kst_tz = ZoneInfo("Asia/Seoul")
now_kst = datetime.datetime.now(kst_tz)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 달력 선택 범위 제한 (최대 어제 날짜까지)
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
# 3. KOBIS API 키 불러오기 (Secrets 우선, 없으면 사이드바/메인 입력창 제공)
# -----------------------------------------------------------------------------
st.sidebar.header("🔑 API 키 설정")

api_key = ""

# Secrets에서 KOBIS_KEY 읽기 시도
try:
    if "KOBIS_KEY" in st.secrets and str(st.secrets["KOBIS_KEY"]).strip():
        api_key = str(st.secrets["KOBIS_KEY"]).strip()
        st.sidebar.success("✅ Secrets에서 API 키를 불러왔습니다.")
except Exception:
    pass

# Secrets에 키가 없는 경우 입력창 제공
if not api_key:
    api_key_input = st.sidebar.text_input(
        "KOBIS API 키 입력",
        type="password",
        help="영화진흥위원회 오픈API 키를 입력하세요."
    )
    if api_key_input:
        api_key = api_key_input.strip()

if not api_key:
    st.info("💡 **API 키 입력이 필요합니다.**")
    st.warning("왼쪽 사이드바에서 KOBIS API 키를 직접 입력하거나 Streamlit Cloud의 Secrets에 `KOBIS_KEY`를 설정해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. KOBIS API 요청
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
            verify=False
        )
        if response.status_code != 200:
            st.error(f"🚨 **서버 응답 오류 (상태 코드: {response.status_code})**")
            st.info("KOBIS 서버가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해 주세요.")
            st.stop()
            
        data = response.json()
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
    st.info("API 키가 올바른지, KOBIS 마이페이지에서 키 활성화 상태 및 일일 요청 제한을 확인해 주세요.")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ **그날은 아직 집계 전입니다**")
    st.info("선택하신 날짜의 박스오피스 집계 데이터가 없거나 아직 집계 중입니다. 다른 날짜를 선택해 보세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 변환 및 가공 (순위 증감
