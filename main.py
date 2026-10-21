import datetime
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="어제 일별 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스")

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 계산
# -----------------------------------------------------------------------------
# 배포 서버(Streamlit Cloud) 시계가 UTC이므로, 한국 표준시(Asia/Seoul) 기준 시각을 사용합니다.
kst_tz = ZoneInfo("Asia/Seoul")
now_kst = datetime.datetime.now(kst_tz)
yesterday_kst = now_kst - datetime.timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD)
target_dt = yesterday_kst.strftime("%Y%m%d")
# 화면 표시용 날짜 형식 (YYYY년 MM월 DD일)
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")

st.caption(f"📅 조회 기준일: {display_date} ({target_dt})")

# -----------------------------------------------------------------------------
# 3. KOBIS 비밀키 확인 및 API 요청
# -----------------------------------------------------------------------------
# Secrets에 KOBIS_KEY가 없는 경우 안내 후 중단
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 **API 키(KOBIS_KEY)를 찾을 수 없습니다.**")
    st.info(
        "**[확인 방법]**\n\n"
        "1. **Streamlit Cloud 배포 시:** 앱 설정의 `App settings` > `Secrets` 메뉴에 아래와 같이 입력하세요.\n"
        "   ```toml\n"
        "   KOBIS_KEY = \"발급받은_인증키_문자열\"\n"
        "   ```\n"
        "2. **로컬 테스트 시:** 프로젝트 폴더 내 `.streamlit/secrets.toml` 파일에 위 내용을 작성하세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

# 네트워크 요청
try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
except Exception as e:
    st.error("🚨 **서버와의 통신 중 오류가 발생했습니다.**")
    st.info(
        "**[확인 방법]**\n\n"
        "1. 인터넷 연결 상태를 확인해 주세요.\n"
        "2. 영화진흥위원회(KOBIS) 서버에 일시적인 장애가 있는지 확인해 주세요."
    )
    st.stop()

# -----------------------------------------------------------------------------
# 4. API 오류 응답 및 빈 데이터 검증
# -----------------------------------------------------------------------------
# KOBIS API는 인증키가 틀려도 상태코드 200과 함께 faultInfo 객체를 전달합니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 **KOBIS API 호출 오류가 발생했습니다.**")
    st.warning(f"오류 메시지: {fault.get('message', '알 수 없는 오류')}")
    st.info(
        "**[확인 방법]**\n\n"
        "1. 등록된 `KOBIS_KEY`가 올바른 키인지 확인해 주세요.\n"
        "2. KOBIS 오픈API 마이페이지에서 키가 활성화되어 있는지 확인해 주세요.\n"
        "3. 일일 요청 제한 횟수를 초과했는지 확인해 주세요."
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있는 경우
if not daily_list:
    st.warning("⚠️ **조회된 박스오피스 영화 목록이 없습니다.**")
    st.info(
        "**[확인 방법]**\n\n"
        "1. 새벽 시간대에는 어제의 데이터 집계가 아직 완료되지 않았을 수 있습니다.\n"
        "2. 영화진흥위원회 통합전산망 서버 집계 상황을 잠시 후 다시 확인해 주세요."
    )
    st.stop()

# -----------------------------------------------------------------------------
# 5. 데이터 변환 및 가공
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# 문자열로 들어오는 숫자 데이터들을 정수형(int)으로 변환
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------------------------------------------------------
# 6. 1위 영화 지표 카드 3장
# -----------------------------------------------------------------------------
top1 = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위 영화: {top1['movieNm']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="현재 순위", value=f"{top1['rank']}위")
with col2:
    st.metric(label="어제 관객수", value=f"{top1['audiCnt']:,} 명")
with col3:
    st.metric(label="누적 관객수", value=f"{top1['audiAcc']:,} 명")

st.divider()

# -----------------------------------------------------------------------------
# 7. 관객수 상위 5편 막대그래프
# -----------------------------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

top5_df = df.head(5).copy()
# 시각화를 위한 데이터 정리 (영화명을 인덱스로 지정)
chart_data = top5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["관객수"]

st.bar_chart(chart_data)

st.divider()

# -----------------------------------------------------------------------------
# 8. 전체 박스오피스 순위표
# -----------------------------------------------------------------------------
st.subheader("📋 박스오피스 전체 순위표")

# 필요한 컬럼만 추출 및 한글 명칭으로 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 표에 보여줄 수치에 천 단위 쉼표 포맷팅 적용
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
