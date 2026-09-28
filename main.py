import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 기본 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered")

st.title("🍱 학교 급식 찾아보기")

# 2개 탭 구성
tab1, tab2 = st.tabs(["📋 오늘의 급식 메뉴", "📊 평택시 학교별 급식 칼로리 비교"])

# 축약어 대체 사전 및 정규화 함수
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


# NEIS API 요청 함수
@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str, location: str = None):
    """NEIS 학교기본정보 API를 호출하여 학교 목록을 검색합니다."""
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "pIndex": 1, "pSize": 100, "SCHUL_NM": school_name}
    if location:
        params["LCTN_SC_NM"] = location  # 예: 경기도평택시

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


@st.cache_data(ttl=3600)
def fetch_pyeongtaek_schools(school_type_keyword: str):
    """평택 소재 학교 목록 중 선택된 학교급(고/중/초)에 맞게 검색합니다."""
    # 경기도교육청(J10) 관할 평택 소재 학교 검색
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": "J10",
        "SCHUL_NM": school_type_keyword,
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            # 도로명 주소 또는 소재지명에 '평택'이 포함된 학교만 필터링
            pyeongtaek_rows = [
                r
                for r in rows
                if "평택" in r.get("ORG_RDNMA", "")
                or "평택" in r.get("LCTN_SC_NM", "")
            ]
            return pyeongtaek_rows
    except Exception:
        pass
    return []


def extract_calories(cal_str: str) -> float:
    """'654.3 Kcal' 형태의 문자열에서 숫자(float)만 추출합니다."""
    if not cal_str:
        return 0.0
    match = re.search(r"([\d\.]+)", cal_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


# ==========================================
# TAB 1: 오늘의 급식 메뉴
# ==========================================
with tab1:
    st.subheader("1. 학교 검색")
    search_input = st.text_input(
        "학교 이름을 입력하세요",
        placeholder="예: 수도여고, 서울고, 환일중",
        key="tab1_search",
    )

    selected_school = None
    if search_input.strip():
        schools = search_school(search_input.strip())
        if sorted_schools := schools:
            options = {
                f"{sch['SCHUL_NM']} ({sch['LCTN_SC_NM']})": sch
                for sch in sorted_schools
            }
            selected_label = st.selectbox(
                "검색된 학교 목록에서 선택하세요:",
                list(options.keys()),
                key="tab1_select",
            )
            selected_school = options[selected_label]
        else:
            st.warning(
                "⚠️ 입력하신 학교를 찾을 수 없습니다. 정확한 학교명을 입력해주세요."
            )

    st.divider()
    st.subheader("2. 날짜 선택")
    today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    selected_date = st.date_input(
        "날짜를 선택하세요", value=today_kst, key="tab1_date"
    )

    if selected_school and selected_date:
        ymd = selected_date.strftime("%Y%m%d")
        meal_data = fetch_meal_info(
            selected_school["ATPT_OFCDC_SC_CODE"],
            selected_school["SD_SCHUL_CODE"],
            ymd,
        )

        st.markdown(f"### 🍱 **{selected_school['SCHUL_NM']}** 급식 정보")
        st.caption(f"일자: {selected_date.strftime('%Y년 %m월 %d일')}")

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
# TAB 2: 평택시 학교별 급식 칼로리 비교
# ==========================================
with tab2:
    st.subheader("1. 조건 선택")

    c1, c2 = st.columns(2)
    with c1:
        school_kind = st.selectbox(
            "학교급 선택:",
            ["고등학교", "중학교", "초등학교"],
            key="tab2_kind",
        )
    with c2:
        today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
        selected_date_tab2 = st.date_input(
            "날짜 선택:", value=today_kst, key="tab2_date"
        )

    st.divider()

    if selected_date_tab2 and school_kind:
        ymd_tab2 = selected_date_tab2.strftime("%Y%m%d")

        # 검색 키워드 설정 (고등학교 -> 고)
        search_kw = school_kind[0] if school_kind != "초등학교" else "초"
        pyeongtaek_schools = fetch_pyeongtaek_schools(search_kw)

        if pyeongtaek_schools:
            with st.spinner("평택시 내 학교들의 급식 칼로리 정보를 불러오는 중..."):
                meal_records = []
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
                                    "칼로리 정보": m.get("CAL_INFO"),
                                }
                            )

            st.markdown(
                f"### 📊 **평택시 {school_kind} 급식 칼로리 비교**"
            )
            st.caption(
                f"조회 날짜: {selected_date_tab2.strftime('%Y년 %m월 %d일')}"
            )

            if meal_records:
                df = pd.DataFrame(meal_records)

                # 평균 칼로리 메트릭 카드
                avg_cal = round(df["칼로리(kcal)"].mean(), 1)
                max_row = df.loc[df["칼로리(kcal)"].idxmax()]
                min_row = df.loc[df["칼로리(kcal)"].idxmin()]

                m1, m2, m3 = st.columns(3)
                m1.metric("🔥 평균 칼로리", f"{avg_cal} kcal")
                m2.metric(
                    "📈 최고 칼로리",
                    f"{max_row['칼로리(kcal)']} kcal",
                    max_row["학교명"],
                )
                m3.metric(
                    "📉 최저 칼로리",
                    f"{min_row['칼로리(kcal)']} kcal",
                    min_row["학교명"],
                )

                st.divider()

                # 1. 칼로리 비교 막대 그래프
                st.markdown("**📊 학교별 칼로리 비교 그래프**")
                chart_df = df.set_index("학교명")[["칼로리(kcal)"]]
                st.bar_chart(chart_df)

                # 2. 칼로리 상세 데이터 표
                st.markdown("**📋 상세 칼로리 데이터 표**")
                st.dataframe(
                    df[["학교명", "칼로리 정보", "칼로리(kcal)"]].sort_values(
                        by="칼로리(kcal)", ascending=False
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    f"ℹ️ {selected_date_tab2.strftime('%Y년 %m월 %d일')}에 급식 칼로리 정보가 등록된 평택시 {school_kind}가 없습니다. (주말/휴일 또는 미등록)"
                )
        else:
            st.warning("평택시 학교 정보를 불러올 수 없습니다.")
