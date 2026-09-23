"""CSV를 읽어서 분석할 수 있는 상태로 정리(전처리)하는 모듈.

이 파일이 담당하는 일은 4가지입니다.
1) CSV 읽기 (한글 인코딩 문제 대응)
2) 필수 컬럼이 다 있는지 검증
3) 타입 변환 (날짜는 날짜로, 숫자는 숫자로)
4) 결측치/이상치 정리 후 "무엇을 손봤는지" 사용자에게 알려줄 정보 반환

실무에서 가장 많은 시간이 걸리는 부분이 바로 이 전처리입니다.
그래서 화면 코드와 섞지 않고 별도 파일로 분리했습니다.
"""

import pandas as pd

from src import config


class DataValidationError(Exception):
    """업로드한 데이터로는 분석을 진행할 수 없을 때 발생시키는 예외.

    예외를 따로 만든 이유: app.py에서 이 예외만 잡아서
    "사용자에게 보여줄 안내 메시지"로 바꿔 처리할 수 있습니다.
    """

    pass


def read_csv(source) -> pd.DataFrame:
    """CSV 파일을 읽어 DataFrame으로 반환합니다.

    Parameters
    ----------
    source : str | Path | file-like
        파일 경로 또는 Streamlit 업로더가 준 파일 객체

    Returns
    -------
    pd.DataFrame

    Notes
    -----
    한국에서 만든 CSV는 인코딩이 두 가지로 나뉩니다.
    - utf-8-sig : 구글 스프레드시트, 대부분의 툴에서 내보낸 파일
    - cp949     : 윈도우 엑셀에서 "CSV(쉼표로 분리)"로 저장한 파일
    그래서 utf-8 계열을 먼저 시도하고, 실패하면 cp949로 다시 시도합니다.
    이 처리가 없으면 한글 컬럼/값이 있는 파일에서 UnicodeDecodeError가 납니다.
    """
    last_error = None

    for encoding in ("utf-8-sig", "cp949"):
        try:
            # 파일 객체는 한 번 읽으면 커서가 끝으로 가므로 처음으로 되돌립니다.
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, encoding=encoding)
            # 컬럼 이름에 공백이 섞여 있으면 뒤에서 전부 실패하므로 미리 정리합니다.
            df.columns = [str(col).strip() for col in df.columns]
            return df
        except UnicodeDecodeError as error:
            last_error = error
        except pd.errors.EmptyDataError:
            raise DataValidationError("CSV 파일이 비어 있습니다.")

    raise DataValidationError(
        "CSV 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949로 저장한 뒤 다시 시도해주세요. "
        "(원인: {})".format(last_error)
    )


def validate_columns(df: pd.DataFrame) -> list:
    """필수 컬럼 중 빠진 것들의 목록을 반환합니다.

    반환값이 빈 리스트([])면 검증 통과입니다.
    예외를 던지지 않고 "목록"을 돌려주는 이유는
    화면에서 "어떤 컬럼이 없는지" 전부 보여주기 위해서입니다.
    """
    return [col for col in config.REQUIRED_COLUMNS if col not in df.columns]


def check_funnel_consistency(df: pd.DataFrame) -> int:
    """퍼널 순서가 어긋난 행의 개수를 셉니다.

    정상이라면 노출 >= 도달 >= 조회수 >= 클릭 >= 문의 >= 전환 이어야 합니다.
    어긋난 행이 있어도 계산을 막지 않고 개수만 알려줍니다.
    (실무 데이터는 채널마다 집계 기준이 달라 이런 경우가 종종 있습니다.
     여기서 분석을 중단시키면 대시보드를 아예 못 쓰게 됩니다.)
    """
    # 먼저 "위반 없음(False)"으로 시작해서, 단계별로 위반을 누적(or)합니다.
    violated = pd.Series(False, index=df.index)

    for upper, lower in zip(config.FUNNEL_ORDER, config.FUNNEL_ORDER[1:]):
        if upper in df.columns and lower in df.columns:
            violated = violated | (df[upper] < df[lower])

    return int(violated.sum())


def clean_data(df: pd.DataFrame) -> tuple:
    """타입 변환과 결측/이상치 정리를 수행합니다.

    Returns
    -------
    (pd.DataFrame, dict)
        정리된 데이터프레임과, 무엇을 얼마나 손봤는지 담은 info 딕셔너리
    """
    # 원본을 직접 수정하지 않도록 복사합니다.
    # (원본을 바꾸면 Streamlit 캐시와 맞물려 예측하기 어려운 버그가 생깁니다)
    df = df.copy()

    info = {
        "rows_before": len(df),
        "invalid_date_rows": 0,
        "missing_numeric_cells": 0,
        # 원래 값이 있었는데 숫자로 바꾸지 못한 칸 수 (빈칸과 구분해서 셉니다)
        "invalid_numeric_cells": 0,
        "negative_value_cells": 0,
        "has_cost": "cost" in df.columns,
        "has_revenue": "revenue" in df.columns,
    }

    # ------------------------------------------------------------------
    # 1) 날짜 변환
    # ------------------------------------------------------------------
    # errors="coerce" 는 "변환 실패한 값을 에러 대신 NaT(빈 날짜)로 만들어라"는 뜻입니다.
    # 이렇게 하면 이상한 값 하나 때문에 전체가 멈추지 않습니다.
    df[config.DATE_COLUMN] = pd.to_datetime(df[config.DATE_COLUMN], errors="coerce")

    info["invalid_date_rows"] = int(df[config.DATE_COLUMN].isna().sum())
    # 날짜가 없는 행은 기간 분석이 불가능하므로 제외합니다.
    df = df[df[config.DATE_COLUMN].notna()].copy()

    # 시간 정보를 지워 날짜 단위로 통일합니다. (00:00:00 으로 맞춤)
    df[config.DATE_COLUMN] = df[config.DATE_COLUMN].dt.normalize()

    # ------------------------------------------------------------------
    # 2) 숫자 변환 + 결측/음수 처리
    # ------------------------------------------------------------------
    for column in config.ALL_NUMERIC_COLUMNS:
        if column not in df.columns:
            # 선택 컬럼(cost, revenue)이 아예 없으면 '알 수 없음'을 뜻하는 NaN으로 채웁니다.
            # 뒤쪽 계산 코드가 "컬럼이 있나 없나"를 매번 확인하지 않아도 되게 컬럼 자체는 만듭니다.
            #
            # [중요] 여기서 0이 아니라 NaN을 쓰는 이유
            # '매출이 0원이다'와 '매출 데이터를 아예 받지 못했다'는 의미가 전혀 다릅니다.
            # 0으로 채우면 revenue 컬럼이 없는 CSV에서도 ROAS = 0 / 광고비 = 0.00배 로
            # 계산되어, 마치 "광고비를 썼는데 매출이 0원"인 것처럼 보입니다.
            # NaN으로 두면 계산 자체가 불가능(None)으로 처리되어 화면에 '-'로 표시됩니다.
            df[column] = float("nan")
            continue

        raw_series = df[column]

        # (1) 변환 '전에' 원래 비어 있던 칸을 먼저 표시해 둡니다.
        #     빈칸(진짜 결측)과 숫자로 못 바꾼 값(파싱 실패)은 원인이 다르므로
        #     나중에 구분해서 보고해야 합니다.
        as_text = raw_series.astype(str).str.strip()
        originally_blank = raw_series.isna() | (as_text == "")

        # (2) 천 단위 쉼표를 제거한 뒤 숫자로 바꿉니다.
        #     엑셀에서 CSV로 내보내면 숫자가 "1,234" 형태로 저장되는 일이 흔합니다.
        #     쉼표를 그대로 두면 pd.to_numeric이 NaN을 돌려주고, 그 NaN을 0으로
        #     채우면 모든 지표가 0이 되어 KPI 전체가 조용히 무의미해집니다.
        #     그래서 쉼표만 먼저 지우고 변환합니다. ("12,345.67" -> 12345.67)
        converted = pd.to_numeric(as_text.str.replace(",", "", regex=False), errors="coerce")

        # (3) 원래 값이 있었는데 숫자로 바꾸지 못한 칸 = 파싱 실패입니다.
        #     '빈칸이라서 0'과 '읽을 수 없는 값이라서 0'을 같은 것으로 처리하면
        #     사용자가 데이터가 잘못 읽혔다는 사실을 알 수 없습니다.
        parse_failed = converted.isna() & (~originally_blank)

        # [중요] 0으로 채우는 것이 일반적인 정답은 아닙니다.
        # 이 프로젝트는 '성과 데이터의 빈칸 = 그날 집계되지 않음(=0건)'이라고
        # 가정했기 때문에 0으로 채웁니다. 광고비가 비어 있으면 그날 집행하지 않은
        # 것으로 보는 식입니다.
        #
        # 실제 운영 데이터에서는 이 가정이 위험할 수 있습니다.
        # 빈칸이 '집행 안 함(0)'인지 'API 수집 실패(알 수 없음)'인지에 따라
        # 평균·합계·비율이 전부 달라지기 때문입니다. 수집 실패를 0으로 채우면
        # 성과를 과소평가하게 됩니다.
        # 따라서 실무에서는 결측 원인을 먼저 확인하고, 업무 정의에 따라
        # 0 채우기 / 해당 행 제외 / 별도 결측 표시를 구분해서 처리해야 합니다.
        # 그래서 여기서는 빈칸 수와 파싱 실패 수를 각각 info에 기록해
        # 화면에 알려줍니다.
        info["missing_numeric_cells"] += int(originally_blank.sum())
        info["invalid_numeric_cells"] += int(parse_failed.sum())
        converted = converted.fillna(0)

        # 성과 지표에 음수는 있을 수 없으므로 0으로 올립니다.
        negative_count = int((converted < 0).sum())
        info["negative_value_cells"] += negative_count
        if negative_count:
            converted = converted.clip(lower=0)

        df[column] = converted

    # 퍼널 지표는 '개수'이므로 정수로 맞춥니다. (화면에 12.0 대신 12로 보이게)
    for column in config.REQUIRED_NUMERIC_COLUMNS:
        df[column] = df[column].round().astype("int64")

    # ------------------------------------------------------------------
    # 3) 문자 컬럼 정리
    # ------------------------------------------------------------------
    for column in config.TEXT_COLUMNS:
        if column not in df.columns:
            df[column] = config.UNKNOWN_LABEL
            continue
        # 빈 값은 '미분류'로 채우고, 앞뒤 공백을 제거합니다.
        # 공백을 지우지 않으면 "instagram"과 "instagram "이 다른 채널로 집계됩니다.
        df[column] = df[column].fillna(config.UNKNOWN_LABEL).astype(str).str.strip()
        df[column] = df[column].replace("", config.UNKNOWN_LABEL)

    # ------------------------------------------------------------------
    # 4) 화면 표시용 한국어 라벨 컬럼 추가
    # ------------------------------------------------------------------
    df["channel_label"] = df["channel"].map(config.get_channel_label)
    df["content_type_label"] = df["content_type"].map(config.get_content_type_label)

    # ------------------------------------------------------------------
    # 5) 정렬 및 마무리
    # ------------------------------------------------------------------
    df = df.sort_values(config.DATE_COLUMN).reset_index(drop=True)

    info["rows_after"] = len(df)
    info["funnel_violation_rows"] = check_funnel_consistency(df)

    return df, info


def load_and_prepare(source=None) -> tuple:
    """CSV 읽기 -> 검증 -> 정리를 한 번에 수행하는 함수.

    Parameters
    ----------
    source : str | Path | file-like | None
        None이면 저장소에 포함된 샘플 데이터를 사용합니다.
        (업로드 없이도 대시보드를 바로 체험할 수 있게 하는 장치)

    Returns
    -------
    (pd.DataFrame, dict)

    Raises
    ------
    DataValidationError
        필수 컬럼이 없거나 CSV를 읽을 수 없는 경우
    """
    is_sample = source is None
    if is_sample:
        source = config.SAMPLE_DATA_PATH

    df = read_csv(source)

    missing = validate_columns(df)
    if missing:
        raise DataValidationError(
            "필수 컬럼이 없습니다: {}\n필요한 컬럼 전체: {}".format(
                ", ".join(missing), ", ".join(config.REQUIRED_COLUMNS)
            )
        )

    df, info = clean_data(df)

    if df.empty:
        raise DataValidationError("분석할 수 있는 행이 없습니다. 날짜 형식을 확인해주세요.")

    info["is_sample"] = is_sample
    return df, info


def filter_data(df: pd.DataFrame, start_date, end_date, channels=None, content_types=None):
    """기간/채널/콘텐츠 유형으로 데이터를 걸러냅니다.

    Parameters
    ----------
    start_date, end_date : date | datetime | str
        분석 기간 (양쪽 끝 포함)
    channels : list | None
        선택한 채널 코드 목록.
        None  = 필터를 걸지 않음(전체 채널)
        []    = 선택한 채널이 없음 -> 결과 0건
    content_types : list | None
        선택한 콘텐츠 유형 목록. channels와 같은 규칙입니다.

    Returns
    -------
    pd.DataFrame

    Notes
    -----
    None과 빈 리스트([])를 반드시 구분합니다.

    빈 리스트를 '전체'로 처리하면, 사용자가 화면에서 채널을 전부 지웠을 때
    필터가 사라져 전체 채널 합계가 표시됩니다. 사이드바에는 아무것도 선택되지
    않았는데 화면에는 전체 숫자가 나오므로, 사용자가 잘못된 KPI를 읽게 됩니다.
    "아무것도 선택하지 않음"은 "전체 선택"이 아니라 "결과 0건"이 맞습니다.

    그래서 `if channels:` (빈 리스트를 falsy로 보는 검사) 대신
    `if channels is not None:` 을 씁니다. 빈 리스트가 넘어오면
    isin([]) 이 모든 행을 False로 만들어 결과가 비게 됩니다.
    """
    # 비교를 위해 Timestamp로 통일합니다. (문자열/date/datetime 무엇이 와도 동작)
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()

    mask = (df[config.DATE_COLUMN] >= start) & (df[config.DATE_COLUMN] <= end)

    if channels is not None:
        mask = mask & df["channel"].isin(channels)

    if content_types is not None:
        mask = mask & df["content_type"].isin(content_types)

    return df[mask].copy()
