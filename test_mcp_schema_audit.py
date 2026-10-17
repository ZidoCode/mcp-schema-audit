"""Tests for mcp-schema-audit."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mcp_schema_audit as msa


def jl(obj):
    return json.dumps(obj)


INIT_OK = {"direction": "response", "id": 1, "result": {
    "protocolVersion": "2025-11-25", "serverInfo": {"name": "srv", "version": "1.0"}}}


class TestSchema(unittest.TestCase):
    def _tools(self, tools, init=True):
        lines = ([jl(INIT_OK)] if init else []) + [
            jl({"direction": "response", "id": 2, "result": {"tools": tools}})]
        return msa.audit(lines)

    def test_clean(self):
        tools = [{"name": "t", "inputSchema": {"type": "object", "properties": {}}}]
        self.assertEqual(self._tools(tools), [])

    def test_schema_missing(self):
        f = self._tools([{"name": "t"}])
        self.assertTrue(any(x[1] == "schema-missing" and x[0] == msa.CRITICAL for x in f))

    def test_schema_empty(self):
        f = self._tools([{"name": "t", "inputSchema": {}}])
        self.assertTrue(any(x[1] == "schema-empty" and x[0] == msa.CRITICAL for x in f))
        self.assertIn("gitlab-mcp #286", [x[2] for x in f if x[1] == "schema-empty"][0])

    def test_root_type_missing(self):
        f = self._tools([{"name": "t", "inputSchema": {"properties": {}}}])
        self.assertTrue(any(x[1] == "root-type-not-object" for x in f))

    def test_root_type_allof(self):
        # langfuse #13804: allOf root without type
        f = self._tools([{"name": "t", "inputSchema": {"allOf": [{"type": "object"}]}}])
        self.assertTrue(any(x[1] == "root-type-not-object" for x in f))

    def test_draft07_tuple(self):
        schema = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object",
                  "properties": {"span": {"type": "array", "items": [{"type": "number"}]}}}
        f = self._tools([{"name": "t", "inputSchema": schema}])
        hits = [x for x in f if x[1] == "draft07-dialect"]
        self.assertEqual(hits[0][0], msa.CRITICAL)
        self.assertIn("strapi #27395", hits[0][2])

    def test_draft07_no_tuple_warns(self):
        schema = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object",
                  "properties": {}}
        f = self._tools([{"name": "t", "inputSchema": schema}])
        hits = [x for x in f if x[1] == "draft07-dialect"]
        self.assertEqual(hits[0][0], msa.WARNING)

    def test_duplicate_tool(self):
        f = self._tools([{"name": "t", "inputSchema": {"type": "object"}},
                         {"name": "t", "inputSchema": {"type": "object"}}])
        self.assertTrue(any(x[1] == "duplicate-tool" for x in f))

    def test_unnamed_tool(self):
        f = self._tools([{"inputSchema": {"type": "object"}}])
        self.assertTrue(any(x[1] == "tool-unnamed" for x in f))


class TestInitialize(unittest.TestCase):
    def test_unknown_version(self):
        bad = {"direction": "response", "id": 1, "result": {
            "protocolVersion": "9.2.9", "serverInfo": {"name": "s", "version": "1"}}}
        f = msa.audit([jl(bad)])
        self.assertTrue(any(x[1] == "unknown-protocol-version" and x[0] == msa.CRITICAL
                            for x in f))

    def test_renegotiation_info(self):
        lines = [jl({"direction": "request", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2026-07-28"}}), jl(INIT_OK)]
        f = msa.audit(lines)
        self.assertTrue(any(x[1] == "version-renegotiated" and x[0] == msa.INFO for x in f))

    def test_serverinfo_missing(self):
        f = msa.audit([jl({"direction": "response", "id": 1,
                           "result": {"protocolVersion": "2025-11-25"}})])
        self.assertTrue(any(x[1] == "serverinfo-unnamed" for x in f))

    def test_no_initialize_at_all(self):
        f = msa.audit([jl({"direction": "response", "id": 2,
                           "result": {"tools": []}})])
        self.assertTrue(any(x[1] == "no-initialize" for x in f))

    def test_empty_tools(self):
        f = msa.audit([jl(INIT_OK), jl({"direction": "response", "id": 2,
                                        "result": {"tools": []}})])
        self.assertTrue(any(x[1] == "empty-tools" for x in f))

    def test_exit_codes(self):
        d = tempfile.mkdtemp()
        clean = os.path.join(d, "clean.jsonl")
        with open(clean, "w") as fh:
            fh.write(jl(INIT_OK) + "\n" + jl({"direction": "response", "id": 2, "result": {
                "tools": [{"name": "t", "inputSchema": {"type": "object"}}]}}) + "\n")
        dirty = os.path.join(d, "dirty.jsonl")
        with open(dirty, "w") as fh:
            fh.write(jl(INIT_OK) + "\n" + jl({"direction": "response", "id": 2, "result": {
                "tools": [{"name": "t", "inputSchema": {}}]}}) + "\n")
        script = os.path.join(os.path.dirname(msa.__file__), "mcp_schema_audit.py")
        self.assertEqual(subprocess.run([sys.executable, script, clean],
                                        capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run([sys.executable, script, dirty],
                                        capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
