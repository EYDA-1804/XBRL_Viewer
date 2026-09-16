
import unittest

from xbrl_engine.builders import build_role_documents


def meta(kind, full_id):
    return {
        "kind": kind,
        "full_id": full_id,
        "id": full_id,
        "name": full_id.split("_", 1)[-1],
        "prefix": full_id.split("_", 1)[0],
        "aliases": [full_id],
        "type": "xbrli:monetaryItemType" if kind == "item" else "",
        "periodType": "instant" if kind == "item" else "",
        "balance": "",
    }


class PreOrderContextTest(unittest.TestCase):
    def test_sibling_order_pairs_context_and_sorts_tables(self):
        concepts = {
            "Root": ("abstract", "dart_Root", "주석 루트"),
            "SentenceA": ("text", "dart_SentenceA", "A 문장영역"),
            "OverviewA": ("abstract", "dart_OverviewA", "A 개요"),
            "TextA": ("text", "dart_TextA", "A 설명"),
            "TableA": ("table", "dart_TableA", "A 표"),
            "SentenceB": ("text", "dart_SentenceB", "B 문장영역"),
            "OverviewB": ("abstract", "dart_OverviewB", "B 개요"),
            "TextB": ("text", "dart_TextB", "B 설명"),
            "TableB": ("table", "dart_TableB", "B 표"),
            "OwnerA": ("abstract", "dart_OwnerA", "A owner"),
            "LineA": ("lineitems", "dart_LineA", "A 항목"),
            "ItemA": ("item", "ifrs-full_ItemA", "A 금액"),
            "AxisA": ("axis", "dart_AxisA", "A 축"),
            "DomainA": ("domain", "dart_DomainA", "A 도메인"),
            "MemberA": ("member", "dart_MemberA", "A 멤버"),
            "OwnerB": ("abstract", "dart_OwnerB", "B owner"),
            "LineB": ("lineitems", "dart_LineB", "B 항목"),
            "ItemB": ("item", "ifrs-full_ItemB", "B 금액"),
            "AxisB": ("axis", "dart_AxisB", "B 축"),
            "DomainB": ("domain", "dart_DomainB", "B 도메인"),
            "MemberB": ("member", "dart_MemberB", "B 멤버"),
        }

        labels = {}
        xsd = {}

        for concept, (kind, full_id, ko_label) in concepts.items():
            xsd[concept] = meta(kind, full_id)
            labels[concept] = {
                "ko": {"label": ko_label},
                "en": {"label": concept},
                "_default": ko_label,
            }

        # 문장영역/개요/Table이 부모-자식이 아니라 PRE order로 나열된 사례
        pre_bundle = {
            "role_uri": "pre-main",
            "pre": {
                "arcs": [
                    {"from": "Root", "to": "SentenceA", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "OverviewA", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "TextA", "order": 2.5, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "TableA", "order": 3, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "SentenceB", "order": 4, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "OverviewB", "order": 5, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "TextB", "order": 5.5, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "Root", "to": "TableB", "order": 6, "arcrole": "parent-child", "preferredLabel": ""},
                ]
            },
            "def": {"arcs": []},
        }

        def def_bundle(table, owner, line, item, axis, domain, member):
            return {
                "role_uri": f"def-{table}",
                "pre": {"arcs": []},
                "def": {
                    "arcs": [
                        {"from": owner, "to": table, "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/all", "preferredLabel": ""},
                        {"from": table, "to": axis, "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/hypercube-dimension", "preferredLabel": ""},
                        {"from": axis, "to": domain, "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/dimension-domain", "preferredLabel": ""},
                        {"from": domain, "to": member, "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                        {"from": owner, "to": line, "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                        {"from": line, "to": item, "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    ]
                },
            }

        def_b = def_bundle(
            "TableB", "OwnerB", "LineB", "ItemB",
            "AxisB", "DomainB", "MemberB",
        )
        def_a = def_bundle(
            "TableA", "OwnerA", "LineA", "ItemA",
            "AxisA", "DomainA", "MemberA",
        )

        # DEF role은 일부러 B -> A 순서. 최종 화면은 PRE order A -> B여야 함.
        grouped = {
            "D100": {
                "display_title": "테스트 주석",
                "group": "연결재무제표 주석",
                "scope": "CFS",
                "is_body": False,
                "roles": [
                    ("pre-main", pre_bundle),
                    ("def-b", def_b),
                    ("def-a", def_a),
                ],
            }
        }

        facts = [
            {"concept": "TextA", "period_key": "OTHER", "value": "A 서술", "formatted_value": "A 서술", "is_numeric": False, "scope": "CFS", "dimension_map": {}, "member_set": set()},
            {"concept": "TextB", "period_key": "OTHER", "value": "B 서술", "formatted_value": "B 서술", "is_numeric": False, "scope": "CFS", "dimension_map": {}, "member_set": set()},
            {"concept": "ItemA", "period_key": "CY", "value": "10", "formatted_value": "10", "is_numeric": True, "scope": "CFS", "dimension_map": {"AxisA": "MemberA"}, "member_set": {"MemberA"}},
            {"concept": "ItemB", "period_key": "CY", "value": "20", "formatted_value": "20", "is_numeric": True, "scope": "CFS", "dimension_map": {"AxisB": "MemberB"}, "member_set": {"MemberB"}},
        ]

        documents = build_role_documents(
            grouped,
            facts,
            labels,
            xsd,
        )
        sections = documents["D100"]["sections"]

        self.assertEqual(
            [section["table_concept"] for section in sections],
            ["TableA", "TableB"],
        )

        first, second = sections

        self.assertEqual(
            [block["concept"] for block in first["context_blocks"]],
            ["SentenceA", "OverviewA"],
        )
        self.assertEqual(
            [block["concept"] for block in second["context_blocks"]],
            ["SentenceB", "OverviewB"],
        )

        first_context_items = {
            item["concept"]
            for block in first["context_blocks"]
            for item in block.get("items", [])
        }
        second_context_items = {
            item["concept"]
            for block in second["context_blocks"]
            for item in block.get("items", [])
        }

        self.assertIn("TextA", first_context_items)
        self.assertNotIn("TextB", first_context_items)
        self.assertIn("TextB", second_context_items)
        self.assertNotIn("TextA", second_context_items)

        # 각 표의 기존 DEF 열/행 구조 유지
        self.assertEqual(
            first["period_blocks"][0]["columns"][0]["criteria"],
            {"AxisA": "MemberA"},
        )
        self.assertEqual(
            first["period_blocks"][0]["rows"][0]["concept"],
            "ItemA",
        )


if __name__ == "__main__":
    unittest.main()
