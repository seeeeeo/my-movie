import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 화면 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="KOBIS 일일 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망")


# ---------------------------------------------------------
# 2. 한국 시간 기준 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul을 사용한다.
kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API에서 조회할 수 있는 가장 늦은 날짜를 어제로 제한한다.


# ---------------------------------------------------------
# 3. 날짜 선택
# ---------------------------------------------------------
st.subheader("📅 조회 날짜")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜를 선택하세요.",
    value=yesterday_kst,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday_kst
)

# 혹시 잘못된 날짜가 들어오면 한 번 더 확인
if selected_date > yesterday_kst:
    st.error("오늘 날짜의 박스오피스는 아직 집계 전입니다.")
    st.stop()

# API용 날짜 형식: YYYYMMDD
target_date = selected_date.strftime("%Y%m%d")


# ---------------------------------------------------------
# 4. KOBIS 인증키 가져오기
# ---------------------------------------------------------
# 실제 인증키는 코드에 작성하지 않는다.
# Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해야 한다.
try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]

except Exception:
    st.error("🔑 KOBIS_KEY를 찾을 수 없습니다.")

    st.info(
        "Streamlit Cloud의 앱 설정 → Secrets에서 "
        "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
    )

    st.stop()


# ---------------------------------------------------------
# 5. KOBIS API 주소
# ---------------------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 6. 문자열 숫자를 정수로 바꾸는 함수
# ---------------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달되므로
# 그래프와 정렬에 사용할 수 있도록 숫자로 변환한다.
def to_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------
# 7. KOBIS API 호출
# ---------------------------------------------------------
# 같은 날짜의 데이터를 다시 요청하면
# 최대 1시간 동안 캐시된 결과를 사용한다.
@st.cache_data(ttl=3600, show_spinner=False)
def get_boxoffice(target_date, api_key):

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "type": "request",
            "message": str(e),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "type": "json",
            "message": "API 응답을 JSON으로 읽을 수 없습니다.",
            "data": None
        }


    # -----------------------------------------------------
    # 인증키 오류 등으로 faultInfo가 오는 경우
    # -----------------------------------------------------
    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        return {
            "success": False,
            "type": "fault",
            "message": fault_info.get(
                "message",
                "KOBIS API 오류가 발생했습니다."
            ),
            "data": None
        }


    # -----------------------------------------------------
    # boxOfficeResult 확인
    # -----------------------------------------------------
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:

        return {
            "success": False,
            "type": "empty",
            "message": "boxOfficeResult가 없습니다.",
            "data": None
        }


    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )


    # -----------------------------------------------------
    # 영화 목록이 비어 있는 경우
    # -----------------------------------------------------
    if not movie_list:

        return {
            "success": False,
            "type": "no_movies",
            "message": "영화 목록이 없습니다.",
            "data": None
        }


    # -----------------------------------------------------
    # 필요한 데이터만 표로 정리
    # -----------------------------------------------------
    rows = []

    for movie in movie_list:

        rows.append({
            "순위": to_int(movie.get("rank")),
            "rankInten": to_int(movie.get("rankInten")),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int(movie.get("audiCnt")),
            "누적관객": to_int(movie.get("audiAcc")),
            "스크린수": to_int(movie.get("scrnCnt")),
        })


    df = pd.DataFrame(rows)

    return {
        "success": True,
        "type": None,
        "message": "",
        "data": df
    }


# ---------------------------------------------------------
# 8. 선택한 날짜의 데이터 가져오기
# ---------------------------------------------------------
with st.spinner("박스오피스 데이터를 가져오는 중입니다..."):

    result = get_boxoffice(
        target_date,
        KOBIS_KEY
    )


# ---------------------------------------------------------
# 9. API 오류 처리
# ---------------------------------------------------------
if not result["success"]:

    if result["type"] == "no_movies":

        st.warning("📭 그날은 아직 집계 전입니다.")

        st.info(
            f"{selected_date.strftime('%Y년 %m월 %d일')}의 "
            "박스오피스 영화 목록이 없습니다.\n\n"
            "KOBIS에서 해당 날짜의 데이터가 아직 제공되지 "
            "않았거나 해당 날짜에 집계된 영화관입장권 데이터가 "
            "없는 것일 수 있습니다."
        )


    elif result["type"] == "fault":

        st.error("⚠️ KOBIS API에서 오류가 반환되었습니다.")

        st.info(
            "다음 내용을 확인해 주세요.\n\n"
            "• Streamlit Secrets의 KOBIS_KEY가 정확한지 확인\n"
            "• KOBIS 인증키가 정상적으로 발급되었는지 확인\n"
            "• KOBIS Open API 이용에 문제가 없는지 확인\n\n"
            f"API 오류 메시지: {result['message']}"
        )


    elif result["type"] == "request":

        st.error("🌐 KOBIS API에 접속하지 못했습니다.")

        st.info(
            "다음 내용을 확인해 주세요.\n\n"
            "• 인터넷 연결 상태\n"
            "• KOBIS Open API 서버 상태\n"
            "• API 주소가 정상적으로 동작하는지 확인\n\n"
            f"오류 내용: {result['message']}"
        )


    elif result["type"] == "json":

        st.error("📄 API 응답을 읽을 수 없습니다.")

        st.info(
            "KOBIS API가 정상적인 JSON 데이터를 반환했는지 "
            "확인해 주세요."
        )


    else:

        st.error("⚠️ 박스오피스 데이터를 가져오지 못했습니다.")

        st.info(
            "KOBIS API 응답에 필요한 데이터가 있는지 확인해 주세요."
        )

    st.stop()


df = result["data"]


# ---------------------------------------------------------
# 10. 조회 날짜 표시
# ---------------------------------------------------------
st.subheader(
    f"📅 {selected_date.strftime('%Y년 %m월 %d일')} 박스오피스"
)


# ---------------------------------------------------------
# 11. 1위 영화
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "영화",
        first_movie["영화명"]
    )

with col2:
    st.metric(
        "당일 관객수",
        f"{first_movie['관객수']:,}명"
    )

with col3:
    st.metric(
        "누적 관객수",
        f"{first_movie['누적관객']:,}명"
    )


# ---------------------------------------------------------
# 12. 관객수 상위 5편 그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    df
    .sort_values("관객수", ascending=False)
    .head(5)
    .copy()
)

chart_data = top5.set_index("영화명")[["관객수"]]

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 13. 영화명에 트로피 붙이기
# ---------------------------------------------------------
def make_movie_name(row):

    movie_name = row["영화명"]

    # 누적관객이 100만 명을 초과하면 트로피 표시
    if row["누적관객"] > 1_000_000:
        movie_name += " 🏆"

    return movie_name


# ---------------------------------------------------------
# 14. 순위 변동 표시
# ---------------------------------------------------------
def make_rank_change(value):

    # rankInten이 양수면 순위가 오른 것
    if value > 0:
        return f"🔺 {value}"

    # rankInten이 음수면 순위가 내려간 것
    elif value < 0:
        return f"🔻 {abs(value)}"

    # 0이면 순위 변동 없음
    else:
        return "-"


# ---------------------------------------------------------
# 15. 표에 사용할 데이터 만들기
# ---------------------------------------------------------
display_df = df.copy()

display_df["영화명"] = display_df.apply(
    make_movie_name,
    axis=1
)

display_df["전일 대비"] = display_df["rankInten"].apply(
    make_rank_change
)


# ---------------------------------------------------------
# 16. 필요한 열만 선택
# ---------------------------------------------------------
display_df = display_df[
    [
        "순위",
        "전일 대비",
        "영화명",
        "개봉일",
        "관객수",
        "누적관객",
        "스크린수"
    ]
].copy()


# ---------------------------------------------------------
# 17. 숫자를 보기 좋게 표시
# ---------------------------------------------------------
display_df["관객수"] = display_df["관객수"].map(
    lambda x: f"{x:,}"
)

display_df["누적관객"] = display_df["누적관객"].map(
    lambda x: f"{x:,}"
)

display_df["스크린수"] = display_df["스크린수"].map(
    lambda x: f"{x:,}"
)


# ---------------------------------------------------------
# 18. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎥 전체 박스오피스")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 19. 안내 문구
# ---------------------------------------------------------
st.divider()

st.caption(
    "🔺 순위 상승   🔻 순위 하락   - 순위 변동 없음"
)

st.caption(
    "🏆 누적 관객수가 100만 명을 초과한 영화"
)
