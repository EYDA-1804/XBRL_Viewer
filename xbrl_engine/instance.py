import xml.etree.ElementTree as ET
from .config import *
from .utils import *

def period_info_to_label(p):
    if not p:
        return "-"
    if p.get("type") == "instant":
        return p.get("date", "-")
    s, e = p.get("start_date", ""), p.get("end_date", "")
    return f"{s} ~ {e}" if s and e else (e or s or "-")


def period_end(p):
    if not p:
        return ""
    return p.get("date") or p.get("end_date") or ""


def scope_from_member(mem):
    m = (mem or "").lower()
    if any(x in m for x in ["separate", "individual", "standalone", "별도", "개별"]):
        return "별도"
    if any(x in m for x in ["consolidated", "연결"]):
        return "연결"
    return "unknown"


def is_scope_member(mem):
    return scope_from_member(mem) != "unknown"


def is_report_scope_concept(concept, label=""):
    """
    주석 표의 열 구조에서 제외할 연결/별도 범위 구성요소.
    예: ConsolidatedFinancialStatementsMember, SeparateFinancialStatementsMember 등.
    Axis / Domain / Member 중에서도 보고범위만 의미하는 요소는 표 컬럼으로 쓰지 않는다.
    """
    text = f"{concept or ''} {label or ''}".lower()

    keywords = [
        "consolidated",
        "separate",
        "individual",
        "standalone",
        "연결",
        "별도",
        "개별",
    ]

    return any(k in text for k in keywords)


def parse_contexts_units(root, xsd=None):
    contexts = {}
    for ctx in root.findall(".//xbrli:context", NS):
        cid = ctx.get("id")
        pinfo = {}
        p = ctx.find(".//xbrli:period", NS)
        if p is not None:
            ins = p.find("xbrli:instant", NS)
            sd = p.find("xbrli:startDate", NS)
            ed = p.find("xbrli:endDate", NS)
            if ins is not None and ins.text:
                pinfo = {"type": "instant", "date": ins.text.strip()}
            elif sd is not None and ed is not None:
                pinfo = {"type": "duration", "start_date": sd.text.strip() if sd.text else "", "end_date": ed.text.strip() if ed.text else ""}
        members, dimensions, scope = [], [], "unknown"
        dimension_map = {}
        full_dimension_map = {}

        for em in ctx.findall(".//xbrldi:explicitMember", NS):
            # Keep the same canonical Full IDs used by DEF axis/member arcs.
            # Local-name-only context keys make every detail column miss while
            # an unqualified total column can still match.
            dim = resolve_concept_ref(em.get("dimension", ""), xsd)
            mem = resolve_concept_ref(em.text.strip() if em.text else "", xsd)

            if dim and mem:
                full_dimension_map[dim] = mem

            dimensions.append({"dimension": dim, "member": mem})

            sc = scope_from_member(mem)
            if sc != "unknown":
                scope = sc

            # Consolidated/Separate 등 보고범위 member는 표 컬럼 매칭에서는 제외한다.
            if mem and not is_scope_member(mem):
                members.append(mem)
                if dim:
                    dimension_map[dim] = mem

        contexts[cid] = {
            "id": cid,
            "period": pinfo,
            "period_label": period_info_to_label(pinfo),
            "period_end_date": period_end(pinfo),
            "members": members,
            "member_set": set(members),
            "dimensions": dimensions,
            "dimension_map": dimension_map,
            "full_dimension_map": full_dimension_map,
            "scope": scope
        }
    dates = sorted({c["period_end_date"] for c in contexts.values() if c.get("period_end_date")}, reverse=True)
    labels = ["CY", "PY", "PY2"]
    date_key = {d: labels[i] for i, d in enumerate(dates[:3])}
    for c in contexts.values():
        c["period_key"] = date_key.get(c.get("period_end_date"), "OTHER")
    units = {}
    for u in root.findall(".//xbrli:unit", NS):
        uid = u.get("id")
        ms = [m.text.strip() for m in u.findall(".//xbrli:measure", NS) if m.text]
        units[uid] = " / ".join(ms)
    return contexts, units


def parse_instance(data, labels, xsd=None):
    root = ET.fromstring(data)
    contexts, units = parse_contexts_units(root, xsd)
    facts = []
    for e in root.iter():
        cref = e.get("contextRef")
        if not cref:
            continue
        val = e.text.strip() if e.text else ""
        if val == "":
            continue
        namespace = e.tag[1:].split("}", 1)[0] if e.tag.startswith("{") else ""
        concept = resolve_concept_ref(local_name(e.tag), xsd, namespace=namespace)
        ctx = contexts.get(cref, {})
        uref = e.get("unitRef", "")
        facts.append({
            "concept": concept,
            "label": display_label(concept, labels, concept),
            "value": val,
            "formatted_value": format_number(val) if is_number_text(val) else val,
            "contextRef": cref,
            "unitRef": uref,
            "unit": units.get(uref, uref),
            "decimals": e.get("decimals", ""),
            "precision": e.get("precision", ""),
            "is_numeric": is_number_text(val),
            "period_key": ctx.get("period_key", "OTHER"),
            "period_label": ctx.get("period_label", "-"),
            "scope": ctx.get("scope", "unknown"),
            "members": list(ctx.get("members", [])),
            "member_set": set(ctx.get("member_set", set())),
            "dimension_map": dict(ctx.get("dimension_map", {})),
            "full_dimension_map": dict(ctx.get("full_dimension_map", {})),
        })
    return contexts, units, facts


# ======================================================
# Tree / relation helpers
# ======================================================
