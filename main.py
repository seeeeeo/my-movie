import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")


# ---------------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않고
# Asia/Seoul 시간대를 명시적으로 사용합니다.

KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# KOBIS API 호출 함수
# ---------------------------------------------------------
# st.cache_data를 사용하면 같은 입력값으로 API를 다시
# 호출하지 않고 일정 시간 동안 이전 결과를 재사용합니다.
#
# ttl=3600 → 1시간 동안 캐시
#
# target_date를 함수의 입력값으로 넣었기 때문에
# 날짜가 바뀌면 새로운 API 요청을 합니다.

@st.cache_data(ttl=3600)
def get_box_office(target_date: str):
    # Streamlit Cloud Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 적지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    # API 요청
    response = requests.get(url, params=params, timeout=10)

    # HTTP 오류가 있으면 예외를 발생시킵니다.
    response.raise_for_status()

    # JSON으로 변환
    data = response.json()

    return data


# ---------------------------------------------------------
# API 결과를 안전하게 가져오기
# ---------------------------------------------------------

try:
    data = get_box_office(target_date)

except KeyError:
    # Secrets에 KOBIS_KEY가 없는 경우
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "`KOBIS_KEY`라는 이름으로 KOBIS 인증키를 등록했는지 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    # 네트워크/API 요청 자체가 실패한 경우
    st.error(
        "KOBIS API 요청에 실패했습니다.\n\n"
        "다음 사항을 확인해 주세요:\n"
        "- 인터넷 연결 상태\n"
        "- KOBIS API 서버가 정상적으로 동작하는지\n"
        "- 조회 날짜가 정상적인 날짜인지\n"
        "- 잠시 후 다시 시도해 보기\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except ValueError:
    # JSON으로 해석할 수 없는 응답이 온 경우
    st.error(
        "KOBIS API에서 올바른 JSON 응답을 받지 못했습니다.\n\n"
        "KOBIS API 서버 상태와 네트워크 연결을 확인한 뒤 "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

except Exception as e:
    # 예상하지 못한 오류도 빈 화면으로 끝내지 않습니다.
    st.error(
        "박스오피스 데이터를 가져오는 중 문제가 발생했습니다.\n\n"
        "Streamlit Cloud의 로그와 KOBIS API 설정을 확인해 주세요.\n\n"
        f"오류 내용: {e}"
    )
    st.stop()


# ---------------------------------------------------------
# faultInfo 확인
# ---------------------------------------------------------
# KOBIS는 인증키가 잘못된 경우에도 HTTP 상태코드가
# 200으로 올 수 있습니다.
# 따라서 status_code만 확인하면 안 되고 faultInfo를 확인해야 합니다.

if "faultInfo" in data:
    fault_info = data["faultInfo"]

    fault_code = fault_info.get("errorCode", "알 수 없음")
    fault_message = fault_info.get("message", "알 수 없는 오류")

    st.error(
        "KOBIS API에서 오류를 반환했습니다.\n\n"
        "다음 사항을 확인해 주세요:\n"
        "- Streamlit Cloud Secrets에 `KOBIS_KEY`가 등록되어 있는지\n"
        "- 인증키 이름이 정확히 `KOBIS_KEY`인지\n"
        "- KOBIS에서 발급받은 인증키가 유효한지\n"
        "- API 사용 제한에 걸리지 않았는지\n\n"
        f"오류 코드: {fault_code}\n\n"
        f"오류 메시지: {fault_message}"
    )
    st.stop()


# ---------------------------------------------------------
# boxOfficeResult와 영화 목록 확인
# ---------------------------------------------------------

box_office_result = data.get("boxOfficeResult")

if not box_office_result:
    st.warning(
        "박스오피스 결과(boxOfficeResult)가 없습니다.\n\n"
        "KOBIS API 응답 형식과 API 서버 상태를 확인해 주세요."
    )
    st.stop()


movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(
        f"{display_date}의 영화 목록이 없습니다.\n\n"
        "다음 사항을 확인해 주세요:\n"
        "- 해당 날짜의 일일 박스오피스 집계가 완료되었는지\n"
        "- KOBIS API가 해당 날짜의 데이터를 제공하는지\n"
        "- 조회 날짜가 정상적으로 계산되었는지\n"
        "- 잠시 후 다시 시도해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 문자열로 받은 숫자를 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS API의 숫자 값은 문자열로 오므로
# 정렬과 그래프에 사용하기 전에 int로 변환합니다.

movies = []

for movie in movie_list:
    converted_movie = {
        "순위": int(movie.get("rank", 0)),
        "영화명": movie.get("movieNm", ""),
        "개봉일": movie.get("openDt", ""),
        "관객수": int(movie.get("audiCnt", 0)),
        "누적관객": int(movie.get("audiAcc", 0)),
        "스크린수": int(movie.get("scrnCnt", 0)),
    }

    movies.append(converted_movie)


# 순위순으로 정렬
movies.sort(key=lambda movie: movie["순위"])


# ---------------------------------------------------------
# 조회 날짜 표시
# ---------------------------------------------------------

st.caption(f"조회 날짜: {display_date} (한국 시간 기준)")


# ---------------------------------------------------------
# 1위 영화 표시
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader("🥇 1위 영화")

st.markdown(f"## {first_movie['영화명']}")

# 지표 카드 세 장
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬해서 상위 5편만 선택
top5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]

# Streamlit의 bar chart에 넣기 좋은 형태로 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 순위")

# 표에는 필요한 항목만 표시합니다.
table_data = [
    {
        "순위": movie["순위"],
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": movie["관객수"],
        "누적관객": movie["누적관객"],
        "스크린수": movie["스크린수"],
    }
    for movie in movies
]

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d",
        ),
    },
)
