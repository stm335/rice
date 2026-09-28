import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 기본 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered")

st.title("🍱 학교 급식 찾아보기")

# 탭 구성 (1. 오늘의 급식 메뉴 / 2. 급식 원산지 비율 분석)
tab1, tab2 = st.tabs(["📋 오늘의 급식 메뉴", "📊 식재료 원산지 비율"])

# 1. 축약어 대체 사전 및 정규화 함수
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


# 2. NEIS API 요청 함수들
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


def parse_origin_info(orgn_str: str):
    """NEIS ORGN_INFO 텍스트를 파싱하여 국산/수입산 항목 및 비율을 추출합니다."""
    if not orgn_str:
        return [], {"국산": 0, "수입산": 0, "기타/혼합": 0}, {}

    items = orgn_str.split("<br/>")
    parsed_list = []

    counts = {"국산": 0, "수입산": 0, "기타/혼합": 0}

    for item in items:
        item_clean = item.strip()
        if not item_clean:
            continue

        # 예: "쇠고기 : 국내산" 또는 "두부 : 콩(호주산)"
        parts = item_clean.split(":")
        ingredient = parts[0].strip()
        origin = parts[1].strip() if len(parts) > 1 else "미표기"

        # 국산/수입산 판별
        if "국내산" in origin or "국산" in origin or "한우" in origin:
            category = "국산"
        elif any(
            country in origin
            for country in [
                "수입산",
                "호주",
                "미국",
                "중국",
                "브라질",
                "칠레",
                "스페인",
                "베트남",
                "원양산",
            ]
        ):
            category = "수입산"
        else:
            category = "기타/혼합"

        counts[category] += 1
        parsed_list.append(
            {"식재료": ingredient, "원산지": origin, "구분": category}
        )

    total = sum(counts.values())
    ratios = {
        k: round((v / total) * 100, 1) if total > 0 else 0 for k, v in counts.items()
    }

    return parsed_list, counts, ratios


# 공통 학교 및 날짜 선택 폼 UI 함수
def render_search_form(key_prefix: str):
    st.subheader("1. 학교 검색")
    search_input = st.text_input(
        "학교 이름을 입력하세요",
        placeholder="예: 수도여고, 서울고, 환일중",
        key=f"{key_prefix}_search",
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
                key=f"{key_prefix}_select",
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
        "날짜를 선택하세요", value=today_kst, key=f"{key_prefix}_date"
    )

    return selected_school, selected_date


# ==========================================
# TAB 1: 오늘의 급식 메뉴
# ==========================================
with tab1:
    school, date_val = render_search_form("tab1")

    if school and date_val:
        ymd = date_val.strftime("%Y%m%d")
        meal_data = fetch_meal_info(
            school["ATPT_OFCDC_SC_CODE"], school["SD_SCHUL_CODE"], ymd
        )

        st.markdown(f"### 🍱 **{school['SCHUL_NM']}** 급식 정보")
        st.caption(f"일자: {date_val.strftime('%Y년 %m월 %d일')}")

        if meal_data:
            raw_dish = meal_data.get("DDISH_NM", "")
            clean_dish = raw_dish.replace("<br/>", "\n")
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


# ==========================================
# TAB 2: 식재료 원산지 비율 분석
# ==========================================
with tab2:
    school, date_val = render_search_form("tab2")

    if school and date_val:
        ymd = date_val.strftime("%Y%m%d")
        meal_data = fetch_meal_info(
            school["ATPT_OFCDC_SC_CODE"], school["SD_SCHUL_CODE"], ymd
        )

        st.markdown(f"### 🌾 **{school['SCHUL_NM']}** 원산지 비율 분석")
        st.caption(f"일자: {date_val.strftime('%Y년 %m월 %d일')}")

        if meal_data:
            orgn_info_str = meal_data.get("ORGN_INFO", "")
            parsed_items, counts, ratios = parse_origin_info(orgn_info_str)

            if parsed_items:
                # 1. 비율 요약 메트릭 표시
                m1, m2, m3 = st.columns(3)
                m1.metric("🇰🇷 국산 비율", f"{ratios['국산']}%", f"{counts['국산']}개 품목")
                m2.metric(
                    "🌐 수입산 비율",
                    f"{ratios['수입산']}%",
                    f"{counts['수입산']}개 품목",
                )
                m3.metric(
                    "🔄 기타/혼합 비율",
                    f"{ratios['기타/혼합']}%",
                    f"{counts['기타/혼합']}개 품목",
                )

                st.divider()

                # 2. 원산지 상세 목록 표
                st.markdown("**📋 전체 식재료 원산지 상세 표**")
                df = pd.DataFrame(parsed_items)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ 해당 날짜에 등록된 식재료 원산지 상세 정보가 없습니다.")
        else:
            st.info("ℹ️ 선택하신 날짜에 제공되는 중식 급식 정보가 없습니다.")
