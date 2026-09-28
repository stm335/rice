import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 설정
st.set_page_config(
    page_title="학교 급식 찾아보기", page_icon="🍱", layout="wide"
)

st.title("🍱 학교 급식 찾아보기")

# 2개 탭 구성
tab1, tab2 = st.tabs(["📋 개별 학교 급식 조회", "📊 평택시 고등학교 전체 칼로리 비교"])

# 축약어 대체 사전
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
    """축약어가 포함된 학교 이름을 정식 명칭 형태로 확장합니다."""
    expanded = name
    for abbr, full in ABBR_MAP.items():
        if abbr in expanded:
            expanded = expanded.replace(abbr, full)
            break
    return expanded


# 1. 개별 학교 검색 API
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


# 2. 평택시 소재 고등학교 동적 조회 API
@st.cache_data(ttl=86400)
def fetch_pyeongtaek_high_schools():
    """경기도교육청(J10) 중 위치(LCTN_SC_NM)가 '경기도 평택시'인 고등학교만 조회합니다."""
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": "J10",  # 경기도교육청
        "LCTN_SC_NM": "경기도 평택시",  # 소재지: 경기도 평택시
        "SCHUL_KND_SC_NM": "고등학교",  # 학교급: 고등학교
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "schoolInfo" in data:
            return data["schoolInfo"][1]["row"]
    except Exception:
        pass
    return []


# 3. 급식 정보 API
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


def extract_calories(cal_str: str) -> float:
    """'654.3 Kcal' 형태의 문자열에서 숫자(float)만 추출합니다."""
    if not cal_str:
        return 0.0
    match = re.search(r"([\d\.]+)", cal_str)
    return float(match.group(1)) if match else 0.0


# ==========================================
# TAB 1: 개별 학교 급식 조회
# ==========================================
with tab1:
    st.subheader("1. 학교 검색")
    search_input = st.text_input(
        "학교 이름을 입력하세요",
        placeholder="예: 수도여고, 서울고, 환일중, 평택고",
        key="tab1_search",
    )

    selected_school = None
    if search_input.strip():
        schools = search_school(search_input.strip())
        if sorted_schools := schools:
            options = {
                f"{sch['SCHUL_NM']} ({sch.get('LCTN_SC_NM', '')})": sch
                for sch in sorted_schools
            }
            selected_label = st.selectbox(
                "검색된 학교 목록에서 선택하세요:",
                list(options.keys()),
                key="tab1_select",
            )
            selected_school = options[selected_label]
        else:
            st.warning("⚠️ 입력하신 학교를 찾을 수 없습니다.")

    st.divider()
    st.subheader("2. 날짜 선택")
    today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    selected_date_tab1 = st.date_input(
        "날짜를 선택하세요", value=today_kst, key="tab1_date"
    )

    if selected_school and selected_date_tab1:
        ymd = selected_date_tab1.strftime("%Y%m%d")
        meal_data = fetch_meal_info(
            selected_school["ATPT_OFCDC_SC_CODE"],
            selected_school["SD_SCHUL_CODE"],
            ymd,
        )

        st.markdown(f"### 🍱 **{selected_school['SCHUL_NM']}** 급식 정보")
        st.caption(f"일자: {selected_date_tab1.strftime('%Y년 %m월 %d일')}")

        if meal_data:
            raw_dish = meal_data.get("DDISH_NM", "")
            clean_dish = raw_dish.replace("<br/>", "\n").replace("<br>", "\n")
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


# ==========================================
# TAB 2: 평택시 고등학교 전체 칼로리 비교
# ==========================================
with tab2:
    st.subheader("📅 날짜 선택 및 평택시 고등학교 칼로리 비교")

    today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    selected_date_tab2 = st.date_input(
        "조회할 날짜를 선택하세요:", value=today_kst, key="tab2_date"
    )

    st.divider()

    if selected_date_tab2:
        ymd_tab2 = selected_date_tab2.strftime("%Y%m%d")

        # 평택시 고등학교 목록 가져오기
        pyeongtaek_schools = fetch_pyeongtaek_high_schools()

        if pyeongtaek_schools:
            st.success(
                f"총 **{len(pyeongtaek_schools)}개**의 평택시 소재 고등학교를 확인했습니다."
            )

            meal_records = []
            with st.spinner(
                f"평택시 고등학교의 {selected_date_tab2.strftime('%Y년 %m월 %d일')} 급식 정보를 불러오는 중..."
            ):
                for sch in pyeongtaek_schools:
                    m = fetch_meal_info(
                        sch["ATPT_OFCDC_SC_CODE"],
                        sch["SD_SCHUL_CODE"],
                        ymd_tab2,
                    )
                    if m and m.get("CAL_INFO"):
                        cal_val = extract_calories(m.get("CAL_INFO"))
                        if cal_val > 0:
                            meal_records.append(
                                {
                                    "학교명": sch["SCHUL_NM"],
                                    "칼로리(kcal)": cal_val,
                                    "상세 칼로리": m.get("CAL_INFO"),
                                }
                            )

            if meal_records:
                df = pd.DataFrame(meal_records)
                df_sorted = df.sort_values(by="칼로리(kcal)", ascending=False)

                st.markdown(
                    f"### 📊 **평택시 고등학교 급식 칼로리 비교** ({selected_date_tab2.strftime('%Y-%m-%d')})"
                )

                avg_cal = round(df_sorted["칼로리(kcal)"].mean(), 1)
                max_row = df_sorted.iloc[0]
                min_row = df_sorted.iloc[-1]

                col1, col2, col3 = st.columns(3)
                col1.metric("🔥 평택시 평균 칼로리", f"{avg_cal} kcal")
                col2.metric(
                    "📈 최고 칼로리",
                    f"{max_row['칼로리(kcal)']} kcal",
                    max_row["학교명"],
                )
                col3.metric(
                    "📉 최저 칼로리",
                    f"{min_row['칼로리(kcal)']} kcal",
                    min_row["학교명"],
                )

                st.divider()

                st.markdown("#### 📊 학교별 칼로리 비교 (막대 그래프)")
                st.bar_chart(
                    df_sorted.set_index("학교명")[["칼로리(kcal)"]], height=450
                )

                st.markdown("#### 📋 상세 데이터 표")
                st.dataframe(
                    df_sorted[["학교명", "상세 칼로리", "칼로리(kcal)"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning(
                    f"ℹ️ 선택하신 날짜({selected_date_tab2.strftime('%Y년 %m월 %d일')})에는 급식 정보가 등록된 평택시 고등학교가 없습니다."
                )
        else:
            st.error(
                "평택시 고등학교 목록을 불러올 수 없습니다. API 연결을 확인해주세요."
            )
