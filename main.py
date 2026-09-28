import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo


# ==========================================
# 페이지 설정
# ==========================================

st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 학교 급식 찾아보기")


# ==========================================
# 탭 구성
# ==========================================

tab1, tab2 = st.tabs([
    "📋 개별 학교 급식 조회",
    "📊 평택시 고등학교 전체 칼로리 비교"
])


# ==========================================
# 축약어 대체 사전
# ==========================================

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


# ==========================================
# 1. 개별 학교 검색 API
# ==========================================

@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str):
    """NEIS 학교기본정보 API를 호출하여 학교 목록을 검색합니다."""

    url = "https://open.neis.go.kr/hub/schoolInfo"

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": school_name,
    }

    try:
        res = requests.get(
            url,
            params=params,
            timeout=10
        )

        res.raise_for_status()

        data = res.json()

        if "schoolInfo" in data and len(data["schoolInfo"]) > 1:
            return data["schoolInfo"][1].get("row", [])

    except requests.exceptions.RequestException as e:
        print(f"학교 검색 API 오류: {e}")

    except Exception as e:
        print(f"학교 검색 처리 오류: {e}")

    return []


def search_school(keyword: str):
    """
    입력된 검색어로 학교를 검색하고,
    결과가 없으면 축약어를 풀어서 다시 검색합니다.
    """

    results = fetch_school_info(keyword)

    if not results:
        expanded_keyword = expand_school_name(keyword)

        if expanded_keyword != keyword:
            results = fetch_school_info(expanded_keyword)

    return results


# ==========================================
# 2. 평택시 고등학교 목록 조회
# ==========================================

@st.cache_data(ttl=86400)
def fetch_pyeongtaek_high_schools():
    """
    경기도 평택시에 소재한 고등학교 목록을 가져옵니다.
    """

    url = "https://open.neis.go.kr/hub/schoolInfo"

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,

        # 경기도교육청
        "ATPT_OFCDC_SC_CODE": "J10",

        # 평택시
        "LCTN_SC_NM": "경기도 평택시",

        # 고등학교
        "SCHUL_KND_SC_NM": "고등학교",
    }

    try:
        res = requests.get(
            url,
            params=params,
            timeout=10
        )

        res.raise_for_status()

        data = res.json()

        if "schoolInfo" in data and len(data["schoolInfo"]) > 1:

            rows = data["schoolInfo"][1].get("row", [])

            return rows

    except requests.exceptions.RequestException as e:
        st.error(f"학교 목록 API 연결 오류: {e}")

    except Exception as e:
        st.error(f"학교 목록 처리 오류: {e}")

    return []


# ==========================================
# 3. 급식 정보 API
# ==========================================

@st.cache_data(ttl=3600)
def fetch_meal_info(
    atpt_code: str,
    sd_code: str,
    ymd_str: str
):
    """
    특정 학교의 특정 날짜 중식 정보를 가져옵니다.
    """

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sd_code,
        "MLSV_YMD": ymd_str,

        # 2 = 중식
        "MMEAL_SC_CODE": "2",
    }

    try:

        res = requests.get(
            url,
            params=params,
            timeout=10
        )

        res.raise_for_status()

        data = res.json()

        if "mealServiceDietInfo" in data:

            rows = data["mealServiceDietInfo"][1].get(
                "row",
                []
            )

            if rows:
                return rows[0]

    except requests.exceptions.RequestException as e:
        print(f"급식 API 오류: {e}")

    except Exception as e:
        print(f"급식 데이터 처리 오류: {e}")

    return None


# ==========================================
# 4. 칼로리 추출
# ==========================================

def extract_calories(cal_str: str) -> float:
    """
    '654.3 Kcal' 같은 문자열에서 숫자만 추출합니다.
    """

    if not cal_str:
        return 0.0

    match = re.search(
        r"([\d.]+)",
        str(cal_str)
    )

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    return 0.0


# ==========================================
# TAB 1
# 개별 학교 급식 조회
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

        schools = search_school(
            search_input.strip()
        )

        if schools:

            # 학교 이름 + 소재지 표시
            options = {
                f"{sch['SCHUL_NM']} "
                f"({sch.get('LCTN_SC_NM', '')})": sch
                for sch in schools
            }

            selected_label = st.selectbox(
                "검색된 학교 목록에서 선택하세요:",
                list(options.keys()),
                key="tab1_select",
            )

            selected_school = options[selected_label]

        else:

            st.warning(
                "⚠️ 입력하신 학교를 찾을 수 없습니다."
            )

    st.divider()

    st.subheader("2. 날짜 선택")

    today_kst = datetime.datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()

    selected_date_tab1 = st.date_input(
        "날짜를 선택하세요",
        value=today_kst,
        key="tab1_date"
    )

    # ======================================
    # 급식 조회
    # ======================================

    if selected_school and selected_date_tab1:

        ymd = selected_date_tab1.strftime(
            "%Y%m%d"
        )

        meal_data = fetch_meal_info(
            selected_school["ATPT_OFCDC_SC_CODE"],
            selected_school["SD_SCHUL_CODE"],
            ymd
        )

        st.markdown(
            f"### 🍱 **{selected_school['SCHUL_NM']}** 급식 정보"
        )

        st.caption(
            f"일자: "
            f"{selected_date_tab1.strftime('%Y년 %m월 %d일')}"
        )

        if meal_data:

            raw_dish = meal_data.get(
                "DDISH_NM",
                ""
            )

            # HTML 줄바꿈 제거
            clean_dish = (
                raw_dish
                .replace("<br/>", "\n")
                .replace("<br>", "\n")
            )

            cal_info = meal_data.get(
                "CAL_INFO",
                "정보 없음"
            )

            col1, col2 = st.columns([2, 1])

            with col1:

                st.markdown(
                    "**📋 메뉴 및 알레르기 정보**"
                )

                st.text(clean_dish)

            with col2:

                st.markdown(
                    "**🔥 칼로리**"
                )

                st.info(cal_info)

        else:

            st.info(
                "ℹ️ 선택하신 날짜에 제공되는 "
                "중식 급식 정보가 없습니다."
            )

    elif not selected_school and search_input.strip():

        st.info(
            "👆 상단 목록에서 학교를 선택해 주세요."
        )

    else:

        st.info(
            "👆 학교 이름을 입력하고 "
            "선택한 후 급식을 확인하세요."
        )


# ==========================================
# TAB 2
# 평택시 고등학교 전체 칼로리 비교
# ==========================================

with tab2:

    st.subheader(
        "📅 날짜 선택 및 평택시 고등학교 칼로리 비교"
    )

    today_kst = datetime.datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()

    selected_date_tab2 = st.date_input(
        "조회할 날짜를 선택하세요:",
        value=today_kst,
        key="tab2_date"
    )

    st.divider()

    # ======================================
    # 날짜가 선택된 경우
    # ======================================

    if selected_date_tab2:

        ymd_tab2 = selected_date_tab2.strftime(
            "%Y%m%d"
        )

        # ==================================
        # 평택시 고등학교 목록 가져오기
        # ==================================

        with st.spinner(
            "평택시 고등학교 목록을 불러오는 중..."
        ):

            pyeongtaek_schools = (
                fetch_pyeongtaek_high_schools()
            )

        # ==================================
        # 학교 목록 확인
        # ==================================

        if pyeongtaek_schools:

            st.success(
                f"총 **{len(pyeongtaek_schools)}개**의 "
                f"평택시 소재 고등학교를 확인했습니다."
            )

            # ==================================
            # 급식 데이터 조회
            # ==================================

            meal_records = []

            progress_bar = st.progress(0)

            status_text = st.empty()

            total_schools = len(
                pyeongtaek_schools
            )

            for index, sch in enumerate(
                pyeongtaek_schools
            ):

                school_name = sch.get(
                    "SCHUL_NM",
                    "학교명 없음"
                )

                status_text.text(
                    f"급식 조회 중... "
                    f"{index + 1}/{total_schools} "
                    f"→ {school_name}"
                )

                m = fetch_meal_info(
                    sch["ATPT_OFCDC_SC_CODE"],
                    sch["SD_SCHUL_CODE"],
                    ymd_tab2
                )

                if m:

                    cal_info = m.get(
                        "CAL_INFO",
                        ""
                    )

                    cal_val = extract_calories(
                        cal_info
                    )

                    if cal_val > 0:

                        meal_records.append(
                            {
                                "학교명": school_name,
                                "칼로리(kcal)": cal_val,
                                "상세 칼로리": cal_info,
                            }
                        )

                progress_bar.progress(
                    (index + 1) / total_schools
                )

            status_text.empty()
            progress_bar.empty()

            # ==================================
            # 결과가 있는 경우
            # ==================================

            if meal_records:

                df = pd.DataFrame(
                    meal_records
                )

                # 칼로리 높은 순
                df_sorted = df.sort_values(
                    by="칼로리(kcal)",
                    ascending=False
                ).reset_index(drop=True)

                st.markdown(
                    f"### 📊 **평택시 고등학교 "
                    f"급식 칼로리 비교** "
                    f"({selected_date_tab2.strftime('%Y-%m-%d')})"
                )

                # ==================================
                # 통계
                # ==================================

                avg_cal = round(
                    df_sorted["칼로리(kcal)"].mean(),
                    1
                )

                max_row = df_sorted.iloc[0]

                min_row = df_sorted.iloc[-1]

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.metric(
                        "🔥 평택시 평균 칼로리",
                        f"{avg_cal} kcal"
                    )

                with col2:

                    st.metric(
                        "📈 최고 칼로리",
                        f"{max_row['칼로리(kcal)']} kcal",
                        max_row["학교명"]
                    )

                with col3:

                    st.metric(
                        "📉 최저 칼로리",
                        f"{min_row['칼로리(kcal)']} kcal",
                        min_row["학교명"]
                    )

                st.divider()

                # ==================================
                # 막대 그래프
                # ==================================

                st.markdown(
                    "#### 📊 학교별 칼로리 비교"
                )

                chart_df = (
                    df_sorted
                    .set_index("학교명")
                    [["칼로리(kcal)"]]
                )

                st.bar_chart(
                    chart_df,
                    height=500
                )

                # ==================================
                # 상세 데이터
                # ==================================

                st.markdown(
                    "#### 📋 상세 데이터 표"
                )

                display_df = df_sorted[
                    [
                        "학교명",
                        "상세 칼로리",
                        "칼로리(kcal)"
                    ]
                ]

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )

                # ==================================
                # CSV 다운로드
                # ==================================

                csv_data = display_df.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    label="📥 CSV 파일 다운로드",
                    data=csv_data,
                    file_name=(
                        f"평택시_고등학교_급식칼로리_"
                        f"{ymd_tab2}.csv"
                    ),
                    mime="text/csv"
                )

            # ==================================
            # 급식 데이터가 없는 경우
            # ==================================

            else:

                st.warning(
                    f"ℹ️ 선택하신 날짜 "
                    f"({selected_date_tab2.strftime('%Y년 %m월 %d일')})에는 "
                    f"급식 정보가 등록된 "
                    f"평택시 고등학교가 없습니다."
                )

        # ==================================
        # 학교 목록 API 실패
        # ==================================

        else:

            st.error(
                "❌ 평택시 고등학교 목록을 "
                "불러오지 못했습니다."
            )

            st.info(
                "NEIS API 연결 상태 또는 "
                "검색 조건을 확인해주세요."
            )
