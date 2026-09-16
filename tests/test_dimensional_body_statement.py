
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
        "periodType": "duration" if kind == "item" else "",
        "balance": "",
    }


class DimensionalBodyStatementTest(unittest.TestCase):
    def test_equity_statement_uses_dimensional_table_builder(self):
        labels = {}
        xsd = {}

        concepts = {
            "EquitySentence": ("text", "dart_EquitySentence", "자본변동표 문장영역"),
            "EquityOverview": ("abstract", "dart_EquityOverview", "자본변동표 개요"),
            "EquityTable": ("table", "dart_EquityTable", "자본변동표"),
            "EquityLineItems": ("lineitems", "dart_EquityLineItems", "자본변동표 항목"),
            "ChangesInEquity": ("item", "ifrs-full_ChangesInEquity", "자본 변동"),
            "ComponentsOfEquityAxis": ("axis", "ifrs-full_ComponentsOfEquityAxis", "자본 구성요소 [축]"),
            "ComponentsOfEquityDomain": ("domain", "ifrs-full_ComponentsOfEquityDomain", "자본 구성요소 [도메인]"),
            "RetainedEarningsMember": ("member", "ifrs-full_RetainedEarningsMember", "이익잉여금"),
            "EquityOwner": ("abstract", "dart_EquityOwner", "자본변동표 owner"),
        }

        for concept, (kind, full_id, ko_label) in concepts.items():
            xsd[concept] = meta(kind, full_id)
            labels[concept] = {
                "ko": {"label": ko_label},
                "en": {"label": concept},
                "_default": ko_label,
            }

        pre_bundle = {
            "role_uri": "pre-equity",
            "pre": {
                "arcs": [
                    {"from": "EquitySentence", "to": "EquityOverview", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "EquityOverview", "to": "EquityTable", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "EquityTable", "to": "EquityLineItems", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "EquityLineItems", "to": "ChangesInEquity", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                ]
            },
            "def": {"arcs": []},
        }

        def_bundle = {
            "role_uri": "def-equity",
            "pre": {"arcs": []},
            "def": {
                "arcs": [
                    {"from": "EquityOwner", "to": "EquityTable", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/all", "preferredLabel": ""},
                    {"from": "EquityTable", "to": "ComponentsOfEquityAxis", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/hypercube-dimension", "preferredLabel": ""},
                    {"from": "ComponentsOfEquityAxis", "to": "ComponentsOfEquityDomain", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/dimension-domain", "preferredLabel": ""},
                    {"from": "ComponentsOfEquityDomain", "to": "RetainedEarningsMember", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    {"from": "EquityOwner", "to": "EquityLineItems", "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    {"from": "EquityLineItems", "to": "ChangesInEquity", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                ]
            },
        }

        grouped = {
            "B210000": {
                "display_title": "자본변동표",
                "group": "연결재무제표",
                "scope": "CFS",
                "is_body": True,
                "roles": [
                    ("pre-equity", pre_bundle),
                    ("def-equity", def_bundle),
                ],
            }
        }

        facts = [
            {
                "concept": "ChangesInEquity",
                "period_key": "CY",
                "value": "100",
                "formatted_value": "100",
                "is_numeric": True,
                "scope": "CFS",
                "dimension_map": {
                    "ComponentsOfEquityAxis": "RetainedEarningsMember"
                },
                "member_set": {"RetainedEarningsMember"},
                "unit": "KRW",
                "decimals": "-3",
            }
        ]

        documents = build_role_documents(
            grouped,
            facts,
            labels,
            xsd,
        )

        section = documents["B210000"]["sections"][0]

        self.assertEqual(section["type"], "note_table")
        self.assertEqual(section["table_concept"], "EquityTable")
        self.assertEqual(
            section["period_blocks"][0]["columns"][0]["criteria"],
            {
                "ComponentsOfEquityAxis":
                "RetainedEarningsMember"
            },
        )
        self.assertEqual(
            section["period_blocks"][0]["rows"][0]["concept"],
            "ChangesInEquity",
        )


if __name__ == "__main__":
    unittest.main()
