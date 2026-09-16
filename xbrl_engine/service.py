import io
import zipfile
import requests

from .config import API_KEY, REPORT_NAME_MAP
from .utils import pick_xbrl_instance_from_zip, make_json_safe
from .taxonomy import parse_label_linkbases, parse_xsd_metadata, parse_pre, parse_def
from .instance import parse_instance
from .relations import build_bundles, group_bundles
from .builders import build_role_documents, build_menu

_REPORT_CACHE = {}
ENGINE_VERSION = "0722-taxonomy-prefix-match-v7"

def load_xbrl_report(rcept_no: str, reprt_code: str) -> dict:
    key = (ENGINE_VERSION, rcept_no, reprt_code)
    if key in _REPORT_CACHE:
        return _REPORT_CACHE[key]
    if not API_KEY:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    res = requests.get(
        "https://opendart.fss.or.kr/api/fnlttXbrl.xml",
        params={"crtfc_key": API_KEY, "rcept_no": rcept_no, "reprt_code": reprt_code},
        verify=False, timeout=40,
    )
    if res.status_code != 200:
        raise RuntimeError(f"DART XBRL API HTTP 오류: {res.status_code}")
    if not res.content.startswith(b"PK"):
        preview = res.content[:2000].decode("utf-8", errors="ignore")
        raise RuntimeError(f"DART 응답이 ZIP 파일이 아닙니다.\n{preview}")
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        instance_name, instance_data = pick_xbrl_instance_from_zip(z)
        if not instance_name:
            raise RuntimeError(
                "ZIP 안에서 XBRL instance 파일을 찾지 못했습니다. "
                f"ZIP 파일 목록: {z.namelist()[:80]}"
            )
        role_types, xsd = parse_xsd_metadata(z)
        labels = parse_label_linkbases(z, xsd)
        pre_roles = parse_pre(z, xsd)
        def_roles = parse_def(z, xsd)
    contexts, units, facts = parse_instance(instance_data, labels, xsd)
    bundles = build_bundles(role_types, pre_roles, def_roles)
    grouped = group_bundles(bundles)
    role_documents = build_role_documents(grouped, facts, labels, xsd)
    payload = {
        "engine_version": ENGINE_VERSION,
        "instance_file": instance_name,
        "summary": {
            "rcept_no": rcept_no, "reprt_code": reprt_code,
            "reprt_name": REPORT_NAME_MAP.get(reprt_code, reprt_code),
            "contexts_count": len(contexts), "facts_count": len(facts),
            "labels_count": len(labels), "xsd_concepts_count": len(xsd),
            "role_types_count": len(role_types), "pre_roles_count": len(pre_roles),
            "def_roles_count": len(def_roles), "role_documents_count": len(role_documents),
        },
        "menus": build_menu(role_documents),
        "role_documents": role_documents,
    }
    result = make_json_safe(payload)
    if len(_REPORT_CACHE) >= 2:
        _REPORT_CACHE.pop(next(iter(_REPORT_CACHE)))
    _REPORT_CACHE[key] = result
    return result
