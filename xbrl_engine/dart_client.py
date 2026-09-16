import io
import re
import zipfile
import xml.etree.ElementTree as ET
import requests
from .config import API_KEY, REPORT_CODE_MAP, REPORT_NAME_MAP

_CORP_CACHE = None

def load_listed_companies():
    global _CORP_CACHE
    if _CORP_CACHE is not None:
        return _CORP_CACHE
    if not API_KEY:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    res = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": API_KEY}, verify=False, timeout=30)
    if res.status_code != 200 or not res.content.startswith(b"PK"):
        raise RuntimeError("DART corpCode API 응답 오류")
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    companies = []
    for c in root.findall("list"):
        stock_code = (c.findtext("stock_code") or "").strip()
        if not stock_code:
            continue
        companies.append({"name": c.findtext("corp_name") or "", "code": stock_code, "corp_code": c.findtext("corp_code") or ""})
    _CORP_CACHE = companies
    return companies

def extract_report_period(name):
    m = re.search(r"\((\d{4})[.\-/](\d{1,2})\)", name or "")
    return (m.group(1), m.group(2).zfill(2)) if m else ("", "")


def infer_report_code(name):
    """DART 보고서명과 결산월을 이용해 보고서 종류를 정확히 판별합니다."""
    text = name or ""
    _, month = extract_report_period(text)

    if "사업보고서" in text:
        return "11011"
    if "반기보고서" in text:
        return "11012"
    if "1분기" in text:
        return "11013"
    if "3분기" in text:
        return "11014"

    # DART에는 단순히 '분기보고서'로 표시되는 경우가 있어 결산월로 보완합니다.
    if "분기보고서" in text:
        if month in {"01", "02", "03", "04"}:
            return "11013"
        if month in {"07", "08", "09", "10"}:
            return "11014"

    return ""


def search_reports(corp_code, year, report_types, fiscal_month="", final_report=None):
    """선택한 연도와 보고서 종류만 반환합니다.

    final_report는 이전 버전 app.py가 다섯 번째 인자로 넘기는 경우를 위한
    하위 호환 인자입니다. 현재는 DART API의 last_reprt_at="Y"를 사용하므로
    값과 관계없이 최종 보고서만 조회합니다.
    """
    codes = {REPORT_CODE_MAP[t] for t in (report_types or []) if t in REPORT_CODE_MAP}
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        # 사업연도 보고서는 다음 해에 공시될 수 있으므로 조회 범위는 다음 해 말까지 둡니다.
        "bgn_de": f"{year}0101",
        "end_de": f"{year + 1}1231",
        "last_reprt_at": "Y",
        "pblntf_ty": "A",
        "page_count": 100,
    }
    result = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params=params, verify=False, timeout=15
    ).json()

    reports = []
    for r in result.get("list", []):
        name = r.get("report_nm", "")
        rc = infer_report_code(name)
        if not rc or (codes and rc not in codes):
            continue

        period_year, period_month = extract_report_period(name)
        if period_year and period_year != str(year):
            continue
        if fiscal_month and period_month and period_month != fiscal_month:
            continue

        reports.append({
            "company": r.get("corp_name", ""),
            "type": name,
            "rcept_no": r.get("rcept_no", ""),
            "reprt_code": rc,
            "reprt_name": REPORT_NAME_MAP.get(rc, ""),
            "rcept_dt": r.get("rcept_dt", ""),
            "report_date": r.get("rcept_dt", ""),
            "corp_code": corp_code,
        })

    # 같은 종류/사업연도의 중복 공시는 최신 접수일자 우선으로 정렬합니다.
    reports.sort(key=lambda x: (x.get("report_date", ""), x.get("rcept_no", "")), reverse=True)
    return reports
