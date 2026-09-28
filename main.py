import datetime
import re
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 기본 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered")

st.title("🍱 학교 급식 찾아보기")

# 1. 축약어 대체 사전 및 정규화 함수 정의
ABBR_MAP = {
    "여고": "여자고등학교",
    "여중": "여자중학교",
    "여초": "여자초등학교",
    "남고": "남자고등학교",
    "남중": "남자중학교",
    "고": "고등학교",
    "중": "중학교",
    "초": "초등학교",
}


def expand_school_name(name: str) -> str:
    """축약어가 포함된 학교 이름을 정식 명칭 형태(예: 수도여고 -> 수도여자고등학교)로 확장합니다."""
    expanded = name
    for abbr, full in ABBR_MAP.items():
        if abbr in expanded:
            expanded = expanded.replace(abbr, full)
            break
    return expanded


# 2. NEIS API 요청 함수
@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str):
    """NEIS 학교기본정보 API를 호출하여 학교 목록을 검색합니다."""
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "pIndex": 1, "pSize": 100, "SCHUL_NM": school_name}
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "schoolInfo" in data:
            return data["schoolInfo"][1]["row"]
    except Exception:
        pass
    return []


def search_school(keyword: str):
    """입력된 검색어로 학교를 검색하고, 결과가 없는 경우 축약어를 풀어 재검색합니다."""
    results = fetch_school_info(keyword)
    if not results:
        expanded_keyword = expand_school_name(keyword)
        if expanded_keyword != keyword:
            results = fetch_school_info(expanded_keyword)
    return results


@st.cache_data(ttl=3600)
def fetch_meal_info(atpt_code: str, sd_code: str, ymd_str: str):
    """NEIS 급식식단정보 API를 호출하여 해당 날짜의 중식 정보를 가져옵니다."""
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sd_code,
        "MLSV_YMD": ymd_str,
        "MMEAL_SC_CODE": "2",  # 2: 중식
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"][0]
    except Exception:
        pass
    return None


# 3. 사이드바 / 입력 폼
st.subheader("1. 학교 검색")
search_input = st.text_input("학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고, 환일중")

selected_school = None

if search_input.strip():
    schools = search_school(search_input.strip())
    if sorted_schools := schools:
        # 셀렉트박스 표시 레이블 구성 (학교명 + 교육청 지역명)
        options = {
            f"{sch['SCHUL_NM']} ({sch['LCTN_SC_NM']})": sch for sch in sorted_schools
        }
        selected_label = st.selectbox("검색된 학교 목록에서 선택하세요:", list(options.keys()))
        selected_school = options[selected_label]
    else:
        st.warning("⚠️ 입력하신 학교를 찾을 수 없습니다. 정확한 학교명을 입력해주세요.")

st.divider()

# 4. 날짜 선택 및 급식 조회
st.subheader("2. 날짜 선택 및 급식 확인")

# 서버 시계와 무관하게 한국 표준시(Asia/Seoul) 기준 오늘 날짜 가져오기
today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
selected_date = st.date_input("날짜를 선택하세요", value=today_kst)

if selected_school and selected_date:
    ymd_formatted = selected_date.strftime("%Y%m%d")

    meal_data = fetch_meal_info(
        selected_school["ATPT_OFCDC_SC_CODE"],
        selected_school["SD_SCHUL_CODE"],
        ymd_formatted,
    )

    st.markdown(f"### 🍱 **{selected_school['SCHUL_NM']}** 급식 정보")
    st.caption(f"일자: {selected_date.strftime('%Y년 %m월 %d일')}")

    if meal_data:
        # HTML 태그 및 가공 (<br/> 태그 변환)
        raw_dish = meal_data.get("DDISH_NM", "")
        clean_dish = raw_dish.replace("<br/>", "\n")

        # 칼로리 정보
        cal_info = meal_data.get("CAL_INFO", "정보 없음")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("**📋 메뉴 및 알레르기 정보**")
            st.text(clean_dish)

        with col2:
            st.markdown("**🔥 칼로리**")
            st.info(cal_info)
    else:
        st.info("ℹ️ 선택하신 날짜에 제공되는 중식 급식 정보가 없습니다.")
elif not selected_school and search_input.strip():
    st.info("👆 상단 목록에서 학교를 선택해 주세요.")
else:
    st.info("👆 학교 이름을 입력하고 선택한 후 급식을 확인하세요.")
