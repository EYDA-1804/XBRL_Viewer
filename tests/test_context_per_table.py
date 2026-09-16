
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


class ContextPerTableTest(unittest.TestCase):
    def test_context_is_one_to_one_and_table_stays_def_based(self):
        labels = {}
        xsd = {}

        concepts = {
            "SentenceA": ("text", "dart_SentenceA", "A 문장영역"),
            "OverviewA": ("abstract", "dart_OverviewA", "A 개요"),
            "TableA": ("table", "dart_TableA", "A 표"),
            "TextA": ("text", "dart_TextA", "A 설명"),
            "LineA": ("lineitems", "dart_LineA", "A 항목"),
            "ItemA": ("item", "ifrs-full_ItemA", "A 금액"),
            "AxisA": ("axis", "dart_AxisA", "A 축"),
            "DomainA": ("domain", "dart_DomainA", "A 도메인"),
            "MemberA": ("member", "dart_MemberA", "A 멤버"),
            "OwnerA": ("abstract", "dart_OwnerA", "A owner"),
            "SentenceB": ("text", "dart_SentenceB", "B 문장영역"),
            "OverviewB": ("abstract", "dart_OverviewB", "B 개요"),
            "TableB": ("table", "dart_TableB", "B 표"),
            "TextB": ("text", "dart_TextB", "B 설명"),
            "LineB": ("lineitems", "dart_LineB", "B 항목"),
            "ItemB": ("item", "ifrs-full_ItemB", "B 금액"),
            "AxisB": ("axis", "dart_AxisB", "B 축"),
            "DomainB": ("domain", "dart_DomainB", "B 도메인"),
            "MemberB": ("member", "dart_MemberB", "B 멤버"),
            "OwnerB": ("abstract", "dart_OwnerB", "B owner"),
        }

        for concept, (kind, full_id, ko) in concepts.items():
            xsd[concept] = meta(kind, full_id)
            labels[concept] = {
                "ko": {"label": ko},
                "en": {"label": concept},
                "_default": ko,
            }

        pre_a = {
            "role_uri": "pre-a",
            "pre": {"arcs": [
                {"from": "SentenceA", "to": "OverviewA", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "OverviewA", "to": "TextA", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "OverviewA", "to": "TableA", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "TableA", "to": "LineA", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "LineA", "to": "ItemA", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                # context 영역에 들어가면 안 되는 구조 concept
                {"from": "OverviewA", "to": "AxisA", "order": 3, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "OverviewA", "to": "ItemA", "order": 4, "arcrole": "parent-child", "preferredLabel": ""},
            ]},
            "def": {"arcs": []},
        }

        pre_b = {
            "role_uri": "pre-b",
            "pre": {"arcs": [
                {"from": "SentenceB", "to": "OverviewB", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "OverviewB", "to": "TextB", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "OverviewB", "to": "TableB", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "TableB", "to": "LineB", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                {"from": "LineB", "to": "ItemB", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
            ]},
            "def": {"arcs": []},
        }

        def_a = {
            "role_uri": "def-a",
            "pre": {"arcs": []},
            "def": {"arcs": [
                {"from": "OwnerA", "to": "TableA", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/all", "preferredLabel": ""},
                {"from": "TableA", "to": "AxisA", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/hypercube-dimension", "preferredLabel": ""},
                {"from": "AxisA", "to": "DomainA", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/dimension-domain", "preferredLabel": ""},
                {"from": "DomainA", "to": "MemberA", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                {"from": "OwnerA", "to": "LineA", "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                {"from": "LineA", "to": "ItemA", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
            ]},
        }

        def_b = {
            "role_uri": "def-b",
            "pre": {"arcs": []},
            "def": {"arcs": [
                {"from": "OwnerB", "to": "TableB", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/all", "preferredLabel": ""},
                {"from": "TableB", "to": "AxisB", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/hypercube-dimension", "preferredLabel": ""},
                {"from": "AxisB", "to": "DomainB", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/dimension-domain", "preferredLabel": ""},
                {"from": "DomainB", "to": "MemberB", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                {"from": "OwnerB", "to": "LineB", "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                {"from": "LineB", "to": "ItemB", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
            ]},
        }

        grouped = {
            "D100": {
                "display_title": "테스트 주석",
                "group": "연결재무제표 주석",
                "scope": "CFS",
                "is_body": False,
                "roles": [
                    ("pre-a", pre_a),
                    ("pre-b", pre_b),
                    ("def-a", def_a),
                    ("def-b", def_b),
                ],
            }
        }

        facts = [
            {"concept": "TextA", "period_key": "OTHER", "value": "A 서술", "formatted_value": "A 서술", "is_numeric": False, "scope": "CFS", "dimension_map": {}, "member_set": set()},
            {"concept": "TextB", "period_key": "OTHER", "value": "B 서술", "formatted_value": "B 서술", "is_numeric": False, "scope": "CFS", "dimension_map": {}, "member_set": set()},
            {"concept": "ItemA", "period_key": "CY", "value": "10", "formatted_value": "10", "is_numeric": True, "scope": "CFS", "dimension_map": {"AxisA": "MemberA"}, "member_set": {"MemberA"}},
            {"concept": "ItemB", "period_key": "CY", "value": "20", "formatted_value": "20", "is_numeric": True, "scope": "CFS", "dimension_map": {"AxisB": "MemberB"}, "member_set": {"MemberB"}},
        ]

        docs = build_role_documents(grouped, facts, labels, xsd)
        sections = docs["D100"]["sections"]

        self.assertEqual(len(sections), 2)
        by_table = {section["table_concept"]: section for section in sections}

        a = by_table["TableA"]
        b = by_table["TableB"]

        self.assertEqual(a["pre_table_concept"], "TableA")
        self.assertEqual(b["pre_table_concept"], "TableB")
        self.assertEqual([x["type"] for x in a["context_blocks"]], ["sentence_area", "overview"])
        self.assertEqual([x["type"] for x in b["context_blocks"]], ["sentence_area", "overview"])

        self.assertIn("SentenceA", a["pre_path"])
        self.assertNotIn("SentenceB", a["pre_path"])
        self.assertIn("SentenceB", b["pre_path"])
        self.assertNotIn("SentenceA", b["pre_path"])

        a_context_concepts = {
            item["concept"]
            for block in a["context_blocks"]
            for item in block.get("items", [])
        }
        self.assertIn("TextA", a_context_concepts)
        self.assertNotIn("ItemA", a_context_concepts)
        self.assertNotIn("AxisA", a_context_concepts)

        # 표 본체는 DEF 기반 0715 구조
        a_block = a["period_blocks"][0]
        self.assertEqual(a_block["columns"][0]["criteria"], {"AxisA": "MemberA"})
        self.assertEqual([row["concept"] for row in a_block["rows"]], ["ItemA"])


if __name__ == "__main__":
    unittest.main()
