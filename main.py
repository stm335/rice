import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 기본 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered")

st.title("🍱 학교 급식 찾아보기")

tab1, tab2 = st.tabs(["📋 오늘의 급식 메뉴", "📊 식재료 원산지 비율"])

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
    expanded = name
    for abbr, full in ABBR_MAP.items():
        if abbr in expanded:
            expanded = expanded.replace(abbr, full)
            break
    return expanded


@st.cache_data(ttl=3600)
def fetch_school_info(school_name: str):
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
    results = fetch_school_info(keyword)
    if not results:
        expanded_keyword = expand_school_name(keyword)
        if expanded_keyword != keyword:
            results = fetch_school_info(expanded_keyword)
    return results


@st.cache_data(ttl=3600)
def fetch_meal_info(atpt_code: str, sd_code: str, ymd_str: str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sd_code,
        "MLSV_YMD": ymd_str,
        "MMEAL_SC_CODE": "2",
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"][0]
    except Exception:
        pass
    return None


def parse_origin_info(meal_data: dict):
    """
    ORGN_INFO 필드 분석 및 DDISH_NM(메뉴명) 내 원산지 표기를 함께 추려냅니다.
    """
    orgn_str = meal_data.get("ORGN_INFO", "") if meal_data else ""
    dish_str = meal_data.get("DDISH_NM", "") if meal_data else ""

    raw_items = []

    # 1. ORGN_INFO 전처리 및 분할
    if orgn_str:
        cleaned_orgn = orgn_str.replace("<br/>", "\n").replace("<br>", "\n")
        lines = [line.strip() for line in cleaned_orgn.split("\n") if line.strip()]
        raw_items.extend(lines)

    # 2. ORGN_INFO가 빈 경우 DDISH_NM(메뉴명) 내 [원산지] 또는 (원산지) 패턴 추출
    if not raw_items and dish_str:
        # 예: 쇠고기무국 [쇠고기:국내산]
        found_in_dish = re.findall(r"\[(.*?)\]|\((.*?)\)", dish_str)
        for group in found_in_dish:
            match = group[0] or group[1]
            if ":" in match or "국산" in match or "산" in match:
                raw_items.append(match)

    if not raw_items:
        return [], {"국산": 0, "수입산": 0, "기타/혼합": 0}, {}

    parsed_list = []
    counts = {"국산": 0, "수입산": 0, "기타/혼합": 0}

    for item in raw_items:
        # 다양한 구분 기호 대응 (:, -, ( ))
        if ":" in item:
            parts = item.split(":", 1)
            ingredient, origin = parts[0].strip(), parts[1].strip()
        elif "-" in item:
            parts = item.split("-", 1)
            ingredient, origin = parts[0].strip(), parts[1].strip()
        else:
            ingredient = "식재료"
            origin = item.strip()

        # 국산/수입산 판별 로직
        if any(kw in origin for kw in ["국내산", "국산", "한우"]):
            category = "국산"
        elif any(
            kw in origin
            for kw in [
                "수입산",
                "호주",
                "미국",
                "중국",
                "브라질",
                "칠레",
                "스페인",
                "베트남",
                "원양산",
                "러시아",
            ]
        ):
            category = "수입산"
        else:
            category = "기타/혼합"

        counts[category] += 1
        parsed_list.append({"식재료": ingredient, "원산지": origin, "구분": category})

    total = sum(counts.values())
    ratios = {
        k: round((v / total) * 100, 1) if total > 0 else 0 for k, v in counts.items()
    }

    return parsed_list, counts, ratios


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
            st.warning("⚠️ 입력하신 학교를 찾을 수 없습니다.")

    st.divider()
    st.subheader("2. 날짜 선택")
    today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    selected_date = st.date_input(
        "날짜를 선택하세요", value=today_kst, key=f"{key_prefix}_date"
    )

    return selected_school, selected_date


# TAB 1: 오늘의 급식 메뉴
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


# TAB 2: 식재료 원산지 비율 분석
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
            parsed_items, counts, ratios = parse_origin_info(meal_data)

            if parsed_items:
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

                st.markdown("**📋 전체 식재료 원산지 상세 표**")
                df = pd.DataFrame(parsed_items)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info(
                    "ℹ️ 해당 날짜의 식단 정보는 있으나 원산지 상세 필드가 등록되어 있지 않습니다."
                )
        else:
            st.info("ℹ️ 선택하신 날짜에 제공되는 중식 급식 정보가 없습니다.")
