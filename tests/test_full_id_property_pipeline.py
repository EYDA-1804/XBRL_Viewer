import io
import unittest
import zipfile

from xbrl_engine.instance import parse_contexts_units, parse_instance
import xml.etree.ElementTree as ET
from xbrl_engine.taxonomy import (
    parse_label_linkbases,
    parse_pre,
    parse_xsd_metadata,
)
from xbrl_engine.utils import (
    apply_role_value_sign,
    concept_properties,
    occurrence_properties,
    taxonomy_prefix,
)


IFRS_NS = "http://xbrl.ifrs.org/taxonomy/2025-01-01/ifrs-full"
DART_NS = "http://dart.fss.or.kr/taxonomy/2025-01-01/ifrs/dart"


class FullIdPropertyPipelineTest(unittest.TestCase):
    def test_taxonomy_prefix_prefers_specific_dart_and_entity_namespaces(self):
        self.assertEqual(taxonomy_prefix(DART_NS), "dart")
        self.assertEqual(
            taxonomy_prefix("http://dart.fss.or.kr/taxonomy/2025-12-31/entity00604268"),
            "entity",
        )
        self.assertEqual(taxonomy_prefix(IFRS_NS), "ifrs-full")

    def test_expression_labels_use_requested_names_and_negated_values_are_inverted(self):
        negated_prop = concept_properties(
            "Revenue",
            {},
            {},
            preferred_label="http://www.xbrl.org/2003/role/negatedLabel",
        )
        terse_prop = concept_properties(
            "Revenue",
            {},
            {},
            preferred_label="http://www.xbrl.org/2003/role/terseLabel",
        )

        self.assertEqual(negated_prop["표현 속성"], "기본(Negated)")
        self.assertEqual(terse_prop["표현 속성"], "별칭1")
        self.assertEqual(apply_role_value_sign("1,000", "http://www.xbrl.org/2003/role/negatedLabel"), "-1,000")
        self.assertEqual(apply_role_value_sign("1,000", "http://www.xbrl.org/2003/role/terseLabel"), "1,000")

    def build_zip(self):
        files = {
            "ifrs-full.xsd": f'''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 targetNamespace="{IFRS_NS}">
  <xsd:element name="Revenue" id="ifrs-full_Revenue"
    type="xbrli:monetaryItemType" xbrli:periodType="duration"
    xbrli:balance="credit"/>
</xsd:schema>''',
            "dart.xsd": f'''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 targetNamespace="{DART_NS}">
  <xsd:element name="Revenue" id="dart_Revenue"
    type="xbrli:stringItemType" xbrli:periodType="duration"/>
  <xsd:element name="RevenueTable" id="dart_RevenueTable"
    abstract="true"/>
</xsd:schema>''',
            "sample_lab-ko.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:labelLink xlink:type="extended" xlink:role="role-label">
  <link:loc xlink:type="locator" xlink:label="ifrsLoc" xlink:href="ifrs-full.xsd#ifrs-full_Revenue"/>
  <link:label xlink:type="resource" xlink:label="ifrsStd" xml:lang="ko"
    xlink:role="http://www.xbrl.org/2003/role/label">수익</link:label>
  <link:label xlink:type="resource" xlink:label="ifrsStart" xml:lang="ko"
    xlink:role="http://www.xbrl.org/2003/role/periodStartLabel">기초 수익</link:label>
  <link:labelArc xlink:type="arc" xlink:from="ifrsLoc" xlink:to="ifrsStd"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"/>
  <link:labelArc xlink:type="arc" xlink:from="ifrsLoc" xlink:to="ifrsStart"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"/>
  <link:loc xlink:type="locator" xlink:label="dartLoc" xlink:href="dart.xsd#dart_Revenue"/>
  <link:label xlink:type="resource" xlink:label="dartStd" xml:lang="ko"
    xlink:role="http://www.xbrl.org/2003/role/label">확장 수익 설명</link:label>
  <link:labelArc xlink:type="arc" xlink:from="dartLoc" xlink:to="dartStd"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"/>
 </link:labelLink>
</link:linkbase>''',
            "sample_lab-en.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:labelLink xlink:type="extended" xlink:role="role-label">
  <link:loc xlink:type="locator" xlink:label="ifrsLoc" xlink:href="ifrs-full.xsd#ifrs-full_Revenue"/>
  <link:label xlink:type="resource" xlink:label="ifrsStd" xml:lang="en"
    xlink:role="http://www.xbrl.org/2003/role/label">Revenue</link:label>
  <link:label xlink:type="resource" xlink:label="ifrsStart" xml:lang="en"
    xlink:role="http://www.xbrl.org/2003/role/periodStartLabel">Revenue at beginning</link:label>
  <link:labelArc xlink:type="arc" xlink:from="ifrsLoc" xlink:to="ifrsStd"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"/>
  <link:labelArc xlink:type="arc" xlink:from="ifrsLoc" xlink:to="ifrsStart"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"/>
 </link:labelLink>
</link:linkbase>''',
            "sample_pre.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:presentationLink xlink:type="extended" xlink:role="role-pre">
  <link:loc xlink:type="locator" xlink:label="table" xlink:href="dart.xsd#dart_RevenueTable"/>
  <link:loc xlink:type="locator" xlink:label="revenue" xlink:href="ifrs-full.xsd#ifrs-full_Revenue"/>
  <link:presentationArc xlink:type="arc" xlink:from="table" xlink:to="revenue"
    order="1" preferredLabel="http://www.xbrl.org/2003/role/periodStartLabel"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"/>
 </link:presentationLink>
</link:linkbase>''',
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, text in files.items():
                archive.writestr(name, text)
        buffer.seek(0)
        return buffer

    def test_taxonomy_fact_and_property_keep_full_id(self):
        with zipfile.ZipFile(self.build_zip()) as archive:
            _, xsd = parse_xsd_metadata(archive)
            labels = parse_label_linkbases(archive, xsd)
            pre = parse_pre(archive, xsd)

        self.assertIn("ifrs-full_Revenue", xsd)
        self.assertIn("dart_Revenue", xsd)
        self.assertEqual(
            pre["role-pre"]["arcs"][0]["to"],
            "ifrs-full_Revenue",
        )
        self.assertEqual(
            pre["role-pre"]["arcs"][0]["preferredRoleKey"],
            "periodStartLabel",
        )

        instance = f'''<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:ifrs="{IFRS_NS}" xmlns:dart="{DART_NS}">
 <xbrli:context id="C1">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:unit id="KRW"><xbrli:measure>iso4217:KRW</xbrli:measure></xbrli:unit>
 <ifrs:Revenue contextRef="C1" unitRef="KRW" decimals="-3" precision="12">1000</ifrs:Revenue>
 <dart:Revenue contextRef="C1">설명</dart:Revenue>
</xbrli:xbrl>'''.encode("utf-8")
        _, _, facts = parse_instance(instance, labels, xsd)
        self.assertEqual(
            {fact["concept"] for fact in facts},
            {"ifrs-full_Revenue", "dart_Revenue"},
        )

        fact = next(fact for fact in facts if fact["concept"] == "ifrs-full_Revenue")
        occurrence = {
            "concept": "ifrs-full_Revenue",
            "concept_id": "ifrs-full_Revenue",
            "occurrence_id": "role-pre|0",
            "preferredLabel": "http://www.xbrl.org/2003/role/periodStartLabel",
            "kind": "item",
        }
        prop = occurrence_properties(occurrence, labels, xsd, fact=fact)
        self.assertEqual(prop["ID"], "ifrs-full_Revenue")
        self.assertEqual(prop["표현속성"], "기초(Beginning)")
        self.assertEqual(prop["기본한글명"], "수익")
        self.assertEqual(prop["표시한글명"], "기초 수익")
        self.assertEqual(prop["기본영문명"], "Revenue")
        self.assertEqual(prop["표시영문명"], "Revenue at beginning")
        self.assertEqual(prop["Decimals"], "-3")
        self.assertEqual(prop["Precision"], "12")
        self.assertEqual(prop["Unit"], "iso4217_KRW")
        self.assertEqual(prop["id"], "ifrs-full_Revenue")

    def test_full_id_wins_over_unprefixed_xsd_id(self):
        xsd = {
            "Revenue": {
                "id": "Revenue",
                "xsd_id": "Revenue",
                "full_id": "ifrs-full_Revenue",
                "name": "Revenue",
                "prefix": "ifrs-full",
                "type": "xbrli:monetaryItemType",
                "periodType": "duration",
                "balance": "credit",
                "kind": "item",
                "aliases": ["Revenue", "ifrs-full_Revenue"],
            }
        }
        prop = concept_properties("Revenue", {}, xsd)
        self.assertEqual(prop["ID"], "ifrs-full_Revenue")

    def test_external_ifrs_locator_keeps_full_id_and_preferred_labels(self):
        files = {
            "sample_lab-ko.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:labelLink xlink:type="extended" xlink:role="labels">
  <link:loc xlink:type="locator" xlink:label="loc" xlink:href="https://xbrl.ifrs.org/ifrs-full.xsd#ifrs-full_Revenue"/>
  <link:label xlink:type="resource" xlink:label="std" xml:lang="ko" xlink:role="http://www.xbrl.org/2003/role/label">수익</link:label>
  <link:label xlink:type="resource" xlink:label="terse" xml:lang="ko" xlink:role="http://www.xbrl.org/2003/role/terseLabel">수익(간략)</link:label>
  <link:labelArc xlink:type="arc" xlink:from="loc" xlink:to="std"/>
  <link:labelArc xlink:type="arc" xlink:from="loc" xlink:to="terse"/>
 </link:labelLink>
</link:linkbase>''',
            "sample_lab-en.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:labelLink xlink:type="extended" xlink:role="labels">
  <link:loc xlink:type="locator" xlink:label="loc" xlink:href="https://xbrl.ifrs.org/ifrs-full.xsd#ifrs-full_Revenue"/>
  <link:label xlink:type="resource" xlink:label="std" xml:lang="en" xlink:role="http://www.xbrl.org/2003/role/label">Revenue</link:label>
  <link:label xlink:type="resource" xlink:label="terse" xml:lang="en" xlink:role="http://www.xbrl.org/2003/role/terseLabel">Revenue, terse</link:label>
  <link:labelArc xlink:type="arc" xlink:from="loc" xlink:to="std"/>
  <link:labelArc xlink:type="arc" xlink:from="loc" xlink:to="terse"/>
 </link:labelLink>
</link:linkbase>''',
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, text in files.items():
                archive.writestr(name, text)
        buffer.seek(0)

        with zipfile.ZipFile(buffer) as archive:
            labels = parse_label_linkbases(archive, {})

        preferred = "http://www.xbrl.org/2003/role/terseLabel"
        prop = concept_properties("ifrs-full_Revenue", labels, {}, preferred_label=preferred)
        self.assertEqual(prop["ID"], "ifrs-full_Revenue")
        self.assertEqual(prop["기본 한글명"], "수익")
        self.assertEqual(prop["기본 영문명"], "Revenue")
        self.assertEqual(prop["표시 한글명"], "수익(간략)")
        self.assertEqual(prop["표시 영문명"], "Revenue, terse")

    def test_context_dimensions_use_same_full_ids_as_definition_arcs(self):
        xsd = {
            "ifrs-full_ClassesOfPropertyPlantAndEquipmentAxis": {
                "name": "ClassesOfPropertyPlantAndEquipmentAxis",
                "full_id": "ifrs-full_ClassesOfPropertyPlantAndEquipmentAxis",
                "aliases": ["ClassesOfPropertyPlantAndEquipmentAxis"],
            },
            "ifrs-full_LandMember": {
                "name": "LandMember",
                "full_id": "ifrs-full_LandMember",
                "aliases": ["LandMember"],
            },
        }
        root = ET.fromstring('''<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2025-01-01/ifrs-full">
 <xbrli:context id="C1">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier>
   <xbrli:segment><xbrldi:explicitMember dimension="ifrs-full:ClassesOfPropertyPlantAndEquipmentAxis">ifrs-full:LandMember</xbrldi:explicitMember></xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
 </xbrli:context>
</xbrli:xbrl>''')
        contexts, _ = parse_contexts_units(root, xsd)
        self.assertEqual(contexts["C1"]["dimension_map"], {
            "ifrs-full_ClassesOfPropertyPlantAndEquipmentAxis": "ifrs-full_LandMember"
        })


if __name__ == "__main__":
    unittest.main()
