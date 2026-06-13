"""Tests for sanitized HAR analysis."""
import json
import urllib.parse

from gemini_web2api.har_analyze import analyze_har


def test_analyze_har_sanitizes_stream_payload(tmp_path):
    inner = [["secret prompt", 0, None, None, None, None, 0], ["en"], None, "secret context"]
    body = urllib.parse.urlencode({"f.req": json.dumps([None, json.dumps(inner)])})
    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "test"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate",
                        "headers": [{"name": "Cookie", "value": "SID=secret"}],
                        "postData": {"text": body},
                    },
                    "response": {"status": 200, "content": {"mimeType": "application/json", "size": 42, "text": "{}"}},
                }
            ],
        }
    }
    path = tmp_path / "sample.har"
    path.write_text(json.dumps(har), encoding="utf-8")

    report = analyze_har(path)

    assert report["entries"] == 1
    assert report["sensitive_header_counts"]["cookie"] == 1
    stream = report["stream_generate"][0]
    assert stream["shape"]["inner_len"] == 4
    assert stream["shape"]["fields"]["0"] == "list:7"
    assert "secret prompt" not in json.dumps(report)
    assert "SID=secret" not in json.dumps(report)


def test_analyze_har_builds_sanitized_batchexecute_rpc_catalog(tmp_path):
    args = json.dumps(["secret prompt", {"private": "secret-token"}, 7])
    body = urllib.parse.urlencode({"f.req": json.dumps([[["MaZiqc", args, None, "generic"]]])})
    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "test"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://gemini.google.com/u/1/_/BardChatUi/data/batchexecute?rpcids=MaZiqc",
                        "headers": [{"name": "Cookie", "value": "SID=secret"}],
                        "postData": {"text": body},
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/json", "size": 123, "text": "Canvas"},
                    },
                }
            ],
        }
    }
    path = tmp_path / "sample.har"
    path.write_text(json.dumps(har), encoding="utf-8")

    report = analyze_har(path)

    catalog = report["rpc_catalog"]
    assert catalog[0]["rpcid"] == "MaZiqc"
    assert catalog[0]["count"] == 1
    assert catalog[0]["statuses"] == {"200": 1}
    assert catalog[0]["post_length"]["min"] == len(body)
    assert catalog[0]["response_size"]["max"] == 123
    assert catalog[0]["arg_shapes"][0]["shape"]["type"] == "list"
    dumped = json.dumps(report, ensure_ascii=False)
    assert "secret prompt" not in dumped
    assert "secret-token" not in dumped
    assert "private" not in dumped
    assert "SID=secret" not in dumped


def test_analyze_har_records_batchexecute_response_markers_without_values(tmp_path):
    args = json.dumps([])
    body = urllib.parse.urlencode({"f.req": json.dumps([[["cYRIkd", args, None, "generic"]]])})
    payload = json.dumps([
        None,
        {
            "status": "done",
            "audio_url": "https://example.com/private-audio.mp3",
            "task_id": "secret-task-id",
        },
    ])
    response_line = json.dumps([["wrb.fr", "cYRIkd", payload, None, None, None, "generic"]])
    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "test"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://gemini.google.com/u/1/_/BardChatUi/data/batchexecute?rpcids=cYRIkd",
                        "headers": [],
                        "postData": {"text": body},
                    },
                    "response": {
                        "status": 200,
                        "content": {"mimeType": "application/json", "size": 300, "text": ")]}'\n\n" + response_line},
                    },
                }
            ],
        }
    }
    path = tmp_path / "sample.har"
    path.write_text(json.dumps(har), encoding="utf-8")

    report = analyze_har(path)

    catalog = report["rpc_catalog"][0]
    assert catalog["rpcid"] == "cYRIkd"
    assert catalog["response_payload_shapes"]
    assert catalog["response_markers"]["http_url"] == 1
    assert catalog["response_markers"]["audio"] >= 1
    assert catalog["response_markers"]["task_status"] >= 1
    dumped = json.dumps(report, ensure_ascii=False)
    assert "private-audio" not in dumped
    assert "secret-task-id" not in dumped
