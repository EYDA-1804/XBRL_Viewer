
import unittest

from xbrl_engine.builders import build_role_documents


class KoxOccurrenceTest(unittest.TestCase):
    def test_split_pre_def_roles_are_merged(self):
        labels = {
            "DisclosureOfPropertyPlantAndEquipmentExplanatory": {
                "ko": {"label": "유형자산에 대한 세부 정보 공시 [문장영역]"},
                "en": {"label": "Property plant and equipment explanatory"},
                "_default": "유형자산에 대한 세부 정보 공시 [문장영역]",
            },
            "DisclosureOfPropertyPlantAndEquipmentAbstract": {
                "ko": {"label": "유형자산에 대한 세부 정보 공시 [개요]"},
                "en": {"label": "Property plant and equipment overview"},
                "_default": "유형자산에 대한 세부 정보 공시 [개요]",
            },
            "DisclosureOfPropertyPlantAndEquipmentTable": {
                "ko": {"label": "유형자산에 대한 세부 정보 공시 [표]"},
                "en": {"label": "Property plant and equipment table"},
                "_default": "유형자산에 대한 세부 정보 공시 [표]",
            },
            "PropertyPlantAndEquipmentLineItems": {
                "ko": {"label": "유형자산에 대한 세부 정보 공시 [항목]"},
                "en": {"label": "Property plant and equipment line items"},
                "_default": "유형자산에 대한 세부 정보 공시 [항목]",
            },
            "PropertyPlantAndEquipment": {
                "ko": {
                    "label": "유형자산",
                    "periodStartLabel": "기초 유형자산",
                    "periodEndLabel": "기말 유형자산",
                },
                "en": {
                    "label": "Property, plant and equipment",
                    "periodStartLabel": "Property, plant and equipment at beginning",
                    "periodEndLabel": "Property, plant and equipment at end",
                },
                "_default": "유형자산",
            },
            "Acquisitions": {
                "ko": {"label": "취득"},
                "en": {"label": "Acquisitions"},
                "_default": "취득",
            },
            "ClassesOfPropertyPlantAndEquipmentAxis": {
                "ko": {"label": "유형자산의 분류 [축]"},
                "en": {"label": "Classes of property plant and equipment axis"},
                "_default": "유형자산의 분류 [축]",
            },
            "PropertyPlantAndEquipmentDomain": {
                "ko": {"label": "유형자산 [구성요소]"},
                "en": {"label": "Property plant and equipment domain"},
                "_default": "유형자산 [구성요소]",
            },
            "LandMember": {
                "ko": {"label": "토지"},
                "en": {"label": "Land"},
                "_default": "토지",
            },
        }

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
                "balance": "debit" if kind == "item" else "",
            }

        xsd = {
            "DisclosureOfPropertyPlantAndEquipmentExplanatory": meta("text", "dart_DisclosureOfPropertyPlantAndEquipmentExplanatory"),
            "DisclosureOfPropertyPlantAndEquipmentAbstract": meta("abstract", "dart_DisclosureOfPropertyPlantAndEquipmentAbstract"),
            "DisclosureOfPropertyPlantAndEquipmentTable": meta("table", "dart_DisclosureOfPropertyPlantAndEquipmentTable"),
            "PropertyPlantAndEquipmentLineItems": meta("lineitems", "dart_PropertyPlantAndEquipmentLineItems"),
            "PropertyPlantAndEquipment": meta("item", "ifrs-full_PropertyPlantAndEquipment"),
            "Acquisitions": meta("item", "ifrs-full_Acquisitions"),
            "ClassesOfPropertyPlantAndEquipmentAxis": meta("axis", "dart_ClassesOfPropertyPlantAndEquipmentAxis"),
            "PropertyPlantAndEquipmentDomain": meta("domain", "dart_PropertyPlantAndEquipmentDomain"),
            "LandMember": meta("member", "dart_LandMember"),
            "PropertyPlantAndEquipmentOwnerAbstract": meta("abstract", "dart_PropertyPlantAndEquipmentOwnerAbstract"),
        }

        pre_bundle = {
            "role_uri": "role-pre",
            "role_code": "D100100a",
            "role_base": "D100100",
            "role_suffix": "a",
            "display_title": "유형자산",
            "pre": {
                "arcs": [
                    {"from": "DisclosureOfPropertyPlantAndEquipmentExplanatory", "to": "DisclosureOfPropertyPlantAndEquipmentAbstract", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "DisclosureOfPropertyPlantAndEquipmentAbstract", "to": "DisclosureOfPropertyPlantAndEquipmentTable", "order": 1, "arcrole": "parent-child", "preferredLabel": ""},
                    # Real DART PRE commonly places Table and LineItems as
                    # siblings below the same Abstract.
                    {"from": "DisclosureOfPropertyPlantAndEquipmentAbstract", "to": "PropertyPlantAndEquipmentLineItems", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentLineItems", "to": "PropertyPlantAndEquipment", "order": 1, "arcrole": "parent-child", "preferredLabel": "http://www.xbrl.org/2003/role/periodStartLabel", "to_full_id": "ifrs-full_PropertyPlantAndEquipment"},
                    {"from": "PropertyPlantAndEquipmentLineItems", "to": "Acquisitions", "order": 2, "arcrole": "parent-child", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentLineItems", "to": "PropertyPlantAndEquipment", "order": 3, "arcrole": "parent-child", "preferredLabel": "http://www.xbrl.org/2003/role/periodEndLabel", "to_full_id": "ifrs-full_PropertyPlantAndEquipment"},
                ]
            },
            "def": {"arcs": []},
        }

        def_bundle = {
            "role_uri": "role-def",
            "role_code": "D100100b",
            "role_base": "D100100",
            "role_suffix": "b",
            "display_title": "유형자산",
            "pre": {"arcs": []},
            "def": {
                "arcs": [
                    {"from": "PropertyPlantAndEquipmentOwnerAbstract", "to": "DisclosureOfPropertyPlantAndEquipmentTable", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/all", "preferredLabel": ""},
                    {"from": "DisclosureOfPropertyPlantAndEquipmentTable", "to": "ClassesOfPropertyPlantAndEquipmentAxis", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/hypercube-dimension", "preferredLabel": ""},
                    {"from": "ClassesOfPropertyPlantAndEquipmentAxis", "to": "PropertyPlantAndEquipmentDomain", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/dimension-domain", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentDomain", "to": "LandMember", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentOwnerAbstract", "to": "PropertyPlantAndEquipmentLineItems", "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentLineItems", "to": "PropertyPlantAndEquipment", "order": 1, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                    {"from": "PropertyPlantAndEquipmentLineItems", "to": "Acquisitions", "order": 2, "arcrole": "http://xbrl.org/int/dim/arcrole/domain-member", "preferredLabel": ""},
                ]
            },
        }

        grouped = {
            "D100100": {
                "role_id": "D100100",
                "display_title": "유형자산",
                "group": "연결재무제표 주석",
                "scope": "연결",
                "is_body": False,
                "roles": [
                    ("role-pre", pre_bundle),
                    ("role-def", def_bundle),
                ],
            }
        }

        facts = [
            {
                "concept": "PropertyPlantAndEquipment",
                "period_key": "PY",
                "formatted_value": "100",
                "value": "100",
                "is_numeric": True,
                "scope": "연결",
                "dimension_map": {"ClassesOfPropertyPlantAndEquipmentAxis": "LandMember"},
                "member_set": {"LandMember"},
                "unit": "KRW",
                "decimals": "-3",
                "context_period_type": "instant",
            },
            {
                "concept": "PropertyPlantAndEquipment",
                "period_key": "CY",
                "formatted_value": "150",
                "value": "150",
                "is_numeric": True,
                "scope": "연결",
                "dimension_map": {"ClassesOfPropertyPlantAndEquipmentAxis": "LandMember"},
                "member_set": {"LandMember"},
                "unit": "KRW",
                "decimals": "-3",
                "context_period_type": "instant",
            },
        ]

        documents = build_role_documents(
            grouped,
            facts,
            labels,
            xsd,
        )
        section = documents["D100100"]["sections"][0]

        self.assertEqual(
            [block["type"] for block in section["context_blocks"]],
            ["sentence_area", "overview"],
        )

        rows = section["period_blocks"][0]["rows"]
        ppe_rows = [
            row
            for row in rows
            if row["concept"] == "PropertyPlantAndEquipment"
        ]

        self.assertEqual(
            [row["label"] for row in ppe_rows],
            ["기초 유형자산", "기말 유형자산"],
        )
        self.assertEqual(
            [row["preferredRoleKey"] for row in ppe_rows],
            ["periodStartLabel", "periodEndLabel"],
        )
        self.assertEqual(
            ppe_rows[0]["properties"]["기본 한글명"],
            "유형자산",
        )
        self.assertEqual(
            ppe_rows[0]["properties"]["표시 한글명"],
            "기초 유형자산",
        )
        self.assertEqual(
            ppe_rows[0]["properties"]["표현 속성"],
            "기초(Beginning)",
        )
        self.assertEqual(
            ppe_rows[0]["properties"]["id"],
            "ifrs-full_PropertyPlantAndEquipment",
        )


if __name__ == "__main__":
    unittest.main()
