import datetime
import re
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# 페이지 설정
st.set_page_config(
    page_title="평택시 고등학교 급식 비교", page_icon="🍱", layout="wide"
)

st.title("🍱 평택시 고등학교 급식 칼로리 비교")


# 1. NEIS API: 평택시 소재 고등학교만 동적으로 가져오는 함수
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
    except Exception as e:
        st.error(f"학교 목록 로드 중 오류 발생: {e}")
    return []


# 2. NEIS API: 급식 정보 가져오는 함수
@st.cache_data(ttl=3600)
def fetch_meal_info(atpt_code: str, sd_code: str, ymd_str: str):
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


# 3. 칼로리 숫자 추출 함수
def extract_calories(cal_str: str) -> float:
    if not cal_str:
        return 0.0
    match = re.search(r"([\d\.]+)", cal_str)
    return float(match.group(1)) if match else 0.0


# ==========================================
# 메인 화면 구성
# ==========================================

# 날짜 선택
today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
selected_date = st.date_input(
    "📅 급식 칼로리를 조회할 날짜를 선택하세요:",
    value=today_kst,
)

st.divider()

if selected_date:
    ymd = selected_date.strftime("%Y%m%d")

    # 평택시 고등학교 목록 가져오기
    pyeongtaek_schools = fetch_pyeongtaek_schools()

    if pyeongtaek_schools:
        st.success(
            f"총 **{len(pyeongtaek_schools)}개**의 평택시 소재 고등학교를 찾았습니다."
        )

        meal_records = []
        with st.spinner(
            f"평택시 고등학교의 {selected_date.strftime('%Y년 %m월 %d일')} 급식 정보를 불러오는 중..."
        ):
            for sch in pyeongtaek_schools:
                m = fetch_meal_info(
                    sch["ATPT_OFCDC_SC_CODE"], sch["SD_SCHUL_CODE"], ymd
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
            # 칼로리 기준 내림차순 정렬
            df_sorted = df.sort_values(by="칼로리(kcal)", ascending=False)

            st.markdown(
                f"### 📊 **평택시 고등학교 급식 칼로리 비교** ({selected_date.strftime('%Y-%m-%d')})"
            )

            # 요약 카드
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

            # 📊 막대 그래프 출력
            st.markdown("#### 📊 학교별 칼로리 비교 (막대 그래프)")
            st.bar_chart(
                df_sorted.set_index("학교명")[["칼로리(kcal)"]], height=450
            )

            # 📋 데이터표 출력
            st.markdown("#### 📋 상세 데이터 표")
            st.dataframe(
                df_sorted[["학교명", "상세 칼로리", "칼로리(kcal)"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning(
                f"ℹ️ 선택하신 날짜({selected_date.strftime('%Y년 %m월 %d일')})에는 급식 정보가 등록된 평택시 고등학교가 없습니다."
            )
    else:
        st.error(
            "평택시 고등학교 목록을 불러올 수 없습니다. API 연결을 확인해주세요."
        )
