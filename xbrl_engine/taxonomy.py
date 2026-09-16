import xml.etree.ElementTree as ET
from .config import *
from .utils import *

def classify_xsd_element(concept, elem):
    sub = elem.get("substitutionGroup", "") or ""
    typ = elem.get("type", "") or ""
    abstract = str(elem.get("abstract", "")).lower() == "true"
    by_name = concept_kind_by_name(concept)
    if by_name != "item":
        return by_name
    if "hypercubeItem" in sub:
        return "table"
    if "dimensionItem" in sub:
        return "axis"
    if "textBlockItemType" in typ:
        return "text"
    if abstract:
        return "abstract"
    return "item"


def parse_xsd_metadata(zip_obj):
    role_types, xsd = {}, {}
    for name in zip_obj.namelist():
        if not name.lower().endswith(".xsd"):
            continue
        try:
            root = ET.fromstring(zip_obj.read(name))
        except Exception:
            continue
        for rt in root.findall(".//link:roleType", NS):
            uri = rt.get("roleURI", "")
            def_node = rt.find("link:definition", NS)
            definition = def_node.text.strip() if def_node is not None and def_node.text else ""
            code = extract_role_code(definition, uri)
            base, suffix = role_base_suffix(code)
            title = clean_role_definition(definition, code)

            # XSD roleType/link:usedOn을 보존합니다. 자본변동표를 제외한
            # 본문/주석 판정에서는 calculationLink 사용 여부를 기준으로 합니다.
            used_on = []
            for used_node in rt.findall("link:usedOn", NS):
                value = (used_node.text or "").strip()
                if value:
                    used_on.append(value)
            used_on = list(dict.fromkeys(used_on))
            has_calculation_link = any(
                local_name(value).lower() == "calculationlink"
                or value.lower().endswith(":calculationlink")
                for value in used_on
            )

            if uri:
                role_types[uri] = {
                    "role_uri": uri,
                    "role_code": code,
                    "role_base": base,
                    "role_suffix": suffix,
                    "display_title": title,
                    "definition": definition,
                    "used_on": used_on,
                    "has_calculation_link": has_calculation_link,
                    "group": role_group(base, title),
                }
        target_namespace = root.get("targetNamespace", "")
        prefix = taxonomy_prefix(target_namespace, name)
        for elem in root.iter():
            if local_name(elem.tag) != "element":
                continue
            raw_name = (elem.get("name") or "").strip()
            raw_id = (elem.get("id") or "").strip()
            concept = clean_qname(raw_name or raw_id)
            if not concept:
                continue
            # 속성창 ID는 label/영문명이 아니라 taxonomy prefix를 포함한 Full ID를 사용합니다.
            # 예: FinancialAssets -> ifrs-full_FinancialAssets
            if raw_id and (raw_id.startswith(prefix + "_") or raw_id.startswith(prefix + ":")):
                full_id = raw_id.replace(":", "_", 1)
            else:
                full_id = f"{prefix}_{concept}"
            aliases = list(dict.fromkeys([x for x in [raw_name, raw_id, full_id, clean_qname(raw_id)] if x]))
            # Full ID is the canonical key.  A local-name key would make
            # ifrs-full_Revenue and dart_Revenue overwrite one another, which
            # also disconnects their lab-ko/lab-en resources.
            xsd[full_id] = {
                "name": concept,
                "id": raw_id or concept,
                "full_id": full_id,
                "prefix": prefix,
                "targetNamespace": target_namespace,
                "aliases": aliases,
                "type": elem.get("type", ""),
                "periodType": elem.get("{http://www.xbrl.org/2003/instance}periodType", ""),
                "balance": elem.get("{http://www.xbrl.org/2003/instance}balance", ""),
                "substitutionGroup": elem.get("substitutionGroup", ""),
                "abstract": str(elem.get("abstract", "")).lower() == "true",
                "kind": classify_xsd_element(concept, elem),
            }
    return role_types, xsd


def label_role_key(role):
    if not role:
        return "label"
    return str(role).rstrip("/").rsplit("/", 1)[-1] or "label"


def label_language_key(lang):
    value = (lang or "").lower()
    if value.startswith("ko"):
        return "ko"
    if value.startswith("en"):
        return "en"
    return value or "und"


def parse_label_linkbases(zip_obj, xsd=None):
    """Label linkbase를 ``concept -> language -> role -> text`` 구조로 읽습니다.

    핵심 규칙
    - PRE/DEF locator와 label locator는 같은 XSD concept key로 정규화합니다.
    - ``xlink:role`` 전체 URI는 ``normalized_label_role_key``로 통일합니다.
    - ``xml:lang``가 빠진 국내 제출파일은 파일명(``lab-ko``, ``label-en``)으로
      언어를 보완합니다.
    - standard label role이 생략된 경우에는 기본 ``label`` role로 처리합니다.
    """
    labels = {}
    xsd = xsd or {}

    def file_language(filename):
        low = filename.lower().replace("_", "-")
        if any(token in low for token in ("lab-ko", "label-ko", "-ko.", "/ko/")):
            return "ko"
        if any(token in low for token in ("lab-en", "label-en", "-en.", "/en/")):
            return "en"
        return ""

    for name in zip_obj.namelist():
        low = name.lower()
        if not low.endswith((".xml", ".xbrl")):
            continue
        if not any(k in low for k in ("lab", "label", "_ko", "-ko", "_en", "-en")):
            continue
        try:
            root = ET.fromstring(zip_obj.read(name))
        except Exception:
            continue

        inferred_lang = file_language(name)
        for link in root.findall(".//link:labelLink", NS):
            locs, resources = {}, {}
            for loc in link.findall("link:loc", NS):
                locator_label = loc.get(XLINK_LABEL)
                href = loc.get(XLINK_HREF)
                if locator_label and href:
                    locs[locator_label] = resolve_concept_ref(href, xsd)

            for res in link.findall("link:label", NS):
                resource_label = res.get(XLINK_LABEL)
                text = "".join(res.itertext()).strip()
                if not resource_label or not text:
                    continue
                role_uri = (res.get(XLINK_ROLE) or "http://www.xbrl.org/2003/role/label").strip()
                language = label_language_key(res.get(XML_LANG, "") or inferred_lang)
                resources[resource_label] = {
                    "text": text,
                    "role_key": normalized_label_role_key(role_uri),
                    "language": language,
                }

            for arc in link.findall("link:labelArc", NS):
                concept = locs.get(arc.get(XLINK_FROM))
                resource = resources.get(arc.get(XLINK_TO))
                if not concept or not resource:
                    continue
                role_map = labels.setdefault(concept, {}).setdefault(resource["language"], {})
                # 동일 role이 여러 번 나오면 먼저 선언된 label을 우선합니다.
                role_map.setdefault(resource["role_key"], resource["text"])

    priority = (
        ("ko", "label"), ("ko", "terseLabel"), ("ko", "verboseLabel"),
        ("en", "label"), ("en", "terseLabel"), ("en", "verboseLabel"),
        ("und", "label"),
    )
    for concept, data in list(labels.items()):
        default = ""
        for language, role in priority:
            default = data.get(language, {}).get(role, "")
            if default:
                break
        data["_default"] = default or concept

    # XSD name/id/full_id/alias 어느 형태로 조회해도 같은 label map을 반환합니다.
    alias_pairs = []
    for concept, meta in xsd.items():
        canonical_data = labels.get(concept)
        if not canonical_data:
            for alias in (meta.get("aliases") or []):
                if alias in labels:
                    canonical_data = labels[alias]
                    labels[concept] = canonical_data
                    break
        if not canonical_data:
            continue

        aliases = set(meta.get("aliases") or [])
        aliases.update({
            concept,
            meta.get("name", ""),
            meta.get("id", ""),
            meta.get("full_id", ""),
            clean_qname(meta.get("id", "")),
            clean_qname(meta.get("full_id", "")),
        })
        alias_pairs.extend((alias, canonical_data) for alias in aliases if alias)

    for alias, data in alias_pairs:
        labels.setdefault(alias, data)

    return labels

def parse_generic_linkbase(zip_obj, keywords, link_tag, arc_tag, xsd=None):
    roles = {}
    for name in zip_obj.namelist():
        low = name.lower()
        if not low.endswith((".xml", ".xbrl")):
            continue
        if not any(k in low for k in keywords):
            continue
        try:
            root = ET.fromstring(zip_obj.read(name))
        except Exception:
            continue
        for link in root.findall(f".//link:{link_tag}", NS):
            uri = link.get(XLINK_ROLE, "")
            if not uri:
                continue
            locs, arcs = {}, []
            for loc in link.findall("link:loc", NS):
                lab = loc.get(XLINK_LABEL)
                href = loc.get(XLINK_HREF)
                if lab and href:
                    locs[lab] = resolve_concept_ref(href, xsd)
            for arc in link.findall(f"link:{arc_tag}", NS):
                preferred_label = (arc.get("preferredLabel") or "").strip()
                arcs.append({
                    "from": locs.get(arc.get(XLINK_FROM), arc.get(XLINK_FROM)),
                    "to": locs.get(arc.get(XLINK_TO), arc.get(XLINK_TO)),
                    "order": float(arc.get("order", 0) or 0),
                    "arcrole": arc.get(XLINK_ARCROLE, ""),
                    "preferredLabel": preferred_label,
                    "preferredRoleKey": normalized_label_role_key(preferred_label),
                    "targetRole": arc.get(XLINK_TARGET_ROLE, ""),
                    "file": name,
                })
            roles[uri] = {"role_uri": uri, "file": name, "arcs": sorted(arcs, key=lambda x: (x["order"], x["from"], x["to"]))}
    return roles


def parse_pre(zip_obj, xsd=None):
    return parse_generic_linkbase(zip_obj, ["pre", "presentation"], "presentationLink", "presentationArc", xsd)


def parse_def(zip_obj, xsd=None):
    return parse_generic_linkbase(zip_obj, ["def", "definition"], "definitionLink", "definitionArc", xsd)


# ======================================================
# XBRL context / fact
# ======================================================
