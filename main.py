import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 학교 급식 찾아보기")


# =========================================================
# 탭
# =========================================================

tab1, tab2 = st.tabs([
    "📋 개별 학교 급식 조회",
    "📊 평택시 고등학교 전체 칼로리 비교"
])


# =========================================================
# NEIS 기본 주소
# =========================================================

NEIS_URL = "https://open.neis.go.kr/hub"


# =========================================================
# 축약어
# =========================================================

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
    """학교 이름의 축약어를 정식 명칭으로 변경"""

    expanded = name

    for abbr, full in ABBR_MAP.items():
        if abbr in expanded:
            expanded = expanded.replace(
                abbr,
                full
            )
            break

    return expanded


# =========================================================
# 1. 학교 검색 API
# =========================================================

@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str):
    """
    학교 이름으로 NEIS 학교기본정보 검색
    """

    url = f"{NEIS_URL}/schoolInfo"

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": school_name,
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        # NEIS 오류
        if "RESULT" in data:
            return []

        if "schoolInfo" not in data:
            return []

        if len(data["schoolInfo"]) < 2:
            return []

        return data["schoolInfo"][1].get(
            "row",
            []
        )

    except Exception:
        return []


def search_school(keyword: str):
    """
    학교 검색.
    결과가 없으면 축약어를 풀어서 다시 검색.
    """

    results = fetch_school_info(
        keyword
    )

    if not results:

        expanded = expand_school_name(
            keyword
        )

        if expanded != keyword:

            results = fetch_school_info(
                expanded
            )

    return results


# =========================================================
# 2. 급식 정보 API
# =========================================================

@st.cache_data(ttl=3600)
def fetch_meal_info(
    atpt_code: str,
    school_code: str,
    ymd: str
):
    """
    특정 학교의 특정 날짜 중식 조회
    """

    url = (
        f"{NEIS_URL}/mealServiceDietInfo"
    )

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_YMD": ymd,

        # 2 = 중식
        "MMEAL_SC_CODE": "2",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            return None

        if len(
            data["mealServiceDietInfo"]
        ) < 2:
            return None

        rows = data[
            "mealServiceDietInfo"
        ][1].get(
            "row",
            []
        )

        if rows:
            return rows[0]

    except Exception:
        return None

    return None


# =========================================================
# 3. 칼로리 추출
# =========================================================

def extract_calories(value):
    """
    '654.3 Kcal' → 654.3
    """

    if not value:
        return 0.0

    match = re.search(
        r"([\d.]+)",
        str(value)
    )

    if not match:
        return 0.0

    try:
        return float(
            match.group(1)
        )
    except ValueError:
        return 0.0


# =========================================================
# 현재 한국 날짜
# =========================================================

today_kst = datetime.datetime.now(
    ZoneInfo("Asia/Seoul")
).date()


# =========================================================
# TAB 1
# 개별 학교 급식 조회
# =========================================================

with tab1:

    st.subheader(
        "🔎 학교 검색"
    )

    search_input = st.text_input(
        "학교 이름을 입력하세요",
        placeholder=(
            "예: 평택고, 평택여고, "
            "한광고, 신한고"
        ),
        key="tab1_search"
    )

    selected_school = None

    # -----------------------------------------------------
    # 학교 검색
    # -----------------------------------------------------

    if search_input.strip():

        schools = search_school(
            search_input.strip()
        )

        if schools:

            options = {}

            for school in schools:

                school_name = school.get(
                    "SCHUL_NM",
                    ""
                )

                location = school.get(
                    "LCTN_SC_NM",
                    ""
                )

                label = (
                    f"{school_name} "
                    f"({location})"
                )

                options[label] = school

            selected_label = st.selectbox(
                "검색된 학교에서 선택하세요",
                list(options.keys()),
                key="tab1_select"
            )

            selected_school = options[
                selected_label
            ]

        else:

            st.warning(
                "⚠️ 학교를 찾을 수 없습니다."
            )

    st.divider()

    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    st.subheader(
        "📅 날짜 선택"
    )

    selected_date_tab1 = st.date_input(
        "급식 날짜",
        value=today_kst,
        key="tab1_date"
    )

    # -----------------------------------------------------
    # 급식 표시
    # -----------------------------------------------------

    if selected_school:

        ymd = selected_date_tab1.strftime(
            "%Y%m%d"
        )

        with st.spinner(
            "급식 정보를 불러오는 중..."
        ):

            meal_data = fetch_meal_info(
                selected_school[
                    "ATPT_OFCDC_SC_CODE"
                ],
                selected_school[
                    "SD_SCHUL_CODE"
                ],
                ymd
            )

        st.markdown(
            f"### 🍱 "
            f"**{selected_school['SCHUL_NM']}** "
            f"급식 정보"
        )

        st.caption(
            selected_date_tab1.strftime(
                "%Y년 %m월 %d일"
            )
        )

        if meal_data:

            raw_dish = meal_data.get(
                "DDISH_NM",
                ""
            )

            clean_dish = re.sub(
                r"<br\s*/?>",
                "\n",
                raw_dish,
                flags=re.IGNORECASE
            )

            cal_info = meal_data.get(
                "CAL_INFO",
                "정보 없음"
            )

            col1, col2 = st.columns(
                [2, 1]
            )

            with col1:

                st.markdown(
                    "#### 📋 메뉴 및 알레르기"
                )

                st.text(
                    clean_dish
                )

            with col2:

                st.markdown(
                    "#### 🔥 칼로리"
                )

                st.info(
                    cal_info
                )

        else:

            st.info(
                "ℹ️ 선택한 날짜에는 "
                "중식 급식 정보가 없습니다."
            )

    else:

        if search_input.strip():

            st.info(
                "👆 검색 결과에서 학교를 "
                "선택해주세요."
            )

        else:

            st.info(
                "👆 학교 이름을 입력해주세요."
            )


# =========================================================
# TAB 2
# 평택시 고등학교만 비교
# =========================================================

with tab2:

    st.subheader(
        "📊 평택시 고등학교 급식 칼로리 비교"
    )

    st.caption(
        "평택시 소재 고등학교만 비교합니다."
    )

    # -----------------------------------------------------
    # 날짜 선택
    # -----------------------------------------------------

    selected_date_tab2 = st.date_input(
        "조회 날짜",
        value=today_kst,
        key="tab2_date"
    )

    st.divider()

    # =====================================================
    # 평택시 고등학교 목록
    # =====================================================
    #
    # 2026년 평택시 고등학교 목록 기준
    #
    # =====================================================

    PYEONGTAEK_HIGH_SCHOOLS = [
        "평택고등학교",
        "신한고등학교",
        "한광고등학교",
        "한광여자고등학교",
        "동일공업고등학교",
        "송탄고등학교",
        "한국관광고등학교",
        "평택여자고등학교",
        "안중고등학교",
        "진위고등학교",
        "태광고등학교",
        "효명고등학교",
        "은혜고등학교",
        "현화고등학교",
        "이충고등학교",
        "경기물류고등학교",
        "청담고등학교",
        "비전고등학교",
        "청북고등학교",
        "라온고등학교",
        "평택마이스터고등학교",
        "용죽고등학교",
    ]

    # =====================================================
    # 학교 코드 가져오기
    # =====================================================

    with st.spinner(
        "평택시 고등학교 정보를 준비하는 중..."
    ):

        pyeongtaek_schools = []

        for school_name in PYEONGTAEK_HIGH_SCHOOLS:

            results = fetch_school_info(
                school_name
            )

            matched_school = None

            # 정확히 같은 이름 우선
            for school in results:

                if school.get(
                    "SCHUL_NM"
                ) == school_name:

                    # 경기도 학교인지 확인
                    if school.get(
                        "ATPT_OFCDC_SC_CODE"
                    ) == "J10":

                        matched_school = school
                        break

            if matched_school:

                pyeongtaek_schools.append(
                    matched_school
                )

    # =====================================================
    # 학교 목록 결과
    # =====================================================

    st.write(
        f"🏫 대상 학교: "
        f"**{len(pyeongtaek_schools)}개**"
    )

    if not pyeongtaek_schools:

        st.error(
            "평택시 고등학교 정보를 가져오지 못했습니다."
        )

        st.info(
            "NEIS API 연결 또는 학교명 정보를 확인해주세요."
        )

    else:

        # -------------------------------------------------
        # 조회 날짜
        # -------------------------------------------------

        ymd = selected_date_tab2.strftime(
            "%Y%m%d"
        )

        # -------------------------------------------------
        # 결과 저장
        # -------------------------------------------------

        meal_records = []

        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        progress = st.progress(0)

        status = st.empty()

        total = len(
            pyeongtaek_schools
        )

        # -------------------------------------------------
        # 학교별 급식 조회
        # -------------------------------------------------

        for index, school in enumerate(
            pyeongtaek_schools
        ):

            school_name = school.get(
                "SCHUL_NM",
                "학교명 없음"
            )

            status.write(
                f"🍱 {index + 1}/{total} "
                f"{school_name} 조회 중..."
            )

            meal = fetch_meal_info(
                school[
                    "ATPT_OFCDC_SC_CODE"
                ],
                school[
                    "SD_SCHUL_CODE"
                ],
                ymd
            )

            if meal:

                cal_info = meal.get(
                    "CAL_INFO",
                    ""
                )

                calories = extract_calories(
                    cal_info
                )

                if calories > 0:

                    meal_records.append(
                        {
                            "학교명": school_name,
                            "상세 칼로리": cal_info,
                            "칼로리(kcal)": calories
                        }
                    )

            progress.progress(
                (index + 1) / total
            )

        status.empty()
        progress.empty()

        # =================================================
        # 결과
        # =================================================

        if meal_records:

            df = pd.DataFrame(
                meal_records
            )

            # 칼로리 내림차순
            df = df.sort_values(
                by="칼로리(kcal)",
                ascending=False
            ).reset_index(
                drop=True
            )

            # -------------------------------------------------
            # 제목
            # -------------------------------------------------

            st.markdown(
                f"### 📊 "
                f"{selected_date_tab2.strftime('%Y년 %m월 %d일')} "
                f"평택시 고등학교 급식 칼로리"
            )

            # -------------------------------------------------
            # 평균
            # -------------------------------------------------

            average_calorie = round(
                df["칼로리(kcal)"].mean(),
                1
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "🔥 평균 칼로리",
                    f"{average_calorie} kcal"
                )

            with col2:

                st.metric(
                    "🍱 급식 정보 확인 학교",
                    f"{len(df)}개"
                )

            st.divider()

            # -------------------------------------------------
            # 그래프
            # -------------------------------------------------

            st.markdown(
                "#### 📊 학교별 칼로리 비교"
            )

            chart_df = df[
                [
                    "학교명",
                    "칼로리(kcal)"
                ]
            ].set_index(
                "학교명"
            )

            st.bar_chart(
                chart_df,
                height=600
            )

            st.divider()

            # -------------------------------------------------
            # 상세 표
            # -------------------------------------------------

            st.markdown(
                "#### 📋 상세 데이터"
            )

            st.dataframe(
                df[
                    [
                        "학교명",
                        "상세 칼로리",
                        "칼로리(kcal)"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

            # -------------------------------------------------
            # CSV 다운로드
            # -------------------------------------------------

            csv_data = df[
                [
                    "학교명",
                    "상세 칼로리",
                    "칼로리(kcal)"
                ]
            ].to_csv(
                index=False
            ).encode(
                "utf-8-sig"
            )

            st.download_button(
                label="📥 CSV 다운로드",
                data=csv_data,
                file_name=(
                    f"평택시_고등학교_급식칼로리_"
                    f"{ymd}.csv"
                ),
                mime="text/csv"
            )

        else:

            st.warning(
                f"ℹ️ "
                f"{selected_date_tab2.strftime('%Y년 %m월 %d일')}에는 "
                f"급식 정보가 등록된 학교가 없습니다."
            )
