from flask import Flask, jsonify, render_template, request
import urllib3
import os

os.environ["DART_API_KEY"] = "1a3fd5237ece68afe2ee1b28dbf8cb24b555d5e0" #본인의 API KEY 입력

from xbrl_engine.dart_client import load_listed_companies, search_reports
from xbrl_engine.service import load_xbrl_report

urllib3.disable_warnings()
app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-XBRL-Engine-Version"] = "0722-taxonomy-prefix-match-v7"
    return response

@app.route("/")
def index(): return render_template("index_v2.html")

@app.route("/viewer")
def viewer(): return render_template("viewer.html")

@app.route("/api/companies")
def companies():
    try:
        q = request.args.get("q", "").strip()
        if len(q) < 2: return jsonify([])
        result = [c for c in load_listed_companies() if q in c["name"] or q in c["code"] or q in c["corp_code"]]
        return jsonify(result[:20])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/search", methods=["POST"])
def search():
    try:
        data = request.json or {}
        if not data.get("corp_code"): return jsonify({"error": "회사 코드가 필요합니다"}), 400
        return jsonify(search_reports(
            corp_code=data["corp_code"],
            year=int(data.get("year", 2025)),
            report_types=data.get("report_types", ["AR"]),
            fiscal_month=data.get("fiscal_month") or data.get("month", ""),
            # 구버전 화면이 final_report를 보내더라도 함수에서 호환 처리합니다.
            final_report=data.get("final_report"),
        ))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/xbrl")
def xbrl():
    try:
        rcept_no = request.args.get("rcept_no", "").strip()
        reprt_code = request.args.get("reprt_code", "11011").strip()
        if not rcept_no: return jsonify({"error": "rcept_no 필수"}), 400
        return jsonify(load_xbrl_report(rcept_no, reprt_code))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)), debug=True)
