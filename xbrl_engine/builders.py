from collections import defaultdict
from itertools import product
from .utils import *
from .relations import *
from .facts import *

from .instance import is_report_scope_concept


def pre_ordered_stream(bundle, xsd):
    """PRE presentationArc를 order 순서의 occurrence stream으로 펼칩니다."""
    arcs = [
        arc
        for arc in bundle.get("pre", {}).get("arcs", [])
        if arc.get("from") and arc.get("to")
    ]
    ordered_arcs = sorted(
        enumerate(arcs),
        key=lambda pair: (
            pair[1].get("order", 0),
            pair[0],
        ),
    )

    children = defaultdict(list)
    child_concepts = set()
    parent_order = []

    for arc_index, arc in ordered_arcs:
        parent = arc.get("from")
        child = arc.get("to")

        if parent not in children:
            parent_order.append(parent)

        children[parent].append({
            "arc_index": arc_index,
            "parent": parent,
            "concept": child,
            "order": arc.get("order", 0),
            "preferredLabel": (arc.get("preferredLabel") or "").strip(),
        })
        child_concepts.add(child)

    roots_in_order = [
        parent
        for parent in parent_order
        if parent not in child_concepts
    ]
    roots_in_order = list(dict.fromkeys(roots_in_order))

    if not roots_in_order:
        roots_in_order = list(dict.fromkeys(parent_order))

    stream = []
    sequence = 0

    def visit(concept, parent, depth, path, occurrence_key, order=0, preferred_label=""):

        nonlocal sequence

        if occurrence_key in path or depth > 100:
            return

        sequence += 1
        stream.append({
            "sequence": sequence,
            "concept": concept,
            "parent": parent,
            "depth": depth,
            "occurrence_key": occurrence_key,
            "occurrence_id": "|".join(str(part) for part in occurrence_key),
            "order": order,
            "preferredLabel": preferred_label,
            "preferredRoleKey": normalized_label_role_key(preferred_label),
            "kind": concept_kind(concept, xsd),
        })

        next_path = set(path)
        next_path.add(occurrence_key)

        for child_info in children.get(concept, []):
            visit(
                child_info["concept"],
                concept,
                depth + 1,
                next_path,
                (
                    child_info["arc_index"],
                    child_info["parent"],
                    child_info["concept"],
                ),
                child_info.get("order", 0),
                child_info.get("preferredLabel", ""),
            )

    for root_index, root in enumerate(roots_in_order):
        visit(
            root,
            None,
            0,
            set(),
            ("root", root_index, root),
            0,
            "",
        )

    return stream


def collect_pre_table_candidates(role_pairs, xsd):
    """PRE Table 후보를 실제 occurrence order와 함께 수집합니다."""
    candidates = []

    for role_index, (uri, bundle) in enumerate(role_pairs):
        stream = pre_ordered_stream(bundle, xsd)

        for stream_index, entry in enumerate(stream):
            if entry.get("kind") != "table":
                continue

            candidates.append({
                "key": (
                    uri,
                    entry.get("occurrence_key"),
                    entry.get("concept"),
                ),
                "uri": uri,
                "bundle": bundle,
                "table": entry.get("concept"),
                "role_index": role_index,
                "table_index": stream_index,
                "stream_index": stream_index,
                "global_order": (
                    role_index,
                    stream_index,
                ),
            })

    return candidates

def def_row_concepts_for_table(table, bundle, facts, labels, xsd):
    """
    0715 DEF 표 행 concept 집합입니다.
    표 구조를 바꾸지 않고 PRE Table 매칭 점수에만 사용합니다.
    """
    return {
        row.get("concept")
        for row in rows_from_lineitems(
            lineitems_for_table(table, bundle, xsd),
            bundle,
            facts,
            labels,
            xsd,
        )
        if row.get("concept")
    }


def pre_item_concepts_for_table(table, bundle, xsd):
    """
    PRE Table subtree의 item concept 집합입니다.
    Axis/Domain/Member는 매칭 및 context text에서 제외합니다.
    """
    cm = child_map(bundle.get("pre", {}).get("arcs", []))
    result = set()

    def visit(node, seen):
        if not node or node in seen:
            return

        next_seen = set(seen)
        next_seen.add(node)

        for child in cm.get(node, []):
            concept = child.get("concept")
            if not concept:
                continue

            kind = concept_kind(concept, xsd)

            if kind == "table" and concept != table:
                continue
            if kind == "item":
                result.add(concept)
                continue
            if kind in {"axis", "domain", "member"}:
                continue

            visit(concept, next_seen)

    visit(table, set())
    return result


def context_candidate_score(
    def_table,
    def_index,
    def_bundle,
    candidate,
    facts,
    labels,
    xsd,
):
    """
    DEF Table과 PRE Table context의 대응 점수.

    강한 근거만 사용합니다.
    - 동일 Table concept
    - DEF item과 PRE item의 교집합
    - DEF owner와 PRE ancestor path의 교집합
    - 표 label token 유사도
    """
    pre_table = candidate["table"]
    pre_bundle = candidate["bundle"]

    if def_table == pre_table:
        return (100000, 1, 1, 0)

    def_items = def_row_concepts_for_table(
        def_table,
        def_bundle,
        facts,
        labels,
        xsd,
    )
    pre_items = pre_item_concepts_for_table(
        pre_table,
        pre_bundle,
        xsd,
    )

    item_overlap = len(def_items & pre_items)
    item_union = len(def_items | pre_items) or 1
    item_ratio = item_overlap / item_union

    owners = {
        item.get("concept")
        for item in table_owner_concepts(def_table, def_bundle, xsd)
        if item.get("concept")
    }
    context = find_table_pre_context(
        pre_table,
        pre_bundle,
        labels,
        xsd,
    )
    owner_overlap = len(owners & set(context.get("path", [])))

    target_tokens = _table_match_text(def_table, labels, xsd)
    candidate_tokens = _table_match_text(pre_table, labels, xsd)
    token_union = len(target_tokens | candidate_tokens) or 1
    token_ratio = len(target_tokens & candidate_tokens) / token_union

    # 아무 구조적 근거가 없으면 순서만으로 억지 매칭하지 않습니다.
    if item_overlap == 0 and owner_overlap == 0 and token_ratio < 0.35:
        return None

    return (
        item_overlap * 1000 + owner_overlap * 100 + int(token_ratio * 100),
        item_ratio,
        token_ratio,
        -abs(candidate.get("table_index", 0) - def_index),
    )


def choose_pre_context_candidate(
    def_table,
    def_index,
    def_bundle,
    candidates,
    used_keys,
    facts,
    labels,
    xsd,
):
    """
    하나의 DEF Table에 하나의 PRE context만 배정합니다.
    같은 PRE context를 여러 표에 중복 부착하지 않습니다.
    """
    best = None
    best_score = None

    for candidate in candidates:
        if candidate["key"] in used_keys:
            continue

        score = context_candidate_score(
            def_table,
            def_index,
            def_bundle,
            candidate,
            facts,
            labels,
            xsd,
        )
        if score is None:
            continue

        if best_score is None or score > best_score:
            best = candidate
            best_score = score

    if best is not None:
        used_keys.add(best["key"])

    return best


def preferred_label_occurrences(bundle):
    result = defaultdict(list)
    for arc in sorted(bundle.get("pre", {}).get("arcs", []),
                      key=lambda x: (x.get("order", 0), x.get("to", ""), x.get("preferredLabel", ""))):
        concept = arc.get("to")
        if concept:
            result[concept].append(arc.get("preferredLabel", ""))
    return result


def preferred_label_map(bundle):
    result = {}
    for concept, values in preferred_label_occurrences(bundle).items():
        result[concept] = next((v for v in values if v), "")
    return result

def pre_parent_map(bundle):
    result=defaultdict(list)
    for arc in sorted(bundle.get("pre",{}).get("arcs",[]), key=lambda x:(x.get("order",0),x.get("from",""),x.get("to",""))):
        if arc.get("from") and arc.get("to"):
            result[arc["to"]].append({"concept":arc["from"],"order":arc.get("order",0),"preferredLabel":arc.get("preferredLabel","")})
    return result


def table_pre_paths(table,bundle,max_depth=40):
    parents=pre_parent_map(bundle); paths=[]
    def _walk(node,up,seen):
        if node in seen or len(up)>max_depth: return
        infos=parents.get(node,[])
        if not infos:
            paths.append(list(reversed(up+[node]))); return
        seen=set(seen); seen.add(node)
        for info in infos: _walk(info["concept"],up+[node],seen)
    _walk(table,[],set())
    return sorted(paths or [[table]], key=lambda p:(-len(p),tuple(p)))


def is_sentence_area(concept,labels,xsd):
    lab=display_label(concept,labels,""); text=f"{concept} {lab}".lower()
    return "문장영역" in lab or "explanatory" in text or "textblock" in text or concept_kind(concept,xsd)=="text"


def is_overview(concept,labels,xsd):
    if is_sentence_area(concept,labels,xsd): return False
    lab=display_label(concept,labels,""); text=f"{concept} {lab}".lower()
    return "개요" in lab or "overview" in text or concept_kind(concept,xsd)=="abstract"




def find_table_pre_context(table, bundle, labels, xsd):
    """
    PRE order를 기준으로 현재 Table 직전에 배치된 문장영역과 개요를 연결합니다.

    직전 Table 이후부터 현재 Table 이전까지만 검사하므로 다른 표의 context가
    섞이지 않습니다. 부모 경로는 order 정보가 부족할 때만 fallback으로 씁니다.
    """
    stream = pre_ordered_stream(bundle, xsd)
    table_positions = [
        index
        for index, entry in enumerate(stream)
        if entry.get("kind") == "table"
        and entry.get("concept") == table
    ]

    best = {
        "path": [table],
        "sentence": None,
        "overview": None,
        "score": 0,
        "table_order": 10**9,
        "sentence_concepts": [],
        "overview_concepts": [],
    }

    def is_narrative_entry(entry):
        concept = entry.get("concept")
        if not concept:
            return False

        kind = concept_kind(concept, xsd)
        label = display_label(
            concept,
            labels,
            "",
            xsd=xsd,
        )
        combined = f"{concept} {label}".lower()

        return (
            kind == "text"
            or "textblock" in combined
            or "explanatory" in combined
            or "narrative" in combined
            or "disclosuretext" in combined
            or "guidance" in combined
            or "explanation" in combined
            or "문장영역" in combined
        )

    for table_position in table_positions:
        previous_table_position = -1

        for index in range(table_position - 1, -1, -1):
            if stream[index].get("kind") == "table":
                previous_table_position = index
                break

        start = previous_table_position + 1
        positions = range(start, table_position)

        overview_positions = [
            position
            for position in positions
            if is_overview(
                stream[position].get("concept"),
                labels,
                xsd,
            )
        ]
        sentence_positions = [
            position
            for position in range(start, table_position)
            if is_sentence_area(
                stream[position].get("concept"),
                labels,
                xsd,
            )
        ]

        overview_position = (
            overview_positions[-1]
            if overview_positions else None
        )
        sentence_position = None

        if sentence_positions:
            limit = (
                overview_position
                if overview_position is not None
                else table_position
            )
            valid = [
                position
                for position in sentence_positions
                if position < limit
            ]
            if valid:
                sentence_position = valid[-1]

        sentence = (
            stream[sentence_position].get("concept")
            if sentence_position is not None else None
        )
        overview = (
            stream[overview_position].get("concept")
            if overview_position is not None else None
        )

        selected_path = [
            concept
            for concept in (sentence, overview, table)
            if concept
        ]

        if sentence is None or overview is None:
            for path in table_pre_paths(
                table,
                bundle,
                max_depth=20,
            ):
                ancestors = path[:-1]

                path_sentence = next(
                    (
                        concept
                        for concept in ancestors
                        if is_sentence_area(
                            concept,
                            labels,
                            xsd,
                        )
                    ),
                    None,
                )
                path_overview = next(
                    (
                        concept
                        for concept in reversed(ancestors)
                        if concept != path_sentence
                        and is_overview(
                            concept,
                            labels,
                            xsd,
                        )
                    ),
                    None,
                )

                if sentence is None and path_sentence:
                    sentence = path_sentence
                if overview is None and path_overview:
                    overview = path_overview

                if path_sentence or path_overview:
                    selected_path = path
                    break

        sentence_concepts = []
        overview_concepts = []

        if sentence_position is not None:
            sentence_end = (
                overview_position
                if overview_position is not None
                else table_position
            )
            sentence_concepts = [
                stream[position].get("concept")
                for position in range(
                    sentence_position,
                    sentence_end,
                )
                if is_narrative_entry(stream[position])
            ]

        if overview_position is not None:
            overview_concepts = [
                stream[position].get("concept")
                for position in range(
                    overview_position,
                    table_position,
                )
                if is_narrative_entry(stream[position])
            ]

        if sentence and sentence not in sentence_concepts:
            sentence_concepts.insert(0, sentence)
        if overview and overview not in overview_concepts:
            overview_concepts.insert(0, overview)

        sentence_concepts = list(
            dict.fromkeys(sentence_concepts)
        )
        overview_concepts = list(
            dict.fromkeys(overview_concepts)
        )

        score = (
            (10 if sentence else 0)
            + (6 if overview else 0)
            + (2 if sentence_position is not None else 0)
            + (2 if overview_position is not None else 0)
        )

        candidate = {
            "path": selected_path or [table],
            "sentence": sentence,
            "overview": overview,
            "score": score,
            "table_order": table_position,
            "sentence_concepts": sentence_concepts,
            "overview_concepts": overview_concepts,
        }

        if (
            candidate["score"] > best["score"]
            or (
                candidate["score"] == best["score"]
                and candidate["table_order"]
                < best["table_order"]
            )
        ):
            best = candidate

    return best

def statement_rows(bundle, facts, labels, xsd):
    fset = {f["concept"] for f in facts}
    structural = set()
    for arc in bundle.get("def", {}).get("arcs", []):
        arcrole = arc.get("arcrole", "")
        if any(token in arcrole for token in ("hypercube-dimension", "dimension-domain", "dimension-default")):
            structural.update([arc.get("from"), arc.get("to")])
        if "domain-member" in arcrole and concept_kind(arc.get("to"), xsd) in {"axis", "domain", "member", "table", "lineitems", "abstract"}:
            structural.add(arc.get("to"))
    rows, seen = [], set()
    for n in pre_nodes(bundle):
        c = n["concept"]
        occurrence_key = (c, normalized_label_role_key(n.get("preferredLabel", "")))
        if occurrence_key in seen or c not in fset or c in structural or concept_kind(c, xsd) != "item":
            continue
        rows.append({"concept": c, "label": preferred_display_label(c, labels, n.get("preferredLabel", ""), xsd=xsd), "preferredLabel": n.get("preferredLabel", ""), "depth": n.get("depth", 0)})
        seen.add(occurrence_key)
    return rows


def build_body_section(doc, facts, labels, xsd):
    idx = fact_index(facts)
    rows, seen = [], set()
    for _, b in doc["roles"]:
        for r in statement_rows(b, facts, labels, xsd):
            occurrence_key = (r["concept"], normalized_label_role_key(r.get("preferredLabel", "")))
            if occurrence_key not in seen:
                rows.append(r); seen.add(occurrence_key)
    table_rows = []
    for r in rows:
        vals = []
        sample_fact = None
        for p in period_columns():
            f = find_fact(idx, r["concept"], p["key"], [], doc["scope"])
            if f and sample_fact is None:
                sample_fact = f
            raw_value = f.get("formatted_value", f.get("value", "")) if f else ""
            inverted_value = apply_role_value_sign(raw_value, r.get("preferredLabel", ""))
            vals.append({"value": inverted_value, "is_numeric": f.get("is_numeric", False) if f else False})
        if any(v["value"] for v in vals):
            table_rows.append({
                "concept": r["concept"],
                "label": r["label"],
                "depth": r["depth"],
                "preferredLabel": r.get("preferredLabel", ""),
                "preferredRoleKey": normalized_label_role_key(r.get("preferredLabel", "")),
                "properties": concept_properties(
                    r["concept"],
                    labels,
                    xsd,
                    fact=sample_fact,
                    display_name=r["label"],
                    preferred_label=r.get("preferredLabel", ""),
                ),
                "values": vals
            })
    return {"type": "body_statement", "title": doc["display_title"], "columns": period_columns(), "rows": table_rows}


# ======================================================
# Note tables from def/pre/fact/context
# ======================================================

def is_table_arc(a, xsd):
    """
    def.xml에서 표 root를 의미하는 arc인지 판단한다.

    KOX 모델 기준:
    - arcrole에 /all 또는 notAll이 있고
    - to_concept가 Table/Hypercube이면 해당 to_concept가 표 root다.
    """
    arcrole = a.get("arcrole", "")
    return (
        ("/all" in arcrole or "notAll" in arcrole or arcrole.endswith("all"))
        and concept_kind(a.get("to"), xsd) == "table"
    )



def detect_tables(bundle, xsd):
    """
    DEF의 `/all -> Table` 관계로 선언된 실제 Table만 반환합니다.

    PRE에 Table concept가 있다는 이유만으로 새 표를 생성하지 않습니다.
    """
    out = []
    seen = set()
    arcs = bundle.get("def", {}).get("arcs", [])

    for arc in sorted(
        arcs,
        key=lambda item: (item.get("order", 0), item.get("to", "")),
    ):
        table = arc.get("to")

        if not table or table in seen:
            continue

        if is_table_arc(arc, xsd):
            out.append(table)
            seen.add(table)

    return out

def table_owner_concepts(table, bundle, xsd):
    """
    /all arc의 from_concept는 해당 표의 owner/abstract인 경우가 많다.
    owner는 LineItems와 overview를 table에 붙일 때 사용한다.
    """
    owners = []
    for a in bundle.get("def", {}).get("arcs", []):
        if is_table_arc(a, xsd) and a.get("to") == table and a.get("from"):
            owners.append({"concept": a.get("from"), "order": a.get("order", 0)})
    return sorted(owners, key=lambda x: x.get("order", 0))


def lineitems_for_table(table, bundle, xsd):
    """
    def.xml에서 table에 속한 LineItems를 찾는다.

    규칙:
    - arcrole = domain-member
    - to_concept = LineItems
    - from_concept는 table owner 또는 table 주변 abstract
    """
    arcs = bundle.get("def", {}).get("arcs", [])
    owners = {x["concept"] for x in table_owner_concepts(table, bundle, xsd)}
    cm_all = child_map(arcs)

    # owner 하위 concept까지 LineItems의 부모 후보로 허용
    owner_desc = set()
    for owner in owners:
        owner_desc.add(owner)
        if owner in cm_all:
            owner_desc.update(n["concept"] for n in walk(cm_all, owner, max_depth=8))

    candidates = []
    for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
        if "domain-member" not in a.get("arcrole", ""):
            continue
        if concept_kind(a.get("to"), xsd) != "lineitems":
            continue
        if not owners or a.get("from") in owner_desc or a.get("from") == table:
            candidates.append({"concept": a.get("to"), "order": a.get("order", 0), "from": a.get("from")})

    # fallback: role 내 LineItems가 하나면 사용
    if not candidates:
        all_li = []
        for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
            if "domain-member" in a.get("arcrole", "") and concept_kind(a.get("to"), xsd) == "lineitems":
                all_li.append({"concept": a.get("to"), "order": a.get("order", 0), "from": a.get("from")})
        if len(all_li) == 1:
            candidates = all_li

    out, seen = [], set()
    for c in candidates:
        if c["concept"] in seen:
            continue
        seen.add(c["concept"])
        out.append(c)
    return out


def rows_from_lineitems(lineitems, bundle, facts, labels, xsd):
    """LineItems 하위 item concept를 행으로 구성한다."""
    fset = {f["concept"] for f in facts}
    dm = child_map(bundle.get("def", {}).get("arcs", []), "domain-member")
    pre_alias = preferred_label_map(bundle)
    rows, seen = [], set()

    for li in lineitems:
        root = li["concept"]
        group_label = preferred_display_label(root, labels, pre_alias.get(root, ""), xsd=xsd)
        descendants = walk(dm, root) if root in dm else []

        for n in descendants:
            c = n["concept"]
            if c in seen:
                continue
            if concept_kind(c, xsd) == "item":
                rows.append({
                    "concept": c,
                    "label": preferred_display_label(c, labels, pre_alias.get(c, ""), xsd=xsd),
                    "preferredLabel": pre_alias.get(c, ""),
                    "depth": max(n.get("depth", 1) - 1, 0),
                    "order": n.get("order", 0),
                    "row_group": group_label,
                    "row_group_concept": root,
                })
                seen.add(c)

    rows.sort(key=lambda x: (x.get("order", 0), x.get("label", "")))
    return rows


def rows_from_pre_table(table, bundle, facts, labels, xsd):
    """PRE occurrence를 원본 presentationArc 단위로 행으로 구성합니다.

    동일 concept라도 parent/order/preferredLabel이 다르면 서로 다른 occurrence로
    유지합니다. 표시명은 해당 occurrence의 preferredLabel role label을 사용합니다.
    """
    stream = pre_ordered_stream(bundle, xsd)
    table_positions = [
        i for i, entry in enumerate(stream)
        if entry.get("concept") == table and entry.get("kind") == "table"
    ]
    if not table_positions:
        return []

    table_pos = table_positions[0]
    table_depth = stream[table_pos].get("depth", 0)
    subtree = []
    for entry in stream[table_pos + 1:]:
        if entry.get("depth", 0) <= table_depth:
            break
        if entry.get("kind") == "table":
            continue
        subtree.append(entry)

    # In real DART PRE linkbases a Table and its LineItems are often siblings
    # under the same Abstract (Table -> Axis, then sibling LineItems -> Items).
    # If the strict Table subtree has no rows, attach the nearest following
    # sibling LineItems occurrence and preserve each preferredLabel occurrence.
    if not any(entry.get("kind") in {"lineitems", "item"} for entry in subtree):
        table_parent = stream[table_pos].get("parent")
        lineitems_pos = None
        for position in range(table_pos + 1, len(stream)):
            entry = stream[position]
            depth = entry.get("depth", 0)
            if depth < table_depth:
                break
            if (
                depth == table_depth
                and entry.get("parent") == table_parent
                and entry.get("kind") == "lineitems"
            ):
                lineitems_pos = position
                break
        if lineitems_pos is not None:
            lineitems_depth = stream[lineitems_pos].get("depth", table_depth)
            subtree = [stream[lineitems_pos]]
            for entry in stream[lineitems_pos + 1:]:
                if entry.get("depth", 0) <= lineitems_depth:
                    break
                if entry.get("kind") != "table":
                    subtree.append(entry)

    lineitems = [e for e in subtree if e.get("kind") == "lineitems"]
    group = lineitems[0] if lineitems else None
    group_concept = group.get("concept", "") if group else ""
    group_label = preferred_display_label(
        group_concept,
        labels,
        group.get("preferredLabel", "") if group else "",
        xsd=xsd,
    ) if group_concept else "항목"

    rows = []
    for entry in subtree:
        if entry.get("kind") != "item":
            continue
        concept = entry.get("concept", "")
        preferred = (entry.get("preferredLabel") or "").strip()
        role_key = normalized_label_role_key(preferred)
        rows.append({
            "occurrence_id": entry.get("occurrence_id"),
            "occurrence_key": entry.get("occurrence_key"),
            "concept": concept,
            "parent": entry.get("parent"),
            "label": preferred_display_label(concept, labels, preferred, xsd=xsd),
            "preferredLabel": preferred,
            "preferredRoleKey": role_key,
            "depth": max(entry.get("depth", 1) - table_depth - 1, 0),
            "order": entry.get("order", 0),
            "sequence": entry.get("sequence", 0),
            "row_group": group_label,
            "row_group_concept": group_concept,
        })
    return rows

def rows_for_table(table, bundle, facts, labels, xsd, pre_table=None, pre_bundle=None):
    """
    하나의 실제 DEF 표에 사용할 행을 구성합니다.

    역할 분리:
    - DEF `table`: LineItems, Axis, Domain, Member 등 실제 표 구조
    - PRE `pre_table`: 행 순서, preferredLabel, 기초/기말 occurrence

    PRE Table은 새로운 표를 만들지 않습니다. 선택된 DEF Table의 행 정보만
    보완합니다.
    """
    def_rows = rows_from_lineitems(
        lineitems_for_table(table, bundle, xsd),
        bundle,
        facts,
        labels,
        xsd,
    )

    # DEF Table과 대응되는 PRE Table을 사용해 행 순서/별칭/기초·기말을 보완합니다.
    source_table = pre_table or table
    pre_rows = rows_from_pre_table(
        source_table,
        pre_bundle or bundle,
        facts,
        labels,
        xsd,
    )

    def_by_concept = {row["concept"]: dict(row) for row in def_rows}
    merged = []
    seen_occurrences = set()
    concepts_seen_in_pre = set()

    for pre_row in pre_rows:
        concept = pre_row["concept"]
        preferred = (pre_row.get("preferredLabel") or "").strip()
        role_key = normalized_label_role_key(preferred)
        occurrence_key = pre_row.get("occurrence_id") or (
            concept,
            role_key,
            pre_row.get("parent"),
            pre_row.get("order", 0),
            pre_row.get("sequence", 0),
        )

        if occurrence_key in seen_occurrences:
            continue

        # PRE에 나온 concept가 DEF LineItems에 없더라도 기초/기말 행으로 유지합니다.
        row = dict(def_by_concept.get(concept, {}))
        row.update(pre_row)
        row["preferredRoleKey"] = role_key
        row["label"] = preferred_display_label(
            concept,
            labels,
            preferred,
            xsd=xsd,
        )

        if concept in def_by_concept:
            row["row_group"] = (
                def_by_concept[concept].get("row_group")
                or pre_row.get("row_group")
                or "항목"
            )
            row["row_group_concept"] = (
                def_by_concept[concept].get("row_group_concept")
                or pre_row.get("row_group_concept", "")
            )

        merged.append(row)
        seen_occurrences.add(occurrence_key)
        concepts_seen_in_pre.add(concept)

    # PRE에 없는 DEF item은 DEF 순서대로 추가합니다.
    for def_row in def_rows:
        concept = def_row["concept"]

        if concept in concepts_seen_in_pre:
            continue

        row = dict(def_row)
        preferred = (row.get("preferredLabel") or "").strip()
        row["preferredRoleKey"] = normalized_label_role_key(preferred)
        row["label"] = preferred_display_label(
            concept,
            labels,
            preferred,
            xsd=xsd,
        )
        merged.append(row)

    return merged[:500]

def axis_specs(table, bundle, labels, xsd):
    """
    table에 연결된 axis/domain/default/member 구조를 def.xml arcrole별로 분리한다.
    """
    arcs = bundle.get("def", {}).get("arcs", [])
    dm = child_map(arcs, "domain-member")
    axes, seen_axes = [], set()

    # table과 직접 연결된 hypercube-dimension 우선
    for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
        if a.get("from") == table and "hypercube-dimension" in a.get("arcrole", ""):
            ax = a.get("to")
            if ax and ax not in seen_axes and concept_kind(ax, xsd) == "axis":
                axes.append({"axis": ax, "order": a.get("order", 0)})
                seen_axes.add(ax)

    # fallback: /all table과 같은 role 내 hypercube-dimension
    if not axes:
        for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
            if "hypercube-dimension" in a.get("arcrole", "") and concept_kind(a.get("to"), xsd) == "axis":
                ax = a.get("to")
                if ax and ax not in seen_axes:
                    axes.append({"axis": ax, "order": a.get("order", 0)})
                    seen_axes.add(ax)

    specs = []
    for ax_info in axes:
        ax = ax_info["axis"]
        ax_label = display_label(ax, labels)
        if is_report_scope_concept(ax, ax_label):
            continue

        defaults, domains = [], []
        for a in sorted(arcs, key=lambda x: (x.get("order", 0), x.get("to", ""))):
            if a.get("from") != ax:
                continue
            to = a.get("to")
            if not to:
                continue
            lab = display_label(to, labels)
            if is_report_scope_concept(to, lab):
                continue
            arcrole = a.get("arcrole", "")
            if "dimension-default" in arcrole:
                defaults.append({"concept": to, "label": lab, "order": a.get("order", 0)})
            elif "dimension-domain" in arcrole:
                domains.append({"concept": to, "label": lab, "order": a.get("order", 0)})

        specs.append({
            "axis": ax,
            "label": ax_label,
            "order": ax_info.get("order", 0),
            "defaults": defaults,
            "domains": domains,
            "dm": dm,
        })

    specs.sort(key=lambda x: x.get("order", 0))
    return specs

def member_leaf_paths(root, dm, labels, xsd, base_path=None, seen=None):
    """domain-member tree를 leaf path 목록으로 펼친다."""
    seen = seen or set()
    base_path = base_path or []
    if root in seen:
        return []
    seen.add(root)

    lab = display_label(root, labels)
    if is_report_scope_concept(root, lab):
        return []

    node = {"concept": root, "label": lab, "kind": concept_kind(root, xsd)}
    path = base_path + [node]
    children = [ch["concept"] for ch in dm.get(root, [])]
    children = [c for c in children if not is_report_scope_concept(c, display_label(c, labels))]

    if not children:
        return [{"path": path, "terminal": root, "label": lab}]

    out = []
    for ch in children:
        out.extend(member_leaf_paths(ch, dm, labels, xsd, path, seen.copy()))
    return out

def columns_for_axis(spec, labels, xsd):
    """하나의 axis에서 상세 구성요소를 먼저, 합계/default 열을 맨 오른쪽에 생성합니다."""
    axis = spec["axis"]
    axis_node = {"concept": axis, "label": spec["label"], "kind": "axis"}
    dm = spec.get("dm", {})
    cols = []
    seen = set()
    default_members = [d["concept"] for d in spec.get("defaults", [])]
    domains = sorted(spec.get("domains", []), key=lambda x: (x.get("order", 0), x.get("concept", "")))

    if not domains and default_members:
        for d in sorted(spec.get("defaults", []), key=lambda x: (x.get("order", 0), x.get("concept", ""))):
            key = f"total:{axis}:{d['concept']}"
            if key in seen:
                continue
            seen.add(key)
            cols.append({
                "label": "합계", "members": [], "criteria": {},
                "total_axes": {axis: [d["concept"]]}, "axis": axis,
                "path": [axis_node, {"concept": key, "label": f"{d['label']} [합계]", "kind": "total"}],
                "terminal": key, "is_total": True,
            })
        return cols

    for domain in domains:
        root = domain["concept"]
        root_label = domain["label"]
        root_node = {"concept": root, "label": root_label, "kind": concept_kind(root, xsd)}
        leaves = []
        for ch in [x["concept"] for x in dm.get(root, [])]:
            leaves.extend(member_leaf_paths(ch, dm, labels, xsd, [root_node]))

        # 상세 member를 definition order대로 먼저 배치합니다.
        for leaf in leaves:
            terminal = leaf["terminal"]
            if terminal in seen:
                continue
            seen.add(terminal)
            cols.append({
                "label": leaf["label"], "members": [terminal],
                "criteria": {axis: terminal}, "total_axes": {}, "axis": axis,
                "path": [axis_node] + leaf["path"], "terminal": terminal, "is_total": False,
            })

        # 각 domain의 합계/default 열은 상세 구성요소의 맨 오른쪽에 배치합니다.
        total_key = f"total:{axis}:{root}"
        if total_key not in seen:
            seen.add(total_key)
            allowed_defaults = list(dict.fromkeys([root] + default_members))
            total_label = "합계" if leaves or root in default_members else root_label
            cols.append({
                "label": total_label, "members": [], "criteria": {},
                "total_axes": {axis: allowed_defaults}, "axis": axis,
                "path": [axis_node, {"concept": total_key, "label": (root_label if "합계" in root_label else f"{root_label} [합계]"), "kind": "total"}],
                "terminal": total_key, "is_total": True,
            })
    return cols

def combine_axis_columns(axis_col_groups):
    """
    axis별 column 후보를 조합하여 전체 컬럼을 만듭니다.

    다중축 상위 합계 규칙:
    - 어떤 상위 axis에서 합계가 선택되면 하위 axis의 detail member 조합은 생성하지 않습니다.
    - 하위 axis는 합계 column만 선택합니다.
    - 결과적으로 상위 합계 header 아래에는 합계 값 column 하나만 남습니다.
    """
    if not axis_col_groups:
        return [{
            "label": "합계",
            "members": [],
            "criteria": {},
            "total_axes": {},
            "table_axes": [],
            "path": [{"label": "합계", "concept": "default", "kind": "total"}],
            "terminal": "default",
            "is_total": True,
        }]

    table_axes = [group["axis"] for group in axis_col_groups]
    groups = [group["cols"] for group in axis_col_groups if group.get("cols")]

    if not groups:
        return [{
            "label": "합계",
            "members": [],
            "criteria": {},
            "total_axes": {},
            "table_axes": [],
            "path": [{"label": "합계", "concept": "default", "kind": "total"}],
            "terminal": "default",
            "is_total": True,
        }]

    final = []
    seen = set()

    for combo in product(*groups):
        # 상위 axis에서 total이 나온 뒤에는 하위 axis도 total이어야 합니다.
        upper_total_seen = False
        valid_combo = True

        for column in combo:
            if upper_total_seen and not column.get("is_total"):
                valid_combo = False
                break

            if column.get("is_total"):
                upper_total_seen = True

        if not valid_combo:
            continue

        criteria = {}
        total_axes = {}
        members = []
        full_path = []
        display_path = []
        terminals = []
        bottom_labels = []
        first_total_found = False

        for column in combo:
            criteria.update(column.get("criteria") or {})

            for axis, values in (column.get("total_axes") or {}).items():
                total_axes.setdefault(axis, [])
                total_axes[axis].extend(values or [])
                total_axes[axis] = list(dict.fromkeys(total_axes[axis]))

            members.extend(column.get("members") or [])
            column_path = list(column.get("path") or [])
            full_path.extend(column_path)
            terminals.append(column.get("terminal", ""))
            bottom_labels.append(column.get("label", ""))

            # 화면 헤더는 최초 상위 합계까지만 표시합니다.
            if not first_total_found:
                display_path.extend(column_path)
                if column.get("is_total"):
                    first_total_found = True

        members = list(dict.fromkeys(member for member in members if member))

        key = (
            tuple(sorted(criteria.items())),
            tuple(
                (axis, tuple(values))
                for axis, values in sorted(total_axes.items())
            ),
        )

        if key in seen:
            continue
        seen.add(key)

        # 상위 합계 조합은 화면상 합계 값 column 하나로 표시합니다.
        if first_total_found:
            label = "합계"
        else:
            label = " / ".join(
                item for item in bottom_labels if item
            ) or "합계"

        final.append({
            "label": label,
            "members": members,
            "criteria": criteria,
            "total_axes": total_axes,
            "table_axes": table_axes,
            "path": display_path or full_path,
            "full_path": full_path,
            "terminal": " / ".join(
                item for item in terminals if item
            ),
            "is_total": len(criteria) == 0,
            "top_total_merged": first_total_found,
        })

        if len(final) >= 240:
            break

    return final

def columns_from_axes(specs, labels, xsd):
    groups = []
    for sp in specs:
        cols = columns_for_axis(sp, labels, xsd)
        if cols:
            groups.append({"axis": sp["axis"], "cols": cols})
    return combine_axis_columns(groups)

def header_rows(cols, labels=None, xsd=None):
    """짧은 합계 path는 rowspan, 공통 axis path는 colspan으로 병합한다."""
    if not cols: return []
    depth=max(len(c.get("path",[])) for c in cols)
    rows=[]
    for d in range(depth):
        row=[]; i=0
        while i<len(cols):
            path=cols[i].get("path",[])
            if d>=len(path):
                i+=1; continue
            node=path[d]; span=1; j=i+1
            while j<len(cols):
                p2=cols[j].get("path",[])
                if d>=len(p2): break
                same=True
                for k in range(d+1):
                    a=path[k].get("concept","") if k<len(path) else ""
                    bb=p2[k].get("concept","") if k<len(p2) else ""
                    if a!=bb: same=False; break
                if not same: break
                span+=1; j+=1
            concept=node.get("concept") or ""; label=node.get("label") or "-"
            terminal=(d==len(path)-1)
            rowspan=(depth-d) if terminal else 1
            row.append({"label":label,"colspan":span,"rowspan":rowspan,"concept":concept,"properties":concept_properties(concept,labels or {},xsd or {},kind=node.get("kind"),display_name=label) if concept and not str(concept).startswith("total:") and concept!="default" else None})
            i=j
        rows.append(row)
    return rows

def row_fact_period_key(period_key, preferred_label):
    """
    PRE preferredLabel로 기초/기말 Fact 기간을 결정합니다.

    당기 표:
      periodStartLabel -> 전기말(PY)
      periodEndLabel   -> 당기말(CY)

    전기 표:
      periodStartLabel -> 전전기말(PY2)
      periodEndLabel   -> 전기말(PY)
    """
    role_key = normalized_label_role_key(preferred_label)

    if role_key == "periodStartLabel":
        return {
            "CY": "PY",
            "PY": "PY2",
        }.get(period_key, period_key)

    # periodEndLabel 및 일반 label은 현재 표 기간 사용
    return period_key

def build_period_block(idx, rows, cols, period, scope, labels, xsd):
    """
    period별로 실제 값이 있는 컬럼만 남긴 후 rows/values/header를 생성한다.
    KOX와의 차이를 줄이기 위해 빈 Cartesian product 컬럼을 제거한다.
    """
    # KOX는 구조가 정의되어 있으면 값이 없는 열도 표시하므로 전체 구조 열을 유지합니다.
    # 다만 열이 전혀 정의되지 않은 경우에만 block을 생성하지 않습니다.
    active_cols = list(cols)
    if not active_cols:
        return None

    brows = []
    for r in rows:
        vals = []
        sample_fact = None
        for c in active_cols:
            f = find_fact_for_column(idx, r["concept"], row_fact_period_key(period["key"], r.get("preferredLabel", "")), c, scope)
            if f and sample_fact is None:
                sample_fact = f
            raw_value = f.get("formatted_value") or f.get("value") if f else ""
            inverted_value = apply_role_value_sign(raw_value, r.get("preferredLabel", ""))
            vals.append({
                "value": inverted_value,
                "is_numeric": f.get("is_numeric", False) if f else False,
            })
        # fact가 없어도 PRE/DEF 구조에 존재하는 item 행은 유지합니다.
        group_concept = r.get("row_group_concept", "")
        group_label = r.get("row_group") or "항목"
        brows.append({
                "concept": r.get("concept", ""),
                "occurrence_id": r.get("occurrence_id"),
                "preferredLabel": r.get("preferredLabel", ""),
                "preferredRoleKey": r.get("preferredRoleKey") or normalized_label_role_key(r.get("preferredLabel", "")),
                "row_group": group_label,
                "row_group_concept": group_concept,
                "row_group_properties": concept_properties(group_concept, labels, xsd, kind="lineitems", display_name=group_label) if group_concept else None,
                "label": r["label"],
                "depth": r.get("depth", 0),
                "properties": concept_properties(r.get("concept", ""), labels, xsd, fact=sample_fact, display_name=r["label"], preferred_label=r.get("preferredLabel", "")),
                "values": vals,
            })

    if not brows:
        return None

    return {
        "period_key": period["key"],
        "period_label": period["label"],
        "columns": active_cols,
        "header_rows": header_rows(active_cols, labels, xsd),
        "rows": brows,
    }




def build_context_values(
    doc,
    concept,
    bundle,
    facts,
    labels,
    xsd,
    stop_concepts=None,
    ordered_concepts=None,
):
    """
    문장영역/개요의 서술형 Text Fact만 수집합니다.

    ordered_concepts가 있으면 현재 PRE Table 직전 order window의 concept만
    사용하여 다른 표의 문장영역/개요/Text가 섞이지 않게 합니다.
    """
    stop = set(stop_concepts or [])
    preferred_map = preferred_label_map(bundle)

    def is_narrative(concept_name):
        kind = concept_kind(concept_name, xsd)
        label = display_label(
            concept_name,
            labels,
            "",
            xsd=xsd,
        )
        combined = f"{concept_name} {label}".lower()

        return (
            kind == "text"
            or "textblock" in combined
            or "explanatory" in combined
            or "narrative" in combined
            or "disclosuretext" in combined
            or "guidance" in combined
            or "explanation" in combined
            or "문장영역" in combined
        )

    if ordered_concepts is not None:
        candidates = [
            candidate
            for candidate in dict.fromkeys(
                ordered_concepts
            )
            if candidate
            and candidate not in stop
            and is_narrative(candidate)
        ]
    else:
        cm = child_map(
            bundle.get("pre", {}).get("arcs", [])
        )
        candidates = []
        seen_nodes = set()

        def collect(node, path):
            if (
                not node
                or node in path
                or node in stop
            ):
                return

            next_path = set(path)
            next_path.add(node)

            if (
                is_narrative(node)
                and node not in seen_nodes
            ):
                candidates.append(node)
                seen_nodes.add(node)

            for child in cm.get(node, []):
                child_concept = child.get("concept")

                if (
                    not child_concept
                    or child_concept in stop
                ):
                    continue

                child_kind = concept_kind(
                    child_concept,
                    xsd,
                )

                if child_kind in {
                    "table",
                    "axis",
                    "domain",
                    "member",
                    "lineitems",
                    "item",
                }:
                    continue

                collect(child_concept, next_path)

        collect(concept, set())

    items = []

    for candidate in candidates:
        candidate_facts = [
            fact
            for fact in facts
            if fact.get("concept") == candidate
            and fact.get("scope", "unknown")
            in {doc.get("scope"), "unknown"}
        ]

        values = []

        for period in note_period_columns():
            match = next(
                (
                    fact
                    for fact in candidate_facts
                    if fact.get("period_key")
                    == period["key"]
                ),
                None,
            )
            if match:
                values.append({
                    "period_label": period["label"],
                    "period_key": period["key"],
                    "value": match.get("value", ""),
                })

        if not values and candidate_facts:
            match = candidate_facts[0]
            values.append({
                "period_label": "",
                "period_key": match.get(
                    "period_key",
                    "",
                ),
                "value": match.get("value", ""),
            })

        preferred = preferred_map.get(candidate, "")
        title = preferred_display_label(
            candidate,
            labels,
            preferred,
            fallback=candidate,
            xsd=xsd,
        )

        items.append({
            "concept": candidate,
            "title": title,
            "values": values,
            "properties": concept_properties(
                candidate,
                labels,
                xsd,
                fact=(
                    candidate_facts[0]
                    if candidate_facts else None
                ),
                display_name=title,
                preferred_label=preferred,
            ),
        })

    return items

def definition_tables(bundle, xsd):
    """DEF의 /all 관계로 선언된 실제 표시용 Table만 반환합니다."""
    tables=[]
    seen=set()
    for arc in sorted(bundle.get("def",{}).get("arcs",[]), key=lambda x:(x.get("order",0),x.get("to",""))):
        concept=arc.get("to")
        if not concept or concept in seen:
            continue
        if is_table_arc(arc,xsd):
            tables.append(concept)
            seen.add(concept)
    return tables


def presentation_tables(bundle, xsd):
    """PRE에 존재하는 Table occurrence를 표시 순서대로 반환합니다."""
    result=[]
    seen=set()
    for node in pre_nodes(bundle):
        concept=node.get("concept")
        if not concept or concept in seen:
            continue
        if concept_kind(concept,xsd)=="table":
            result.append(concept)
            seen.add(concept)
    return result


def _table_match_text(concept, labels, xsd):
    label=display_label(concept,labels,"",xsd=xsd)
    text=f"{concept} {label}".lower()
    # 구조용 공통 단어를 제거하고 실제 주제어만 비교합니다.
    for token in (
        "table","표","abstract","개요","explanatory","문장영역",
        "disclosure","details","of","and","the","에관한","대한",
        "장부금액","금액",
    ):
        text=text.replace(token," ")
    return set(re.findall(r"[a-z0-9가-힣]+",text))


def choose_context_source_table(table, table_index, pre_tables, bundle, labels, xsd):
    """
    실제 DEF Table에 붙일 PRE context source를 선택합니다.

    우선순위:
    1. 동일 concept가 PRE에 존재
    2. DEF owner와 PRE Table의 Abstract parent가 동일
    3. concept/label 주제어 유사도
    4. 같은 순서의 PRE Table
    """
    if table in pre_tables:
        return table

    arcs=bundle.get("pre",{}).get("arcs",[])
    parents=pre_parent_map(bundle)
    owners={x.get("concept") for x in table_owner_concepts(table,bundle,xsd) if x.get("concept")}

    for candidate in pre_tables:
        candidate_parents={x.get("concept") for x in parents.get(candidate,[]) if x.get("concept")}
        if owners & candidate_parents:
            return candidate

    target_tokens=_table_match_text(table,labels,xsd)
    best=None
    best_score=0
    for candidate in pre_tables:
        candidate_tokens=_table_match_text(candidate,labels,xsd)
        union=target_tokens|candidate_tokens
        score=(len(target_tokens&candidate_tokens)/len(union)) if union else 0
        if score>best_score:
            best=candidate
            best_score=score
    if best is not None and best_score>0:
        return best

    if table_index < len(pre_tables):
        return pre_tables[table_index]
    if len(pre_tables)==1:
        return pre_tables[0]
    return table


def is_non_display_scope_table(concept, labels, xsd):
    """연결/별도 범위 지정용 구조 Table은 화면에서 제외합니다."""
    label=display_label(concept,labels,"",xsd=xsd)
    compact=re.sub(r"[^a-z0-9가-힣]","",f"{concept} {label}".lower())
    patterns=(
        "연결또는별도재무제표","연결및별도재무제표","연결별도재무제표",
        "consolidatedorseparatefinancialstatements",
        "consolidatedandseparatefinancialstatements",
        "consolidatedseparatefinancialstatements",
    )
    return any(pattern in compact for pattern in patterns)




def build_note_table(
    doc,
    uri,
    bundle,
    table,
    facts,
    labels,
    xsd,
    context_source_table=None,
    context_source_bundle=None,
    context_pre_table=None,
    context_role_uri=None,
    context_global_order=None,
):
    """
    0715 표 본체는 그대로 유지하고 PRE order로 연결된 문장영역/개요만 붙입니다.

    - 표 행/열/축/도메인/멤버/Fact: 기존 DEF bundle
    - 문장영역/개요: 대응 PRE Table 직전 order window
    """
    idx = fact_index(facts)
    local_pre_table = context_source_table or table

    rows = rows_for_table(
        table,
        bundle,
        facts,
        labels,
        xsd,
        pre_table=local_pre_table,
        pre_bundle=context_source_bundle,
    )

    cols = columns_from_axes(
        axis_specs(table, bundle, labels, xsd),
        labels,
        xsd,
    )

    blocks = []

    for period in note_period_columns():
        block = build_period_block(
            idx,
            rows,
            cols,
            period,
            doc["scope"],
            labels,
            xsd,
        )
        if block:
            blocks.append(block)

    pre_bundle = context_source_bundle
    pre_table = None
    context = {
        "path": [],
        "sentence": None,
        "overview": None,
        "score": 0,
        "table_order": 10**9,
        "sentence_concepts": [],
        "overview_concepts": [],
    }
    context_blocks = []

    if pre_bundle is not None and context_pre_table:
        pre_table = context_pre_table
        context = find_table_pre_context(
            pre_table,
            pre_bundle,
            labels,
            xsd,
        )
        preferred_map = preferred_label_map(
            pre_bundle
        )

        sentence = context.get("sentence")
        overview = context.get("overview")

        if sentence:
            sentence_preferred = preferred_map.get(
                sentence,
                "",
            )
            sentence_title = preferred_display_label(
                sentence,
                labels,
                sentence_preferred,
                fallback=sentence,
                xsd=xsd,
            )
            sentence_items = build_context_values(
                doc,
                sentence,
                pre_bundle,
                facts,
                labels,
                xsd,
                stop_concepts={
                    overview,
                    pre_table,
                },
                ordered_concepts=context.get(
                    "sentence_concepts",
                    [],
                ),
            )
            context_blocks.append({
                "type": "sentence_area",
                "concept": sentence,
                "title": sentence_title,
                "values": (
                    sentence_items[0]["values"]
                    if sentence_items else []
                ),
                "items": sentence_items,
                "properties": concept_properties(
                    sentence,
                    labels,
                    xsd,
                    display_name=sentence_title,
                    preferred_label=sentence_preferred,
                ),
            })

        if overview:
            overview_preferred = preferred_map.get(
                overview,
                "",
            )
            overview_title = preferred_display_label(
                overview,
                labels,
                overview_preferred,
                fallback=overview,
                xsd=xsd,
            )
            overview_items = build_context_values(
                doc,
                overview,
                pre_bundle,
                facts,
                labels,
                xsd,
                stop_concepts={pre_table},
                ordered_concepts=context.get(
                    "overview_concepts",
                    [],
                ),
            )
            context_blocks.append({
                "type": "overview",
                "concept": overview,
                "title": overview_title,
                "values": (
                    overview_items[0]["values"]
                    if overview_items else []
                ),
                "items": overview_items,
                "properties": concept_properties(
                    overview,
                    labels,
                    xsd,
                    display_name=overview_title,
                    preferred_label=overview_preferred,
                ),
            })

    local_preferred = preferred_label_map(
        bundle
    ).get(local_pre_table, "")

    sort_order = (
        context_global_order
        if context_global_order is not None
        else (10**9, 10**9)
    )

    return {
        "type": "note_table",
        "table_concept": table,
        "pre_table_concept": pre_table or "",
        "title": preferred_display_label(
            table,
            labels,
            local_preferred,
            fallback="표",
            xsd=xsd,
        ),
        "context_blocks": context_blocks,
        "pre_path": context.get("path", []),
        "period_blocks": blocks,
        "_pre_sort_order": sort_order,
        "diagnostics": {
            "engine_version": "0722-taxonomy-prefix-match-v7",
            "def_role_uri": uri,
            "def_table": table,
            "context_role_uri": (
                context_role_uri
                if pre_bundle else ""
            ),
            "context_pre_table": pre_table or "",
            "context_path": context.get(
                "path",
                [],
            ),
            "context_table_order": context.get(
                "table_order",
                10**9,
            ),
            "context_blocks_count": len(
                context_blocks
            ),
            "sentence_concepts": context.get(
                "sentence_concepts",
                [],
            ),
            "overview_concepts": context.get(
                "overview_concepts",
                [],
            ),
        },
    }

def build_text_section(doc, concept, facts, labels, periods=None):
    """TextBlock/Explanatory concept를 설명 section으로 구성한다."""
    idx = fact_index(facts)
    vals = []
    periods = periods or note_period_columns()
    for p in periods:
        f = find_fact(idx, concept, p["key"], [], doc["scope"])
        if f:
            vals.append({"period_label": p["label"], "value": f.get("value", "")})
    return {"type": "text", "title": display_label(concept, labels, "설명"), "values": vals} if vals else None





def build_note_sections(
    doc,
    uri,
    bundle,
    facts,
    labels,
    xsd,
    pre_context_candidates=None,
    used_pre_contexts=None,
):
    """
    실제 표는 해당 role의 DEF 구조로 0715와 동일하게 생성합니다.
    각 DEF Table에는 PRE order상 대응되는 context 하나만 붙입니다.
    """
    sections = []
    candidates = list(pre_context_candidates or [])
    used = (
        used_pre_contexts
        if used_pre_contexts is not None
        else set()
    )

    def_tables = [
        table
        for table in definition_tables(bundle, xsd)
        if not is_non_display_scope_table(
            table,
            labels,
            xsd,
        )
    ]

    local_pre_tables = [
        table
        for table in presentation_tables(bundle, xsd)
        if not is_non_display_scope_table(
            table,
            labels,
            xsd,
        )
    ]

    if not def_tables:
        return sections

    seen_def_tables = set()

    for index, table in enumerate(def_tables):
        if table in seen_def_tables:
            continue
        seen_def_tables.add(table)

        local_pre_table = choose_context_source_table(
            table,
            index,
            local_pre_tables,
            bundle,
            labels,
            xsd,
        )

        context_candidate = (
            choose_pre_context_candidate(
                table,
                index,
                bundle,
                candidates,
                used,
                facts,
                labels,
                xsd,
            )
        )

        section = build_note_table(
            doc,
            uri,
            bundle,
            table,
            facts,
            labels,
            xsd,
            context_source_table=local_pre_table,
            context_source_bundle=(
                context_candidate["bundle"]
                if context_candidate else None
            ),
            context_pre_table=(
                context_candidate["table"]
                if context_candidate else None
            ),
            context_role_uri=(
                context_candidate["uri"]
                if context_candidate else None
            ),
            context_global_order=(
                context_candidate["global_order"]
                if context_candidate else None
            ),
        )

        axis_columns = columns_from_axes(
            axis_specs(
                table,
                bundle,
                labels,
                xsd,
            ),
            labels,
            xsd,
        )
        table_rows = rows_for_table(
            table,
            bundle,
            facts,
            labels,
            xsd,
            pre_table=local_pre_table,
        )

        if (
            section.get("period_blocks")
            or axis_columns
            or table_rows
        ):
            sections.append(section)

    return sections


def build_role_documents(grouped, facts, labels, xsd):
    docs = {}

    for base, doc in grouped.items():
        out = {
            "role_id": base,
            "display_title": doc["display_title"],
            "group": doc["group"],
            "scope": doc["scope"],
            "is_body": doc["is_body"],
            "sections": [],
        }

        if doc["is_body"]:
            section = build_body_section(
                doc,
                facts,
                labels,
                xsd,
            )
            if section.get("rows"):
                out["sections"].append(section)
        else:
            pre_candidates = collect_pre_table_candidates(
                doc["roles"],
                xsd,
            )
            used_pre_contexts = set()
            note_sections = []

            for role_sequence, (uri, bundle) in enumerate(
                doc["roles"]
            ):
                role_sections = build_note_sections(
                    doc,
                    uri,
                    bundle,
                    facts,
                    labels,
                    xsd,
                    pre_context_candidates=pre_candidates,
                    used_pre_contexts=used_pre_contexts,
                )

                for local_sequence, section in enumerate(
                    role_sections
                ):
                    section["_def_fallback_order"] = (
                        role_sequence,
                        local_sequence,
                    )
                    note_sections.append(section)

            # PRE Table order가 있는 표는 그 순서대로 배치합니다.
            # 매칭되지 않은 표는 기존 DEF 순서를 fallback으로 유지합니다.
            note_sections.sort(
                key=lambda section: (
                    0
                    if section.get("_pre_sort_order")
                    != (10**9, 10**9)
                    else 1,
                    section.get(
                        "_pre_sort_order",
                        (10**9, 10**9),
                    ),
                    section.get(
                        "_def_fallback_order",
                        (10**9, 10**9),
                    ),
                )
            )

            for section in note_sections:
                section.pop(
                    "_pre_sort_order",
                    None,
                )
                section.pop(
                    "_def_fallback_order",
                    None,
                )

            out["sections"].extend(note_sections)

        if out["sections"]:
            docs[base] = out

    return docs

def build_menu(docs):
    grouped = defaultdict(list)
    for rid, doc in docs.items():
        grouped[doc["group"]].append({"role_id": rid, "title": doc["display_title"]})
    order = ["연결재무제표 본문", "연결재무제표 주석", "별도재무제표 본문", "별도재무제표 주석"]
    return [{"group": g, "items": sorted(grouped.get(g, []), key=lambda x: role_sort_key(x["role_id"], x["title"]))} for g in order]


# ======================================================
# Flask routes
# ======================================================
