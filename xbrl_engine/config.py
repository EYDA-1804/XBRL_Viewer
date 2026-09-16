import os

API_KEY = os.environ.get("DART_API_KEY", "")
REPORT_CODE_MAP = {"AR": "11011", "1Q": "11013", "SAR": "11012", "3Q": "11014"}
REPORT_NAME_MAP = {"11011": "사업보고서", "11013": "1분기보고서", "11012": "반기보고서", "11014": "3분기보고서"}
NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
    "xsd": "http://www.w3.org/2001/XMLSchema",
}
XLINK_LABEL = "{http://www.w3.org/1999/xlink}label"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_FROM = "{http://www.w3.org/1999/xlink}from"
XLINK_TO = "{http://www.w3.org/1999/xlink}to"
XLINK_ROLE = "{http://www.w3.org/1999/xlink}role"
XLINK_ARCROLE = "{http://www.w3.org/1999/xlink}arcrole"
XLINK_TARGET_ROLE = "{http://www.w3.org/1999/xlink}targetRole"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
