import unittest

from xbrl_engine.builders import BuildRuntime, pre_ordered_stream


class BuilderRuntimeCacheTest(unittest.TestCase):
    def test_pre_stream_is_reused_within_one_report_build(self):
        xsd = {
            "Root": {
                "kind": "abstract",
                "full_id": "dart_Root",
                "id": "dart_Root",
                "name": "Root",
                "prefix": "dart",
                "aliases": ["dart_Root"],
            },
            "Item": {
                "kind": "item",
                "full_id": "ifrs-full_Item",
                "id": "ifrs-full_Item",
                "name": "Item",
                "prefix": "ifrs-full",
                "aliases": ["ifrs-full_Item"],
            },
        }
        bundle = {
            "pre": {
                "arcs": [
                    {
                        "from": "Root",
                        "to": "Item",
                        "order": 1,
                        "preferredLabel": "",
                    }
                ]
            }
        }
        runtime = BuildRuntime([], {}, xsd)

        first = pre_ordered_stream(bundle, xsd, runtime=runtime)
        second = pre_ordered_stream(bundle, xsd, runtime=runtime)

        self.assertIs(first, second)
        self.assertEqual(len(runtime.pre_streams), 1)
        self.assertEqual(first[-1]["concept_id"], "ifrs-full_Item")


if __name__ == "__main__":
    unittest.main()
