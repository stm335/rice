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
# 공통 설정
# =========================================================

NEIS_BASE_URL = "https://open.neis.go.kr/hub"


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
            expanded = expanded.replace(abbr, full)
            break

    return expanded


# =========================================================
# 1. 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str):

    url = f"{NEIS_BASE_URL}/schoolInfo"

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
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        # NEIS 오류 응답
        if "RESULT" in data:

            result = data["RESULT"]

            print(
                "NEIS 오류:",
                result.get("CODE"),
                result.get("MESSAGE")
            )

            return []

        if "schoolInfo" not in data:
            return []

        if len(data["schoolInfo"]) < 2:
            return []

        return data["schoolInfo"][1].get(
            "row",
            []
        )

    except Exception as e:

        print(
            f"학교 검색 오류: {e}"
        )

        return []


def search_school(keyword: str):

    results = fetch_school_info(keyword)

    # 검색 결과가 없으면 축약어를 풀어서 다시 검색
    if not results:

        expanded = expand_school_name(keyword)

        if expanded != keyword:

            results = fetch_school_info(
                expanded
            )

    return results


# =========================================================
# 2. 경기도 고등학교 목록 가져오기
# =========================================================

@st.cache_data(ttl=86400)
def fetch_gyeonggi_high_schools():

    url = f"{NEIS_BASE_URL}/schoolInfo"

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,

        # 경기도교육청
        "ATPT_OFCDC_SC_CODE": "J10",

        # 고등학교
        "SCHUL_KND_SC_NM": "고등학교",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        # API 오류 확인
        if "RESULT" in data:

            result = data["RESULT"]

            st.error(
                f"NEIS API 오류: "
                f"{result.get('CODE', '')} / "
                f"{result.get('MESSAGE', '')}"
            )

            return []

        if "schoolInfo" not in data:

            st.error(
                "NEIS API에서 학교 정보를 "
                "받지 못했습니다."
            )

            return []

        if len(data["schoolInfo"]) < 2:

            st.error(
                "NEIS API 응답 구조가 "
                "예상과 다릅니다."
            )

            return []

        rows = data["schoolInfo"][1].get(
            "row",
            []
        )

        return rows

    except requests.exceptions.Timeout:

        st.error(
            "NEIS API 응답 시간이 초과되었습니다."
        )

        return []

    except requests.exceptions.RequestException as e:

        st.error(
            f"NEIS API 연결 오류: {e}"
        )

        return []

    except Exception as e:

        st.error(
            f"학교 목록 처리 오류: {e}"
        )

        return []


# =========================================================
# 3. 평택시 고등학교 필터링
# =========================================================

def get_pyeongtaek_high_schools():

    schools = fetch_gyeonggi_high_schools()

    if not schools:
        return []

    pyeongtaek_schools = []

    for school in schools:

        location = str(
            school.get(
                "LCTN_SC_NM",
                ""
            )
        )

        address = str(
            school.get(
                "ORG_RDNMA",
                ""
            )
        )

        # 소재지 또는 주소에 "평택"이 포함되어 있으면 선택
        if (
            "평택" in location
            or "평택" in address
        ):

            pyeongtaek_schools.append(
                school
            )

    return pyeongtaek_schools


# =========================================================
# 4. 급식 정보
# =========================================================

@st.cache_data(ttl=3600)
def fetch_meal_info(
    atpt_code: str,
    sd_code: str,
    ymd_str: str
):

    url = f"{NEIS_BASE_URL}/mealServiceDietInfo"

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sd_code,
        "MLSV_YMD": ymd_str,

        # 2 = 중식
        "MMEAL_SC_CODE": "2",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        # API 오류
        if "RESULT" in data:
            return None

        if "mealServiceDietInfo" not in data:
            return None

        if len(data["mealServiceDietInfo"]) < 2:
            return None

        rows = data[
            "mealServiceDietInfo"
        ][1].get(
            "row",
            []
        )

        if not rows:
            return None

        return rows[0]

    except Exception as e:

        print(
            f"급식 API 오류: {e}"
        )

        return None


# =========================================================
# 5. 칼로리 추출
# =========================================================

def extract_calories(cal_str):

    if not cal_str:
        return 0.0

    # 숫자 + 소수점 찾기
    match = re.search(
        r"([\d.]+)",
        str(cal_str)
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
# 6. 날짜
# =========================================================

today_kst = datetime.datetime.now(
    ZoneInfo("Asia/Seoul")
).date()


# =========================================================
# TAB 1
# =========================================================

with tab1:

    st.subheader("🔎 1. 학교 검색")

    search_input = st.text_input(
        "학교 이름을 입력하세요",
        placeholder=(
            "예: 평택고, 수도여고, "
            "서울고, 환일중"
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
                    "학교명 없음"
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
                "검색된 학교 목록에서 선택하세요",
                list(options.keys()),
                key="tab1_select"
            )

            selected_school = options[
                selected_label
            ]

        else:

            st.warning(
                "⚠️ 입력하신 학교를 찾을 수 없습니다."
            )

    st.divider()

    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    st.subheader("📅 2. 날짜 선택")

    selected_date_tab1 = st.date_input(
        "날짜를 선택하세요",
        value=today_kst,
        key="tab1_date"
    )

    # -----------------------------------------------------
    # 급식 조회
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

        school_name = selected_school.get(
            "SCHUL_NM",
            "학교"
        )

        st.markdown(
            f"### 🍱 **{school_name}** 급식 정보"
        )

        st.caption(
            "일자: "
            + selected_date_tab1.strftime(
                "%Y년 %m월 %d일"
            )
        )

        if meal_data:

            raw_dish = meal_data.get(
                "DDISH_NM",
                ""
            )

            # <br/> → 줄바꿈
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
                    "**📋 메뉴 및 알레르기 정보**"
                )

                st.text(
                    clean_dish
                )

            with col2:

                st.markdown(
                    "**🔥 칼로리**"
                )

                st.info(
                    cal_info
                )

        else:

            st.info(
                "ℹ️ 선택하신 날짜에 "
                "중식 급식 정보가 없습니다."
            )

    else:

        if search_input.strip():

            st.info(
                "👆 검색 결과에서 학교를 "
                "선택해 주세요."
            )

        else:

            st.info(
                "👆 학교 이름을 입력하고 "
                "학교를 선택해 주세요."
            )


# =========================================================
# TAB 2
# =========================================================

with tab2:

    st.subheader(
        "📊 평택시 고등학교 전체 칼로리 비교"
    )

    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    selected_date_tab2 = st.date_input(
        "조회할 날짜를 선택하세요",
        value=today_kst,
        key="tab2_date"
    )

    st.divider()

    # -----------------------------------------------------
    # 학교 목록 가져오기
    # -----------------------------------------------------

    with st.spinner(
        "평택시 고등학교 목록을 불러오는 중..."
    ):

        pyeongtaek_schools = (
            get_pyeongtaek_high_schools()
        )

    # 디버깅 정보
    st.caption(
        f"평택시 고등학교 검색 결과: "
        f"{len(pyeongtaek_schools)}개"
    )

    # -----------------------------------------------------
    # 학교가 정상적으로 조회된 경우
    # -----------------------------------------------------

    if pyeongtaek_schools:

        st.success(
            f"총 **{len(pyeongtaek_schools)}개**의 "
            f"평택시 고등학교를 확인했습니다."
        )

        ymd_tab2 = selected_date_tab2.strftime(
            "%Y%m%d"
        )

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
                f"→ {school_name}"
            )

            meal = fetch_meal_info(
                school[
                    "ATPT_OFCDC_SC_CODE"
                ],
                school[
                    "SD_SCHUL_CODE"
                ],
                ymd_tab2
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

        # -------------------------------------------------
        # 결과
        # -------------------------------------------------

        if meal_records:

            df = pd.DataFrame(
                meal_records
            )

            # 칼로리 높은 순
            df = df.sort_values(
                "칼로리(kcal)",
                ascending=False
            ).reset_index(
                drop=True
            )

            st.markdown(
                f"### 📊 평택시 고등학교 "
                f"급식 칼로리 비교"
            )

            st.caption(
                selected_date_tab2.strftime(
                    "%Y년 %m월 %d일"
                )
            )

            # -------------------------------------------------
            # 평균 / 최고 / 최저
            # -------------------------------------------------

            average_calorie = round(
                df["칼로리(kcal)"].mean(),
                1
            )

            max_row = df.iloc[0]

            min_row = df.iloc[-1]

            col1, col2, col3 = st.columns(
                3
            )

            with col1:

                st.metric(
                    "🔥 평균 칼로리",
                    f"{average_calorie} kcal"
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

            # -------------------------------------------------
            # 그래프
            # -------------------------------------------------

            st.markdown(
                "#### 📊 학교별 칼로리 비교"
            )

            chart_df = df[
                ["학교명", "칼로리(kcal)"]
            ].set_index(
                "학교명"
            )

            st.bar_chart(
                chart_df,
                height=600
            )

            st.divider()

            # -------------------------------------------------
            # 표
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

            csv = df[
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
                data=csv,
                file_name=(
                    "평택시_고등학교_급식칼로리_"
                    f"{ymd_tab2}.csv"
                ),
                mime="text/csv"
            )

        else:

            st.warning(
                "ℹ️ 선택한 날짜에 급식 정보가 "
                "등록된 평택시 고등학교가 없습니다."
            )

    # -----------------------------------------------------
    # 학교 목록을 못 가져온 경우
    # -----------------------------------------------------

    else:

        st.error(
            "❌ 평택시 고등학교 목록을 "
            "불러오지 못했습니다."
        )

        st.info(
            "아래 디버깅 정보를 확인해 주세요."
        )

        # -------------------------------------------------
        # 직접 API 테스트
        # -------------------------------------------------

        with st.expander(
            "🔧 NEIS API 연결 테스트"
        ):

            test_url = (
                f"{NEIS_BASE_URL}/schoolInfo"
            )

            test_params = {
                "Type": "json",
                "pIndex": 1,
                "pSize": 10,
                "ATPT_OFCDC_SC_CODE": "J10",
                "SCHUL_KND_SC_NM": "고등학교",
            }

            st.write(
                "**요청 주소**"
            )

            st.code(
                test_url
            )

            try:

                test_response = requests.get(
                    test_url,
                    params=test_params,
                    timeout=15
                )

                st.write(
                    "**HTTP 상태 코드:**",
                    test_response.status_code
                )

                st.write(
                    "**실제 요청 URL:**"
                )

                st.code(
                    test_response.url
                )

                test_data = (
                    test_response.json()
                )

                st.write(
                    "**API 응답:**"
                )

                st.json(
                    test_data
                )

            except Exception as e:

                st.error(
                    f"API 테스트 실패: {e}"
                )
