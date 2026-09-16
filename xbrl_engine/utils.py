import io
import zipfile
import re
from .config import *

def local_name(tag):
    if not tag:
        return ""
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def clean_qname(value):
    if not value:
        return ""
    value = str(value).strip()
    if ":" in value:
        value = value.split(":", 1)[1]
    if "_" in value and value.count("_") == 1:
        left, right = value.split("_", 1)
        if left in {"ifrs-full", "dart", "entity", "fss", "krx", "kifrs", "kospi"} or "-" in left:
            value = right
    return value


def locator_full_id(value):
    """Return a taxonomy-prefixed locator fragment without discarding it."""
    raw = str(value or "").strip().split("#")[-1].replace(":", "_", 1)
    if "_" not in raw:
        return ""
    prefix, _ = raw.split("_", 1)
    if prefix in {"ifrs-full", "dart", "entity", "fss", "krx", "kifrs", "kospi"} or "-" in prefix:
        return raw
    return ""


def concept_from_href(href):
    if not href:
        return ""
    return clean_qname(href.split("#")[-1].strip())



def taxonomy_prefix(target_namespace="", schema_name=""):
    """XSD namespace/file name으로 KOX식 Full ID prefix를 결정합니다."""
    text = f"{target_namespace} {schema_name}".lower()
    if "entity" in text:
        return "entity"
    if "kifrs" in text:
        return "kifrs"
    # DART taxonomy namespaces commonly contain the path segment `/ifrs/`.
    # Check the more specific taxonomy before the generic IFRS match.
    if "dart" in text:
        return "dart"
    if "ifrs" in text:
        return "ifrs-full"
    base = (schema_name or "").replace("\\", "/").rsplit("/", 1)[-1].split(".", 1)[0]
    base = re.sub(r"[^A-Za-z0-9_-]+", "", base)
    return base or "extension"


def resolve_concept_ref(value, xsd=None, namespace=""):
    """href fragment, XSD id, QName, instance local-name을 하나의 canonical concept name으로 통일합니다."""
    raw = str(value or "").strip().split("#")[-1]
    if not raw:
        return ""
    local = raw.split(":", 1)[-1]
    candidates = [raw, local, clean_qname(raw)]
    if "_" in local:
        candidates.append(local.split("_", 1)[1])
    xsd = xsd or {}
    # Instance facts only carry a local name after QName parsing.  Use the
    # element namespace first so identically named IFRS/DART/entity concepts
    # do not resolve to whichever schema happened to be parsed last.
    if namespace:
        for concept, meta in xsd.items():
            if meta.get("targetNamespace") != namespace:
                continue
            aliases = set(meta.get("aliases") or [])
            aliases.update({concept, meta.get("name", ""), meta.get("id", ""), meta.get("full_id", "")})
            if raw in aliases or local in aliases or clean_qname(raw) in aliases:
                return concept
        # Imported standard taxonomies are not always bundled in DART's ZIP.
        # The namespace still gives us the same Full ID used by PRE/label locators.
        namespaced_id = f"{taxonomy_prefix(namespace)}_{clean_qname(local)}"
        if namespaced_id:
            return namespaced_id
    for candidate in candidates:
        if candidate in xsd:
            return candidate
    for concept, meta in xsd.items():
        aliases = set(meta.get("aliases") or [])
        aliases.update({meta.get("id", ""), meta.get("full_id", ""), meta.get("name", "")})
        if raw in aliases or local in aliases or clean_qname(raw) in aliases:
            return concept
    return locator_full_id(raw) or clean_qname(raw)

def role_uri_last(role_uri):
    return role_uri.rstrip("/").split("/")[-1] if role_uri else ""


def extract_role_code(definition, fallback=""):
    m = re.search(r"\[([A-Z]\d+[a-zA-Z]?)\]", definition or "")
    if m:
        return m.group(1)
    m = re.search(r"([A-Z]\d+[a-zA-Z]?)", fallback or "")
    return m.group(1) if m else (fallback or "")


def role_base_suffix(role_code):
    m = re.match(r"^([A-Z]\d+)([a-zA-Z])?$", role_code or "")
    return (m.group(1), m.group(2) or "") if m else (role_code or "", "")


def clean_role_definition(definition, role_code=""):
    title = definition or ""
    if "|" in title:
        title = title.split("|", 1)[0]
    title = re.sub(r"\s+", " ", title).strip()
    return title or (f"[{role_code}]" if role_code else "ROLE")


def title_no_code(title):
    return re.sub(r"^\s*\[[^\]]+\]\s*", "", title or "").strip()


def role_scope(role_base):
    m = re.search(r"(\d)$", role_base or "")
    return "연결" if m and m.group(1) == "0" else "별도"


BODY_KEYWORDS = ["재무상태표", "포괄손익계산서", "자본변동표", "현금흐름표"]


def is_body_title(title):
    compact = re.sub(r"\s+", "", title or "")
    return any(re.sub(r"\s+", "", k) in compact for k in BODY_KEYWORDS)


def role_group(role_base, title):
    return f"{role_scope(role_base)}재무제표 {'본문' if is_body_title(title) else '주석'}"


def role_sort_key(role_base, title):
    label = title_no_code(title)
    role_num = 999999
    m = re.search(r"(\d+)", role_base or "")
    if m:
        role_num = int(m.group(1))
    no = 999999
    m2 = re.match(r"^\s*(\d+)(?:[.\-\s]|$)", label)
    if m2:
        no = int(m2.group(1))
    body_order = {"재무상태표": 1, "포괄손익계산서": 2, "자본변동표": 3, "현금흐름표": 4}
    body_idx = 99
    compact = re.sub(r"\s+", "", label)
    for k, v in body_order.items():
        if re.sub(r"\s+", "", k) in compact:
            body_idx = v
            break
    return (body_idx, no, role_num, label)


def concept_kind_by_name(concept):
    c = concept or ""
    if c.endswith("Axis"):
        return "axis"
    if c.endswith("Domain"):
        return "domain"
    if c.endswith("Member"):
        return "member"
    if c.endswith("Table") or c.endswith("Hypercube"):
        return "table"
    if c.endswith("LineItems"):
        return "lineitems"
    if c.endswith("Abstract"):
        return "abstract"
    if c.endswith("TextBlock") or "Explanatory" in c:
        return "text"
    return "item"


def concept_kind(concept, xsd=None):
    if xsd and concept in xsd:
        return xsd[concept].get("kind") or concept_kind_by_name(concept)
    return concept_kind_by_name(concept)


def label_role_key(role):
    if not role:
        return ""
    return str(role).rstrip("/").rsplit("/", 1)[-1]


def _label_data_for_concept(concept, labels, xsd=None):
    """
    concept, XSD id, full_id, alias 중 어느 키로 들어와도 동일한 label map을 찾습니다.
    """
    labels = labels or {}

    if concept in labels:
        return labels.get(concept)

    xsd = xsd or {}

    # concept가 canonical key인 경우 그 meta의 aliases를 검사합니다.
    meta = xsd.get(concept, {})
    candidates = [
        concept,
        meta.get("name", ""),
        meta.get("id", ""),
        meta.get("full_id", ""),
        clean_qname(meta.get("id", "")),
        clean_qname(meta.get("full_id", "")),
    ]
    candidates.extend(meta.get("aliases") or [])

    # concept 자체가 alias인 경우 canonical meta를 역탐색합니다.
    for canonical, item in xsd.items():
        aliases = set(item.get("aliases") or [])
        aliases.update({
            canonical,
            item.get("name", ""),
            item.get("id", ""),
            item.get("full_id", ""),
            clean_qname(item.get("id", "")),
            clean_qname(item.get("full_id", "")),
        })
        if concept in aliases:
            candidates.extend(list(aliases))
            candidates.append(canonical)
            break

    for candidate in candidates:
        if candidate and candidate in labels:
            return labels[candidate]

    return None



def normalized_label_role_key(role):
    """PRE preferredLabel과 lab-ko/lab-en resource role을 같은 key로 맞춥니다.

    DEF/PRE/label linkbase의 to concept는 taxonomy alias를 통해 동일 canonical
    concept로 해석하고, preferredLabel URI의 마지막 role 이름을 사용해 해당
    label/text()를 선택합니다.
    """
    key = label_role_key(role)
    compact = re.sub(r"[^a-z0-9]", "", key.lower())

    if not compact or compact == "label" or compact.endswith("standardlabel"):
        return "label"
    if "periodstart" in compact or compact in {"startlabel", "beginninglabel", "openinglabel"}:
        return "periodStartLabel"
    if "periodend" in compact or compact in {"endlabel", "endinglabel", "closinglabel"}:
        return "periodEndLabel"
    if "negatedterse" in compact:
        return "negatedTerseLabel"
    if "negatedtotal" in compact:
        return "negatedTotalLabel"
    if "negated" in compact:
        return "negatedLabel"
    if "total" in compact:
        return "totalLabel"
    if "terse" in compact:
        return "terseLabel"
    if "verbose" in compact:
        return "verboseLabel"
    if compact == "dartlabel":
        return "dart_label"
    return key or "label"

def preferred_display_label(concept, labels, preferred_label="", language="ko", fallback=None, xsd=None):
    """PRE preferredLabel role과 동일한 lab-ko/lab-en label을 선택합니다.

    언어는 엄격히 분리합니다. 표시 한글명은 ko(또는 언어 미지정), 표시 영문명은
    en(또는 언어 미지정)에서만 찾으며 ko/en 사이를 교차 대체하지 않습니다.
    """
    data = _label_data_for_concept(concept, labels, xsd=xsd)
    if isinstance(data, str):
        return data or fallback or concept
    if not isinstance(data, dict):
        return fallback or concept

    preferred_key = normalized_label_role_key(preferred_label)

    def lookup(lang, role):
        role_map = data.get(lang, {})
        if not isinstance(role_map, dict):
            return ""
        if role_map.get(role):
            return role_map[role]
        wanted = normalized_label_role_key(role)
        for stored_role, value in role_map.items():
            if value and normalized_label_role_key(stored_role) == wanted:
                return value
        return ""

    # preferredLabel이 있으면 동일 role을 먼저 조회합니다.
    for lang in (language, "und"):
        value = lookup(lang, preferred_key)
        if value:
            return value

    # 해당 preferred role resource가 없는 경우에만 같은 언어의 standard label로 fallback.
    for lang in (language, "und"):
        for role in ("label", "terseLabel", "verboseLabel"):
            value = lookup(lang, role)
            if value:
                return value

    return fallback or concept

def display_label(concept, labels, fallback=None, xsd=None):
    return preferred_display_label(concept, labels, "", "ko", fallback, xsd=xsd)

def datatype_label(type_name):
    """XSD type을 KOX 속성 패널에 표시하기 쉬운 데이터 타입명으로 변환한다."""
    t = (type_name or "").lower()
    if "monetary" in t:
        return "숫자(Monetary)"
    if "shares" in t:
        return "숫자(Shares)"
    if "perShare".lower() in t:
        return "숫자(Per share)"
    if "decimal" in t or "integer" in t or "pure" in t or "percent" in t:
        return "숫자"
    if "textblock" in t:
        return "문장(TextBlock)"
    if "string" in t or "escaped" in t:
        return "문자"
    return type_name or "-"


def period_type_label(period_type):
    """XBRL periodType을 한글 표시명으로 변환한다."""
    p = (period_type or "").lower()
    if p == "instant":
        return "특정 시점"
    if p == "duration":
        return "기간"
    return period_type or "-"


def balance_label(balance):
    """XBRL balance 속성을 한글 표시명으로 변환한다."""
    b = (balance or "").lower()
    if b == "debit":
        return "차변"
    if b == "credit":
        return "대변"
    return balance or "-"


def find_xsd_meta(concept, xsd=None):
    """canonical concept, XSD id, Full ID, alias 중 어느 값으로 들어와도 메타데이터를 찾습니다."""
    xsd = xsd or {}
    if concept in xsd:
        return xsd[concept]
    raw = str(concept or "")
    cleaned = clean_qname(raw)
    for name, meta in xsd.items():
        aliases = set(meta.get("aliases") or [])
        aliases.update({name, meta.get("name", ""), meta.get("id", ""), meta.get("full_id", "")})
        if raw in aliases or cleaned in aliases or clean_qname(meta.get("id", "")) == cleaned:
            return meta
    return {}


def full_concept_id(concept, meta=None):
    """속성 탭의 ID를 XSD/PRE locator의 ``to_concept`` ID로 반환합니다.

    기본 영문 label을 ID로 사용하지 않습니다. taxonomy prefix가 보존된 ``full_id``를
    우선 사용하고, 없을 때만 원본 XSD id 또는 canonical concept로 보완합니다.
    """
    meta = meta or {}
    full_id = str(meta.get("full_id") or "").strip()
    if full_id:
        return full_id.replace(":", "_", 1)
    raw_id = str(meta.get("id") or "").strip()
    if raw_id:
        return raw_id.replace(":", "_", 1)
    return str(concept or "-")



def label_value(concept, labels, language="ko", role_key="label", xsd=None):
    data = _label_data_for_concept(concept, labels, xsd=xsd)

    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return ""

    wanted = normalized_label_role_key(role_key)
    role_map = data.get(language, {})

    if isinstance(role_map, dict):
        if role_map.get(wanted):
            return role_map[wanted]

        for key, value in role_map.items():
            if value and normalized_label_role_key(key) == wanted:
                return value

    return ""



def apply_role_value_sign(value, preferred_label=""):
    """NEGATED role의 경우 값의 부호를 반전한다."""
    if value in (None, ""):
        return value

    role_key = normalized_label_role_key(preferred_label)
    if role_key not in {"negatedLabel", "negatedTerseLabel", "negatedTotalLabel"}:
        return value

    if isinstance(value, (int, float)):
        return -value

    text = str(value).strip()
    if text in {"", "-", "+"}:
        return value

    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return str(-float(text)) if "." in text else str(-int(text))

    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        number = text.replace(",", "")
        return f"{-float(number):,.0f}" if "." not in number else f"{-float(number):,.4f}".rstrip("0").rstrip(".")

    return value


def concept_properties(
    concept,
    labels=None,
    xsd=None,
    kind=None,
    fact=None,
    display_name=None,
    preferred_label="",
):
    """
    기본 label과 PRE preferredLabel 표시명을 분리합니다.
    """
    concept = concept or ""
    labels = labels or {}
    xsd = xsd or {}
    meta = find_xsd_meta(concept, xsd) if concept else {}
    element_kind = (
        kind
        or meta.get("kind")
        or concept_kind_by_name(concept)
    )

    base_ko = (
        label_value(concept, labels, "ko", "label", xsd=xsd)
        or display_label(concept, labels, concept, xsd=xsd)
    )
    base_en = (
        label_value(concept, labels, "en", "label", xsd=xsd)
        or concept
    )

    display_ko = preferred_display_label(
        concept,
        labels,
        preferred_label,
        "ko",
        display_name or base_ko or concept,
        xsd=xsd,
    )
    display_en = preferred_display_label(
        concept,
        labels,
        preferred_label,
        "en",
        base_en or concept,
        xsd=xsd,
    )

    role_key = normalized_label_role_key(preferred_label)

    expression_names = {
        "label": "기본",
        "periodStartLabel": "기초(Beginning)",
        "periodEndLabel": "기말(Ending)",
        "totalLabel": "합계(Total)",
        "terseLabel": "별칭1",
        "verboseLabel": "상세(Verbose)",
        "negatedLabel": "기본(Negated)",
        "negatedTerseLabel": "별칭1(Negated)",
        "negatedTotalLabel": "합계(Negated)",
        "dart_label": "DART",
    }
    expression = expression_names.get(role_key or "label", role_key or "기본")

    value_for_display = apply_role_value_sign(
        (fact or {}).get("value"),
        preferred_label,
    )

    return {
        "id": full_concept_id(concept, meta),
        "ID": full_concept_id(concept, meta),
        "concept": concept,
        "표현 속성": expression,
        "표현속성": expression,
        "기본 한글명": base_ko or concept,
        "기본한글명": base_ko or concept,
        "기본 영문명": base_en or concept,
        "기본영문명": base_en or concept,
        "표시 한글명": display_ko or base_ko or concept,
        "표시한글명": display_ko or base_ko or concept,
        "표시 영문명": display_en or base_en or concept,
        "표시영문명": display_en or base_en or concept,
        "요소 구분": element_kind,
        "데이터 타입": datatype_label(meta.get("type", "")),
        "차변/대변": balance_label(meta.get("balance", "")),
        "0 표시": "표시 안함",
        "소수점 자릿수": (fact or {}).get("decimals") or "-",
        "정수 자릿수": (
            "15"
            if "monetary" in meta.get("type", "").lower()
            else "-"
        ),
        "기간 속성": period_type_label(meta.get("periodType", "")),
        "통화 및 단위정보": (fact or {}).get("unit") or "-",
        "_display_value": value_for_display,
    }


def occurrence_properties(occurrence, labels=None, xsd=None, fact=None):
    """Build property data for one PRE/DEF concept occurrence.

    An occurrence owns the preferredLabel, while its concept owns XSD metadata
    and lab-ko/lab-en resources.  Keeping that distinction prevents repeated
    concepts with different presentation roles from sharing a display label.
    """
    occurrence = occurrence or {}
    concept = occurrence.get("to_concept") or occurrence.get("concept_id") or occurrence.get("concept") or ""
    props = concept_properties(
        concept,
        labels,
        xsd,
        kind=occurrence.get("kind"),
        display_name=occurrence.get("display_name"),
        preferred_label=occurrence.get("preferredLabel", ""),
        fact=fact,
    )

    # Compact aliases are retained for callers that use the KOX field names.
    props.update({
        "ID": props.get("id", concept),
        "표현속성": props.get("표현 속성", "기본"),
        "기본한글명": props.get("기본 한글명", concept),
        "기본영문명": props.get("기본 영문명", concept),
        "표시한글명": props.get("표시 한글명", concept),
        "표시영문명": props.get("표시 영문명", concept),
        "Decimals": (fact or {}).get("decimals") or "-",
        "Precision": (fact or {}).get("precision") or "-",
        "Unit": str((fact or {}).get("unit") or "-").replace(":", "_", 1),
    })
    return props

def is_number_text(value):
    if value is None:
        return False
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", str(value).strip().replace(",", "")))


def format_number(value):
    try:
        text = str(value).strip().replace(",", "")
        if text == "":
            return ""
        if "." in text:
            return f"{float(text):,.4f}".rstrip("0").rstrip(".")
        return f"{int(text):,}"
    except Exception:
        return str(value)


def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, set):
        return sorted(list(obj))
    if isinstance(obj, tuple):
        return [make_json_safe(v) for v in obj]
    return obj


def pick_xbrl_instance_from_zip(zip_obj):
    """
    ZIP 내부에서 실제 XBRL instance 문서를 찾습니다.

    기존 로직은 확장자가 .xml/.xbrl이고 root local-name이 정확히 xbrl인 파일만
    인정했기 때문에, 다음 경우 instance 탐색에 실패할 수 있었습니다.

    - 파일명이 대문자 확장자이거나 확장자가 없는 경우
    - ZIP 안에 하위 ZIP이 한 번 더 들어 있는 경우
    - XML parser가 일부 외부 참조/인코딩 문제로 root 판별에 실패하는 경우
    - instance 파일명이 일반적인 패턴과 다른 경우

    판별 우선순위:
    1. XML root가 xbrli:xbrl
    2. 본문에 xbrli:context와 contextRef가 함께 존재
    3. 파일명/크기 기반 후보
    4. 하위 ZIP 재귀 탐색
    """
    candidates = []
    nested_zip_names = []

    for name in zip_obj.namelist():
        if name.endswith("/"):
            continue

        low = name.lower()
        base = low.rsplit("/", 1)[-1]

        if low.endswith(".zip"):
            nested_zip_names.append(name)
            continue

        # taxonomy/linkbase 파일은 instance 후보에서 우선 제외합니다.
        if low.endswith(".xsd"):
            continue
        if any(token in base for token in (
            "_pre", "-pre", "presentation",
            "_def", "-def", "definition",
            "_lab", "-lab", "label",
            "_cal", "-cal", "calculation",
            "schema"
        )):
            continue

        try:
            raw = zip_obj.read(name)
        except Exception:
            continue

        if not raw or len(raw) < 20:
            continue

        # 바이너리 파일은 제외합니다.
        head = raw[:1000].lstrip()
        if not (
            head.startswith(b"<?xml")
            or head.startswith(b"<")
            or b"<xbrli:xbrl" in raw[:5000]
            or b":xbrl" in raw[:5000]
        ):
            continue

        score = 0
        root_is_xbrl = False

        try:
            root = ET.fromstring(raw)
            root_is_xbrl = local_name(root.tag).lower() == "xbrl"
            if root_is_xbrl:
                score += 1000
        except Exception:
            # 전체 파싱이 실패하더라도 아래 signature 검사로 후보를 유지합니다.
            pass

        sample = raw[:200000].lower()

        if b"<xbrli:xbrl" in sample or b":xbrl" in sample:
            score += 500
        if b"<xbrli:context" in sample or b":context" in sample:
            score += 250
        if b"contextref=" in sample:
            score += 250
        if b"<xbrli:unit" in sample or b":unit" in sample:
            score += 100

        if low.endswith(".xbrl"):
            score += 120
        elif low.endswith(".xml"):
            score += 60

        if "instance" in base:
            score += 100

        # 일반적으로 instance가 linkbase보다 크므로 동점일 때 참고합니다.
        score += min(len(raw) // 100000, 50)

        if score >= 300:
            candidates.append((score, len(raw), name, raw, root_is_xbrl))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, name, raw, _ = candidates[0]
        return name, raw

    # DART ZIP 안에 하위 ZIP이 포함된 변형도 처리합니다.
    for nested_name in nested_zip_names:
        try:
            nested_raw = zip_obj.read(nested_name)
            with zipfile.ZipFile(io.BytesIO(nested_raw)) as nested_zip:
                found_name, found_raw = pick_xbrl_instance_from_zip(nested_zip)
                if found_name:
                    return f"{nested_name}!/{found_name}", found_raw
        except Exception:
            continue

    return None, None


# ======================================================
# XSD / labels / linkbases
# ======================================================
