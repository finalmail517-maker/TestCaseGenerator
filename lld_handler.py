"""
LLD Handler - Extracts content from Word LLD documents and generates test cases.
Plugs into existing LLMHandler, CSVHandler, and RAGSystem without modifying them.

Smart fallback: when LLM quota is exceeded, extracts testable items directly
from the raw docx structure (paragraphs + table rows) and generates meaningful
named test cases — no LLM required for fallback.

Handles:
  - Class sections    → every method with its actual parameters
  - API sections      → every endpoint with its response codes
  - Database sections → every column with constraints
  - Error sections    → every error code with name + description
  - Flow sections     → every step as a numbered test step
  - Validation sections → every rule as an assertion
"""

import json
import zipfile
import io
import re
from typing import Dict, List, Tuple
from logger import get_app_logger

logger = get_app_logger("lld_handler")

# Table header rows to skip during extraction
HEADER_ROWS = {
    "method | parameters | description",
    "column | type | constraint | description",
    "method | endpoint | request body | response",
    "method | endpoint | auth required | description",
    "code | error | description",
    "method | parameters | description",
}


class LLDHandler:
    """
    Reads a Word (.docx) LLD document, extracts structured content section by section,
    and generates test cases using LLMHandler. Falls back to rule-based extraction
    when LLM is unavailable (quota exceeded, network error, etc).
    """

    def __init__(self, llm_handler, rag_system=None):
        self.llm = llm_handler
        self.rag = rag_system
        logger.info("✅ LLDHandler initialized")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def process_lld_file(
        self,
        file_bytes: bytes,
        filename: str,
        test_types: List[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        Main entry point. Returns {"Unit Test": [...], "Functional Test": [...]}
        identical shape to TestGenerator output.
        """
        if test_types is None:
            test_types = ["Unit Test", "Functional Test"]

        logger.info(f"📄 Processing LLD file: {filename}")

        raw_lines = self._extract_raw_lines(file_bytes)
        if not raw_lines:
            logger.error("❌ No content could be extracted from the document")
            return {"Unit Test": [], "Functional Test": []}

        logger.info(f"✅ Extracted {len(raw_lines)} lines from {filename}")

        sections = self._split_into_sections(raw_lines)
        logger.info(f"📑 Identified {len(sections)} LLD sections")

        if self.rag:
            self._store_in_rag(sections, filename)

        all_tests: Dict[str, List[Dict]] = {"Unit Test": [], "Functional Test": []}

        for test_type in test_types:
            logger.info(f"🔧 Generating {test_type}s from LLD...")
            tests = self._generate_tests_from_sections(sections, test_type, filename)
            all_tests[test_type] = tests
            logger.info(f"✅ Generated {len(tests)} {test_type}s")

        total = sum(len(v) for v in all_tests.values())
        logger.info(f"🏁 LLD test generation complete – {total} total tests")
        return all_tests

    # ──────────────────────────────────────────────────────────────────
    # DOCX EXTRACTION — returns list of (type, text) tuples
    # type is "P" (paragraph) or "T" (table row)
    # ──────────────────────────────────────────────────────────────────

    def _extract_raw_lines(self, file_bytes: bytes) -> List[Tuple[str, str]]:
        """Extract all text from docx preserving paragraph vs table-row distinction."""
        try:
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                if "word/document.xml" not in z.namelist():
                    logger.error("❌ Not a valid .docx file")
                    return []
                with z.open("word/document.xml") as doc_xml:
                    from xml.etree import ElementTree as ET
                    tree = ET.parse(doc_xml)

            body = tree.getroot().find(
                ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body"
            )
            if body is None:
                return []

            lines = []
            for child in body:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "p":
                    text = "".join(
                        run.text for run in child.iter(f"{ns}t") if run.text
                    ).strip()
                    if text:
                        lines.append(("P", text))
                elif tag == "tbl":
                    for row in child.iter(f"{ns}tr"):
                        cells = []
                        for cell in row.iter(f"{ns}tc"):
                            cell_text = " ".join(
                                t.text for t in cell.iter(f"{ns}t") if t.text
                            ).strip()
                            cells.append(cell_text)
                        if any(cells):
                            lines.append(("T", " | ".join(cells)))

            return lines

        except Exception as e:
            logger.error(f"❌ Error extracting docx: {e}", exc_info=True)
            return []

    # ──────────────────────────────────────────────────────────────────
    # SECTION SPLITTING
    # ──────────────────────────────────────────────────────────────────

    _HEADING_RE = re.compile(r"^(\d+[\.\d]*\s+.{2,}|[A-Z][A-Z\s]{4,})\s*$")

    def _is_heading(self, ltype: str, text: str) -> bool:
        return (
            ltype == "P"
            and bool(self._HEADING_RE.match(text))
            and len(text) < 100
        )

    def _split_into_sections(self, raw_lines: List[Tuple[str, str]]) -> List[Dict]:
        """Split raw lines into named sections, classifying each."""
        sections = []
        current_heading = "Document Header"
        current_lines: List[Tuple[str, str]] = []

        for ltype, text in raw_lines:
            if self._is_heading(ltype, text):
                if current_lines:
                    sec_type = self._classify(current_heading, current_lines)
                    sections.append({
                        "heading": current_heading,
                        "lines": current_lines,
                        "type": sec_type,
                    })
                current_heading = text
                current_lines = []
            else:
                current_lines.append((ltype, text))

        if current_lines:
            sec_type = self._classify(current_heading, current_lines)
            sections.append({
                "heading": current_heading,
                "lines": current_lines,
                "type": sec_type,
            })

        return sections

    def _classify(self, heading: str, lines: List[Tuple[str, str]]) -> str:
        combined = (heading + " " + " ".join(t for _, t in lines)).lower()
        if any(k in combined for k in ["post |", "get |", "put |", "delete |", "patch |"]):
            return "api"
        if any(k in combined for k in ["method | parameters", "method |"]):
            return "class"
        if any(k in combined for k in ["table:", "varchar", "int | pk", "boolean |", "datetime |", "text | not null"]):
            return "database"
        if re.search(r'\b(validationerror|authenticationerror|forbiddenerror|notfounderror|conflicterror|ratelimiterror|servererror)\b', combined):
            return "error"
        if any(k in combined for k in ["flow", "sequence", "process"]):
            return "flow"
        if any(k in combined for k in ["rule", "validation", "minimum", "maximum"]):
            return "validation"
        return "general"

    # ──────────────────────────────────────────────────────────────────
    # TEST GENERATION
    # ──────────────────────────────────────────────────────────────────

    def _generate_tests_from_sections(
        self,
        sections: List[Dict],
        test_type: str,
        filename: str
    ) -> List[Dict]:
        all_tests = []
        tc_index = 1

        for i, section in enumerate(sections, 1):
            heading = section["heading"]
            sec_type = section["type"]

            if not section["lines"]:
                continue

            logger.info(f"  Section {i}/{len(sections)}: '{heading}' [{sec_type}]")

            # Build plain text version for LLM prompt
            content = "\n".join(text for _, text in section["lines"])
            prompt = self._build_lld_prompt(heading, content, sec_type, test_type)

            try:
                response = self.llm._make_request(prompt)

                if not response or response.startswith("Error:"):
                    logger.warning(f"⚠️ LLM failed for '{heading}' — using smart fallback")
                    fallbacks = self._smart_fallback(section, test_type, filename, tc_index)
                    all_tests.extend(fallbacks)
                    tc_index += len(fallbacks)
                    continue

                parsed = self._parse_lld_response(response, test_type, section, filename)

                if not parsed:
                    logger.warning(f"⚠️ Parse failed for '{heading}' — using smart fallback")
                    fallbacks = self._smart_fallback(section, test_type, filename, tc_index)
                    all_tests.extend(fallbacks)
                    tc_index += len(fallbacks)
                    continue

                for test in parsed:
                    test["file"] = filename
                    test["chunk_name"] = heading
                    test["chunk_type"] = sec_type
                    test["source"] = "lld"

                all_tests.extend(parsed)
                tc_index += len(parsed)
                logger.info(f"    ✅ {len(parsed)} LLM tests for '{heading}'")

            except Exception as e:
                logger.error(f"    ❌ Exception on '{heading}': {e}")
                fallbacks = self._smart_fallback(section, test_type, filename, tc_index)
                all_tests.extend(fallbacks)
                tc_index += len(fallbacks)

        return all_tests

    def _parse_lld_response(self, response, test_type, section, filename):
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start == -1 or end <= start:
                return []

            raw_tests = json.loads(response[start:end])
            valid = []

            for idx, t in enumerate(raw_tests):
                if not isinstance(t, dict):
                    continue
                if test_type == "Functional Test":
                    valid.append({
                        "name": t.get("test_case_id", f"TC-LLD-{idx+1:02d}"),
                        "test_case_id": t.get("test_case_id", f"TC-LLD-{idx+1:02d}"),
                        "description": t.get("description", ""),
                        "steps": t.get("steps", "Step 1: Execute\nStep 2: Verify"),
                        "expected_result": t.get("expected_result", "System behaves as expected"),
                        "type": test_type,
                        "target": t.get("target", section["heading"]),
                        "format": "professional"
                    })
                else:
                    valid.append({
                        "name": t.get("name", f"test_{idx+1}"),
                        "description": t.get("description", ""),
                        "code": t.get("code", "def test():\n    pass"),
                        "type": test_type,
                        "target": t.get("target", section["heading"]),
                        "format": "code"
                    })
            return valid

        except Exception as e:
            logger.error(f"❌ Response parse error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────
    # LLM PROMPT
    # ──────────────────────────────────────────────────────────────────

    def _build_lld_prompt(self, heading: str, content: str, sec_type: str, test_type: str) -> str:
        content = content[:2000]
        if test_type == "Unit Test":
            return f"""You are a QA engineer. Read this LLD section and generate unit test cases.

SECTION HEADING: {heading}
SECTION TYPE: {sec_type}
SECTION CONTENT:
{content}

Generate 3-5 unit test cases based on the above LLD content.
Each test must be specific to the described functionality, not generic.

Return ONLY a valid JSON array, no explanation, no markdown:
[
  {{
    "name": "test_register_user_success",
    "description": "Tests that register_user creates a new user when valid inputs are provided",
    "code": "def test_register_user_success():\\n    # Arrange\\n    username = 'testuser'\\n    password = 'Test@1234'\\n    # Act\\n    result = user_service.register_user(username, password, email)\\n    # Assert\\n    assert result['user_id'] is not None",
    "target": "register_user"
  }}
]"""
        else:
            return f"""You are a QA engineer. Read this LLD section and generate functional test cases.

SECTION HEADING: {heading}
SECTION TYPE: {sec_type}
SECTION CONTENT:
{content}

Generate 3-5 functional test cases based on the above LLD content.
Each test must be specific to the described functionality, not generic.

Return ONLY a valid JSON array, no explanation, no markdown:
[
  {{
    "test_case_id": "TC-FN-01",
    "description": "Verify that user registration succeeds with valid inputs",
    "steps": "Step 1: Send POST /api/v1/register with valid username, password, email\\nStep 2: Verify response status is 201\\nStep 3: Verify response contains user_id",
    "expected_result": "User is created successfully. Response returns 201 with user_id and success message.",
    "target": "register_user"
  }}
]"""

    # ──────────────────────────────────────────────────────────────────
    # SMART FALLBACK — extracts every item from structured docx content
    # ──────────────────────────────────────────────────────────────────

    def _smart_fallback(
        self,
        section: Dict,
        test_type: str,
        filename: str,
        start_index: int
    ) -> List[Dict]:
        items = self._extract_testable_items(section)
        tests = []

        for i, item in enumerate(items):
            idx = start_index + i
            if test_type == "Unit Test":
                tests.append(self._build_unit_test(item, filename, idx))
            else:
                tests.append(self._build_functional_test(item, filename, idx))

        logger.info(f"    📝 Smart fallback: {len(tests)} tests for '{section['heading']}'")
        return tests

    def _extract_testable_items(self, section: Dict) -> List[Dict]:
        """
        Extract every testable item from a section's structured lines.
        Uses 'P' (paragraph) and 'T' (table row) types correctly.
        """
        heading = section["heading"]
        sec_type = section["type"]
        lines = section["lines"]

        table_rows = [text for ltype, text in lines if ltype == "T"]
        para_lines = [text for ltype, text in lines if ltype == "P"]
        items = []

        # ── CLASS: every method row ────────────────────────────────────
        if sec_type == "class":
            for row in table_rows:
                if row.lower() in HEADER_ROWS:
                    continue
                m = re.match(r'^([a-z][a-z0-9_]+)\(\)\s*\|\s*([^|]+)\|(.+)', row)
                if m:
                    method = m.group(1).strip()
                    params = m.group(2).strip()
                    desc = m.group(3).strip()
                    items.append({
                        'type': 'method', 'name': method,
                        'target': method, 'params': params,
                        'desc': desc, 'context': heading
                    })

        # ── API: every endpoint row ────────────────────────────────────
        elif sec_type == "api":
            for row in table_rows:
                if row.lower() in HEADER_ROWS:
                    continue
                m = re.match(r'^(GET|POST|PUT|DELETE|PATCH)\s*\|\s*(/[\w/\-{}]+)\s*\|(.+)', row)
                if m:
                    http_m = m.group(1)
                    path = m.group(2).strip()
                    rest = m.group(3).strip()
                    # response is last pipe-separated part
                    parts = [p.strip() for p in rest.split('|')]
                    response = parts[-1] if parts else ""
                    name = (path.strip('/').replace('/', '_').replace('-', '_')
                            .replace('{', '').replace('}', ''))
                    items.append({
                        'type': 'api',
                        'name': f"{http_m.lower()}_{name}",
                        'target': f"{http_m} {path}",
                        'response': response,
                        'context': heading
                    })

        # ── DATABASE: every column row ─────────────────────────────────
        elif sec_type == "database":
            columns = []
            for row in table_rows:
                if row.lower() in HEADER_ROWS:
                    continue
                parts = [p.strip() for p in row.split('|')]
                if len(parts) >= 4:
                    col_name, col_type, constraint, col_desc = (
                        parts[0], parts[1], parts[2], parts[3]
                    )
                    if re.match(r'^(INT|VARCHAR|TEXT|BOOLEAN|DATETIME|FLOAT|BIGINT)', col_type, re.I):
                        columns.append({
                            'name': col_name, 'type': col_type,
                            'constraint': constraint, 'description': col_desc
                        })
            if columns:
                tbl = re.search(r'Table:\s*(\w+)', heading)
                table_name = tbl.group(1) if tbl else heading
                items.append({
                    'type': 'database', 'name': f"table_{table_name.lower()}",
                    'target': table_name, 'columns': columns, 'context': heading
                })

        # ── ERROR CODES: every error row ───────────────────────────────
        elif sec_type == "error":
            errors = []
            for row in table_rows:
                if row.lower() in HEADER_ROWS:
                    continue
                m = re.match(r'^(\d{3})\s*\|\s*(\w+)\s*\|\s*(.+)', row)
                if m:
                    errors.append({
                        'code': m.group(1),
                        'name': m.group(2),
                        'desc': m.group(3).strip()
                    })
            if errors:
                items.append({
                    'type': 'error', 'name': 'error_handling',
                    'target': heading, 'errors': errors, 'context': heading
                })

        # ── FLOW: paragraph lines are the steps ────────────────────────
        elif sec_type == "flow":
            steps = [t for t in para_lines if len(t) > 5]
            if steps:
                safe = re.sub(r'\W+', '_', heading.lower())[:40]
                items.append({
                    'type': 'flow', 'name': safe,
                    'target': heading, 'steps': steps, 'context': heading
                })

        # ── VALIDATION: paragraph lines are the rules ──────────────────
        elif sec_type == "validation":
            rules = [t for t in para_lines if len(t) > 5]
            if rules:
                safe = re.sub(r'\W+', '_', heading.lower())[:40]
                items.append({
                    'type': 'validation', 'name': safe,
                    'target': heading, 'rules': rules, 'context': heading
                })

        # ── GENERAL: use heading as single item ────────────────────────
        if not items:
            safe = re.sub(r'\W+', '_', heading.lower())[:40]
            items.append({
                'type': 'general', 'name': safe,
                'target': heading, 'context': heading
            })

        return items

    # ──────────────────────────────────────────────────────────────────
    # UNIT TEST BUILDER
    # ──────────────────────────────────────────────────────────────────

    def _build_unit_test(self, item: Dict, filename: str, index: int) -> Dict:
        name = f"test_{item['name']}"
        target = item['target']
        t = item['type']

        if t == 'method':
            params = item.get('params', '')
            desc_text = item.get('desc', '')
            param_list = ', '.join([
                p.strip().split()[0] for p in params.split(',') if p.strip()
            ]) if params else '...'
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for: {target}({params})\n"
                f"    Description: {desc_text}\n"
                f"    LLD Section: {item['context']}\n"
                f'    """\n'
                f"    # Arrange\n"
                f"    # TODO: prepare inputs — {params}\n\n"
                f"    # Act\n"
                f"    # result = {target}({param_list})\n\n"
                f"    # Assert\n"
                f"    # assert result is not None"
            )
            desc = f"Unit test for {target}({params}) — {desc_text[:80]}"

        elif t == 'api':
            parts = target.split(' ', 1)
            http_m, path = parts[0], parts[1] if len(parts) > 1 else ''
            resp = item.get('response', '')
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for API: {target}\n"
                f"    Expected response: {resp}\n"
                f'    """\n'
                f"    # Arrange\n"
                f"    # TODO: prepare payload for {http_m} {path}\n\n"
                f"    # Act\n"
                f"    # response = client.{http_m.lower()}('{path}')\n\n"
                f"    # Assert\n"
                f"    # assert response.status_code in [200, 201]"
            )
            desc = f"Unit test for API endpoint: {target}"

        elif t == 'database':
            table = item['target']
            cols = item.get('columns', [])
            col_checks = "\n    # ".join([
                f"assert '{c['name']}' in result  # {c['type']} {c['constraint']}"
                for c in cols[:6]
            ])
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for DB table: {table}\n"
                f"    Columns: {', '.join([c['name'] for c in cols])}\n"
                f'    """\n'
                f"    # Arrange: insert test record into {table}\n\n"
                f"    # Act\n"
                f"    # result = db.query('SELECT * FROM {table} WHERE ...')\n\n"
                f"    # Assert\n"
                f"    # {col_checks}"
            )
            desc = f"Unit test for DB table: {table} ({len(cols)} columns: {', '.join([c['name'] for c in cols])})"

        elif t == 'error':
            errors = item.get('errors', [])
            error_lines = "\n    # ".join([
                f"[{e['code']}] {e['name']}: {e['desc']}" for e in errors
            ])
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for all error codes\n"
                f'    """\n'
                f"    # Error scenarios to cover:\n"
                f"    # {error_lines}\n\n"
                f"    pass"
            )
            desc = f"Unit test for error codes: {', '.join([e['code']+' '+e['name'] for e in errors])}"

        elif t == 'flow':
            steps = item.get('steps', [])
            steps_txt = "\n    # ".join([f"Step {i+1}: {s}" for i, s in enumerate(steps)])
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for flow: {item['context']}\n"
                f'    """\n'
                f"    # Flow steps:\n"
                f"    # {steps_txt}\n\n"
                f"    pass"
            )
            desc = f"Unit test for flow: {item['context']} ({len(steps)} steps)"

        elif t == 'validation':
            rules = item.get('rules', [])
            rules_txt = "\n    # ".join([f"Rule {i+1}: {r}" for i, r in enumerate(rules)])
            code = (
                f"def {name}():\n"
                f'    """\n'
                f"    Unit Test for validation: {item['context']}\n"
                f'    """\n'
                f"    # Validation rules:\n"
                f"    # {rules_txt}\n\n"
                f"    pass"
            )
            desc = f"Unit test for validation: {item['context']} ({len(rules)} rules)"

        else:
            code = f"def {name}():\n    \"\"\" {item['context']} \"\"\"\n    pass"
            desc = f"Unit test for: {item['context']}"

        return {
            'name': name, 'description': desc, 'code': code,
            'type': 'Unit Test', 'target': target, 'file': filename,
            'chunk_name': item['context'], 'chunk_type': t,
            'source': 'lld', 'fallback': True, 'format': 'code'
        }

    # ──────────────────────────────────────────────────────────────────
    # FUNCTIONAL TEST BUILDER
    # ──────────────────────────────────────────────────────────────────

    def _build_functional_test(self, item: Dict, filename: str, index: int) -> Dict:
        target = item['target']
        t = item['type']
        tc_id = f"TC-LLD-{index:02d}"

        if t == 'method':
            params = item.get('params', '')
            desc_text = item.get('desc', '')
            desc = f"Verify {target}() behaves correctly — {desc_text[:80]}"
            steps = (
                f"Step 1: Set up required dependencies for {target}\n"
                f"Step 2: Call {target}({params})\n"
                f"Step 3: Verify return value is correct and not null\n"
                f"Step 4: Verify no unexpected exceptions are raised"
            )
            expected = f"{target}() completes successfully. {desc_text}"

        elif t == 'api':
            parts = target.split(' ', 1)
            http_m, path = parts[0], parts[1] if len(parts) > 1 else ''
            resp = item.get('response', '')
            desc = f"Verify {http_m} {path} returns correct response"
            steps = (
                f"Step 1: Prepare valid request payload for {http_m} {path}\n"
                f"Step 2: Send {http_m} request to {path} with required headers\n"
                f"Step 3: Verify response status code is correct\n"
                f"Step 4: Verify response body matches expected: {resp[:120] if resp else 'success'}"
            )
            expected = f"{http_m} {path} returns: {resp if resp else 'success response with correct fields'}"

        elif t == 'database':
            table = item['target']
            cols = item.get('columns', [])
            not_null = [c for c in cols if 'NOT NULL' in c.get('constraint', '').upper()]
            unique_cols = [c for c in cols if 'UNIQUE' in c.get('constraint', '').upper()]
            desc = f"Verify table {table} stores data correctly and enforces all constraints"
            steps = (
                f"Step 1: Insert a valid record into {table} with all {len(cols)} fields\n"
                f"Step 2: Verify all columns are stored correctly\n"
                f"Step 3: Attempt to insert record missing NOT NULL fields: "
                f"{', '.join([c['name'] for c in not_null[:3]])}\n"
                f"Step 4: Verify constraint violation is raised\n"
                + (f"Step 5: Attempt to insert duplicate values for UNIQUE columns: "
                   f"{', '.join([c['name'] for c in unique_cols[:2]])}\n"
                   f"Step 6: Verify uniqueness constraint is enforced"
                   if unique_cols else "")
            )
            expected = (
                f"Table {table} correctly stores valid records and enforces "
                f"all constraints across {len(cols)} columns"
            )

        elif t == 'error':
            errors = item.get('errors', [])
            desc = "Verify system returns correct HTTP error codes for all invalid scenarios"
            steps = "\n".join([
                f"Step {i+1}: Trigger {e['name']} ({e['code']}) — {e['desc']}"
                for i, e in enumerate(errors)
            ])
            expected = (
                f"System returns correct HTTP status codes for all error scenarios: "
                f"{', '.join([e['code']+' ('+e['name']+')' for e in errors])}"
            )

        elif t == 'flow':
            steps_list = item.get('steps', [])
            desc = f"Verify the complete flow: {item['context']}"
            steps = "\n".join([
                f"Step {i+1}: {s}" for i, s in enumerate(steps_list)
            ])
            expected = (
                f"All {len(steps_list)} steps in '{item['context']}' "
                f"complete successfully in the correct sequence"
            )

        elif t == 'validation':
            rules = item.get('rules', [])
            desc = f"Verify all {len(rules)} validation rules for: {item['context']}"
            steps = (
                f"Step 1: Submit input violating each rule:\n"
                + "\n".join([f"         Rule {i+1}: {r}" for i, r in enumerate(rules)])
                + f"\nStep 2: Verify system rejects each invalid input with correct error\n"
                f"Step 3: Submit input satisfying all {len(rules)} rules\n"
                f"Step 4: Verify system accepts valid input"
            )
            expected = (
                f"System enforces all {len(rules)} validation rules in "
                f"'{item['context']}'. Invalid input rejected, valid input accepted."
            )

        else:
            desc = f"Verify: {item['context']}"
            steps = f"Step 1: Set up scenario\nStep 2: Execute operation\nStep 3: Verify outcome"
            expected = f"System behaves as described in LLD section '{item['context']}'"

        return {
            'name': tc_id, 'test_case_id': tc_id,
            'description': desc, 'steps': steps, 'expected_result': expected,
            'type': 'Functional Test', 'target': target, 'file': filename,
            'chunk_name': item['context'], 'chunk_type': t,
            'source': 'lld', 'fallback': True, 'format': 'professional'
        }

    # ──────────────────────────────────────────────────────────────────
    # RAG STORAGE
    # ──────────────────────────────────────────────────────────────────

    def _store_in_rag(self, sections: List[Dict], filename: str):
        try:
            content = "\n\n".join(
                f"# {s['heading']}\n" + "\n".join(text for _, text in s["lines"])
                for s in sections
            )
            parsed_data = {
                filename: {
                    "filename": filename,
                    "language": "lld_document",
                    "code": content,
                    "functions": [{"name": s["heading"]} for s in sections if s["type"] in ("class", "function")],
                    "classes": [{"name": s["heading"]} for s in sections if s["type"] == "class"],
                    "imports": [],
                    "lines_of_code": sum(len(s["lines"]) for s in sections),
                    "complexity": "medium"
                }
            }
            self.rag.add_code_documents(parsed_data)
            logger.info("✅ LLD content stored in RAG system")
        except Exception as e:
            logger.warning(f"⚠️ Could not store in RAG: {e}")

    def get_lld_summary(self, sections: List[Dict]) -> str:
        lines = [f"📄 Extracted {len(sections)} sections from LLD:"]
        for s in sections:
            lines.append(f"  • [{s['type'].upper()}] {s['heading']}")
        return "\n".join(lines)
