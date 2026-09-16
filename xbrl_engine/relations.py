from collections import defaultdict
from .utils import *

def child_map(arcs, arcrole_contains=None):
    """
    arc 목록을 parent -> children 구조로 변환한다.

    개선 사항:
    - 같은 parent 아래에서 order만 다르고 to_concept가 같은 arc가 반복되는 경우가 있다.
    - 이 경우 표 하단이나 header에 같은 member가 중복 표시될 수 있으므로
      parent + to concept + arcrole 기준으로 첫 번째만 유지한다.
    """
    m = defaultdict(list)
    seen = defaultdict(set)

    for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
        arcrole = a.get("arcrole", "")

        if arcrole_contains and arcrole_contains not in arcrole:
            continue

        frm = a.get("from")
        to = a.get("to")

        if not frm or not to:
            continue

        key = (to, arcrole_contains or arcrole, a.get("preferredLabel", ""), a.get("order", 0))

        if key in seen[frm]:
            continue

        seen[frm].add(key)
        m[frm].append({
            "concept": to,
            "order": a.get("order", 0),
            "arcrole": arcrole,
            "preferredLabel": a.get("preferredLabel", ""),
        })

    return m


def roots(arcs):
    p, c = set(), set()
    for a in arcs:
        if a.get("from"):
            p.add(a["from"])
        if a.get("to"):
            c.add(a["to"])
    return sorted(list(p - c))


def walk(cm, root, max_depth=50):
    out, seen = [], set()
    def _walk(node, depth):
        if depth > max_depth:
            return
        for ch in cm.get(node, []):
            key=(node,ch["concept"],depth,ch.get("preferredLabel",""),ch.get("order",0))
            if key in seen: continue
            seen.add(key)
            out.append({"concept":ch["concept"],"depth":depth+1,"order":ch.get("order",0),"arcrole":ch.get("arcrole",""),"preferredLabel":ch.get("preferredLabel","")})
            _walk(ch["concept"], depth+1)
    _walk(root,0)
    return out

def pre_nodes(bundle):
    """PRE tree를 occurrence 단위로 펼쳐 preferredLabel 중복을 보존합니다."""
    arcs = bundle.get("pre", {}).get("arcs", [])
    cm = child_map(arcs)
    out = []

    def _walk(node, depth, preferred="", order=0, path=None):
        path = set(path or set())
        if node in path or depth > 80:
            return
        out.append({
            "concept": node,
            "depth": depth,
            "order": order,
            "preferredLabel": preferred or "",
        })
        next_path = set(path)
        next_path.add(node)
        for child in cm.get(node, []):
            _walk(child["concept"], depth + 1,
                  child.get("preferredLabel", ""),
                  child.get("order", 0), next_path)

    for root in roots(arcs):
        _walk(root, 0, "", 0, set())
    return out

def build_bundles(role_types, pre_roles, def_roles):
    uris = set(role_types) | set(pre_roles) | set(def_roles)
    bundles = {}
    for uri in uris:
        meta = role_types.get(uri, {})
        code = meta.get("role_code") or extract_role_code("", uri)
        base, suffix = role_base_suffix(code)
        title = meta.get("display_title") or clean_role_definition("", code)
        bundles[uri] = {
            "role_uri": uri,
            "role_code": code,
            "role_base": base,
            "role_suffix": suffix,
            "display_title": title,
            "definition": meta.get("definition", ""),
            "used_on": list(meta.get("used_on") or []),
            "has_calculation_link": bool(meta.get("has_calculation_link")),
            "group": role_group(base, title),
            "pre": pre_roles.get(uri, {"arcs": []}),
            "def": def_roles.get(uri, {"arcs": []}),
        }
    return bundles



def bundle_has_body_statement(bundle):
    """
    제목 정보가 불완전할 때만 사용하는 본문 role 보조 판정입니다.

    기존에는 PRE/DEF의 모든 하위 concept를 검색했기 때문에,
    '16. 투자부동산' 같은 주석 안에 StatementOfFinancialPosition 관련
    concept가 하나라도 있으면 본문으로 오분류될 수 있었습니다.

    수정 후에는:
    - 번호가 붙은 주석 제목은 즉시 False
    - PRE presentation tree의 root concept만 검사
    - 명확한 4대 재무제표 root signature만 허용
    """
    title = bundle.get("display_title", "")

    if is_numbered_note_title(title):
        return False

    if is_body_title(title):
        return True

    pre_arcs = bundle.get("pre", {}).get("arcs", [])
    if not pre_arcs:
        return False

    parent_nodes = {a.get("from") for a in pre_arcs if a.get("from")}
    child_nodes = {a.get("to") for a in pre_arcs if a.get("to")}
    root_nodes = parent_nodes - child_nodes

    root_signatures = (
        "statementoffinancialposition",
        "statementofcomprehensiveincome",
        "statementofprofitorlossandothercomprehensiveincome",
        "statementofchangesinequity",
        "statementofcashflows",
    )

    for root in root_nodes:
        compact = re.sub(r"[^a-z0-9]", "", (root or "").lower())
        if any(signature in compact for signature in root_signatures):
            return True

    return False

def group_bundles(bundles):
    grouped = defaultdict(list)
    for uri, b in bundles.items():
        if len(b.get("pre", {}).get("arcs", [])) + len(b.get("def", {}).get("arcs", [])) == 0:
            continue
        grouped[b.get("role_base")].append((uri, b))
    docs = {}
    for base, items in grouped.items():
        items = sorted(items, key=lambda x: (x[1].get("role_suffix") != "", x[1].get("role_suffix", "").lower(), x[1].get("role_code", "")))
        base_bundle = next((b for _, b in items if not b.get("role_suffix")), items[0][1])
        title = base_bundle.get("display_title") or f"[{base}]"
        title = re.sub(r"\[[A-Z]\d+[a-zA-Z]\]", f"[{base}]", title)
        # 본문/주석 분류 규칙
        # 1) 자본변동표는 기존 제목 기반 판정을 유지합니다.
        # 2) 그 밖의 Role은 XSD roleType/link:usedOn에 calculationLink가
        #    하나라도 선언되어 있으면 본문으로 분류합니다.
        # 3) calculationLink가 없으면 재무제표와 유사한 concept를 포함해도 주석입니다.
        compact_title = re.sub(r"\s+", "", title or "")
        is_equity_statement = "자본변동표" in compact_title
        has_calculation_link = any(
            bool(bundle.get("has_calculation_link"))
            for _, bundle in items
        )
        is_body = is_equity_statement or has_calculation_link

        if is_body:
            # 본문 role에 같은 base의 주석 suffix role(a, b, c...)가 섞이면
            # 주석 TextBlock/Axis/Member가 재무제표 본문에 나타납니다.
            # 따라서 본문은 suffix가 없는 base role만 사용합니다.
            body_roles = [(uri, b) for uri, b in items if not b.get("role_suffix")]
            selected_roles = body_roles[:1] if body_roles else [items[0]]
        else:
            selected_roles = items

        group_name = f"{role_scope(base)}재무제표 {'본문' if is_body else '주석'}"
        docs[base] = {
            "role_id": base,
            "display_title": title,
            "group": group_name,
            "scope": role_scope(base),
            "is_body": is_body,
            "roles": selected_roles,
        }
    return docs


# ======================================================
# Fact matching
# ======================================================
