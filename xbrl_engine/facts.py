from collections import defaultdict
from .utils import *

def fact_index(facts):
    idx = defaultdict(list)
    for f in facts:
        idx[(f["concept"], f["period_key"])].append(f)
    return idx


def find_fact(idx, concept, period_key, required_members=None, wanted_scope=None):
    """
    기존 호환용 fact 매칭 함수.
    본문 재무제표처럼 dimension 컬럼이 없는 경우 사용한다.
    주석 표는 아래 find_fact_for_column()을 사용해 dimension_map 기준으로 더 정확히 매칭한다.
    """
    required = set(required_members or [])
    candidates = idx.get((concept, period_key), [])
    matched = []

    for f in candidates:
        members = set(f.get("member_set", set()))

        if required and not required.issubset(members):
            continue

        fs = f.get("scope", "unknown")

        if wanted_scope and fs not in {wanted_scope, "unknown"}:
            continue

        rank_scope = 0 if fs == wanted_scope else 1
        extra_members = len(members - required)

        matched.append((rank_scope, extra_members, len(members), f))

    if not matched:
        return None

    matched.sort(key=lambda x: (x[0], x[1], x[2]))
    return matched[0][3]


def find_fact_for_column(idx, concept, period_key, col, wanted_scope=None):
    """
    KOX식 주석 표 셀 매칭 함수.

    핵심 차이:
    - 기존 member_set subset 매칭은 너무 느슨해서 값이 여러 합계/구성요소 컬럼에 반복될 수 있다.
    - 이 함수는 context의 dimension_map(axis -> member)을 기준으로 정확히 매칭한다.

    col 구조:
    - criteria: {axis: member}
      해당 axis가 정확히 해당 member여야 한다.
    - total_axes: {axis: [default_or_domain_member, ...]}
      해당 axis는 detail member가 없어야 하거나, default/domain member일 때만 매칭한다.
    - table_axes: 현재 표에서 사용하는 전체 axis 목록
      이 axis들 중 criteria/total_axes에 맞지 않는 다른 member가 있으면 제외한다.
    """
    candidates = idx.get((concept, period_key), [])
    criteria = dict(col.get("criteria") or {})
    total_axes = dict(col.get("total_axes") or {})
    table_axes = list(col.get("table_axes") or [])
    matched = []

    for f in candidates:
        fs = f.get("scope", "unknown")
        if wanted_scope and fs not in {wanted_scope, "unknown"}:
            continue

        dmap = dict(f.get("dimension_map") or {})

        ok = True

        # 1) detail axis는 정확히 해당 member여야 한다.
        for axis, member in criteria.items():
            if dmap.get(axis) != member:
                ok = False
                break

        if not ok:
            continue

        # 2) total/default axis는 detail member가 있으면 안 된다.
        #    단, dimension-default/domain member 자체가 explicit하게 들어온 경우는 허용한다.
        for axis, allowed_defaults in total_axes.items():
            actual = dmap.get(axis)
            allowed = set(allowed_defaults or [])
            if actual and allowed and actual not in allowed:
                ok = False
                break
            if actual and not allowed:
                ok = False
                break

        if not ok:
            continue

        # 3) 이 표의 다른 axis에 예상하지 않은 member가 들어 있으면 제외한다.
        for axis in table_axes:
            if axis in criteria or axis in total_axes:
                continue
            if axis in dmap:
                ok = False
                break

        if not ok:
            continue

        # 4) score: scope 정확도, 불필요한 dimension 수가 적은 fact 우선
        expected_axes = set(criteria) | set(total_axes)
        extra_axes = len([a for a in dmap if a in table_axes and a not in expected_axes])
        rank_scope = 0 if fs == wanted_scope else 1
        matched.append((rank_scope, extra_axes, len(dmap), f))

    if not matched:
        return None

    matched.sort(key=lambda x: (x[0], x[1], x[2]))
    return matched[0][3]


def column_has_fact(idx, rows, col, period_key, scope):
    """period별 컬럼 pruning을 위해 해당 컬럼에 값이 하나라도 있는지 확인한다."""
    for r in rows:
        if find_fact_for_column(idx, r["concept"], period_key, col, scope):
            return True
    return False


def period_columns():
    """
    본문 재무제표용 기간 컬럼.
    본문은 당기/전기/전전기까지 필요하다.
    """
    return [
        {"key": "CY", "label": "당기"},
        {"key": "PY", "label": "전기"},
        {"key": "PY2", "label": "전전기"}
    ]


def note_period_columns():
    """
    주석 표용 기간 컬럼.
    주석은 당기/전기만 렌더링한다.
    전전기 표가 본문과 링크되거나 불필요하게 나타나는 문제를 방지한다.
    """
    return [
        {"key": "CY", "label": "당기"},
        {"key": "PY", "label": "전기"}
    ]


# ======================================================
# Body statement
# ======================================================