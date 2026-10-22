import datetime
from zoneinfo import ZoneInfo
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
# 3. KOBIS API 키 불러오기 (Secrets 우선, 없으면 수동 입력)
# -----------------------------------------------------------------------------
api_key = ""

try:
    if "KOBIS_KEY" in st.secrets:
        api_key = st.secrets["KOBIS_KEY"]
except Exception:
    pass

if not api_key:
    st.info("💡 Secrets 설정이 비어 있어 수동 입력모드로 전환되었습니다.")
    api_key = st.text_input(
        "🔑 KOBIS API 키를 입력하세요", 
        type="password", 
        help="영화진흥위원회(KOBIS)에서 발급받은 인증키를 입력하세요."
    )
    
    with st.expander("📌 배포 서버(Secrets)에 키를 영구 저장하는 방법"):
        st.markdown(
            "1. Streamlit Cloud의 해당 앱 화면 우측 하단 **Manage app** 클릭\n"
            "2. **Settings** > **Secrets** 탭 선택\n"
            "3. 아래 형식으로 작성 후 **Save** 클릭:\n"
            "```toml\n"
            "KOBIS_KEY = \"발급받은_인증키_문자열\"\n"
            "```"
        )

if not api_key:
    st.warning("⚠️ API 키를 입력하셔야 박스오피스 정보 조회가 가능합니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. API 요청
# -----------------------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
except Exception:
    st.error("🚨 **서버와의 통신 중 오류가 발생했습니다.**")
    st.info("인터넷 연결 상태 및 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 5. API 오류 응답 및 빈 데이터 검증
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 **KOBIS API 호출 오류가 발생했습니다.**")
    st.warning(f"오류 메시지: {fault.get('message', '알 수 없는 오류')}")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ **그날은 아직 집계 전입니다**")
    st.info("선택하신 날짜의 박스오피스 집계 데이터가 없거나 아직 집계 중입니다. 다른 날짜를 선택해 보세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 변환 및 가공 (순위 증감, 100만 관객 트로피)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 순위 증감 화살표 가공
def format_rank_change(val):
    if val > 0:
        return f"🔺 {val}"
    elif val < 0:
        return f"🔹 {abs(val)}"
    return "-"

df["순위변동"] = df["rankInten"].apply(format_rank_change)

# 100만 관객 이상 트로피 표시
def format_movie_name(row):
    name = row["movieNm"]
    if row["audiAcc"] >= 1000000:
        return f"{name} 🏆"
    return name

df["표시_영화명"] = df.apply(format_movie_name, axis=1)

# -----------------------------------------------------------------------------
# 7. 1위 영화 지표 카드 3장
# -----------------------------------------------------------------------------
top1 = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위 영화: {top1['표시_영화명']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="현재 순위", value=f"{top1['rank']}위", delta=top1["순위변동"])
with col2:
    st.metric(label="당일 관객수", value=f"{top1['audiCnt']:,} 명")
with col3:
    st.metric(label="누적 관객수", value=f"{top1['audiAcc']:,} 명")

st.divider()

# -----------------------------------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# -----------------------------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

top5_df = df.head(5).copy()
chart_data = top5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["관객수"]

st.bar_chart(chart_data)

st.divider()

# -----------------------------------------------------------------------------
# 9. 전체 박스오피스 순위표 및 데이터 다운로드 기능
# -----------------------------------------------------------------------------
st.subheader("📋 박스오피스 전체 순위표")

display_df = df[["rank", "순위변동", "표시_영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "순위변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 수치 데이터 포맷팅
formatted_df = display_df.copy()
formatted_df["관객수"] = formatted_df["관객수"].map("{:,}".format)
formatted_df["누적관객"] = formatted_df["누적관객"].map("{:,}".format)
formatted_df["스크린수"] = formatted_df["스크린수"].map("{:,}".format)

# 테이블 출력
st.dataframe(
    formatted_df,
    use_container_width=True,
    hide_index=True
)

# -----------------------------------------------------------------------------
# [신규 기능] CSV 파일 다운로드 버튼
# -----------------------------------------------------------------------------
# 엑셀 한글 깨짐 방지를 위해 utf-8-sig 인코딩 적용
csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    label="📥 조회된 박스오피스 표 CSV로 다운로드",
    data=csv_bytes,
    file_name=f"boxoffice_{target_dt}.csv",
    mime="text/csv",
    help="현재 화면에 표시된 박스오피스 순위표를 엑셀에서 열 수 있는 CSV 파일로 저장합니다."
)
