import streamlit as st
import os
import re
import time
import json
from pathlib import Path
from datetime import datetime
from llm_handler import LLMHandler
from code_parser import CodeParser
from test_generator import TestGenerator
from git_handler import GitHandler
from csv_handler import CSVHandler
from rag_system import RAGSystem
from security import SecurityManager
from logger import get_app_logger, TestGenerationLogger
from lld_handler import LLDHandler

# ---- Logger -------------------------------------------------------------------
logger = get_app_logger("streamlit_app")
test_logger = TestGenerationLogger()
logger.info("=" * 60)
logger.info("Test Case Generator – Unified Chat UI (full features)")
logger.info("=" * 60)

# ---- Page config ---------------------------------------------------------------
st.set_page_config(
    page_title="AI Test Case Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Session state -------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "previous_code" not in st.session_state:
    st.session_state.previous_code = {}
if "rag_system" not in st.session_state:
    st.session_state.rag_system = RAGSystem()
if "llm_handler" not in st.session_state:
    st.session_state.llm_handler = LLMHandler()
if "security_manager" not in st.session_state:
    st.session_state.security_manager = SecurityManager()
#lld----------------
if "lld_handler" not in st.session_state:
    st.session_state.lld_handler = LLDHandler(
        st.session_state.llm_handler,
        st.session_state.rag_system
    )
#------------------
if "generated_tests" not in st.session_state:
    st.session_state.generated_tests = {}
if "last_repo_info" not in st.session_state:
    st.session_state.last_repo_info = {}
if "pending_git" not in st.session_state:
    st.session_state.pending_git = None
if "current_repo_path" not in st.session_state:
    st.session_state.current_repo_path = None
if "current_repo_csv" not in st.session_state:
    st.session_state.current_repo_csv = {}
if "current_chat_file" not in st.session_state:
    st.session_state.current_chat_file = None
if "selected_test_types" not in st.session_state:
    st.session_state.selected_test_types = ["Unit Test", "Functional Test"]


def generate_smart_chat_name(chat_history: list, selected_test_types: list = None) -> str:
    """
    Generate smart chat name based on:
    1. First user message content (what tests were requested)
    2. Repository name from URL
    3. Selected test types from sidebar
    
    Examples:
    - "Functional and Unit test cases for vector_c"
    - "Unit test cases for vector_c"
    - "Functional test cases for my_project"
    """
    if not chat_history:
        return "chat"
    
    # Find first user message
    first_message = None
    for msg in chat_history:
        if msg['role'] == 'user':
            first_message = msg['content']
            break
    
    if not first_message:
        return "chat"
    
    # Extract repo name from any message containing a Git URL
    repo_name = None
    git_pat = re.compile(r"(https?://|git@)[\w\.\-@:/~]+?\.git", re.IGNORECASE)
    
    for msg in chat_history:
        if msg['role'] == 'user':
            match = git_pat.search(msg['content'])
            if match:
                url = match.group(0).strip()
                # Extract repo name from URL (e.g., vector_c from vector_c.git)
                repo_name = url.rstrip('.git').split('/')[-1]
                break
    
    # Detect test types from first message OR use selected types
    message_lower = first_message.lower()
    has_functional = 'functional' in message_lower
    has_unit = 'unit' in message_lower
    
    # If no test types mentioned in message, use selected types from sidebar
    if not has_functional and not has_unit and selected_test_types:
        has_functional = 'Functional Test' in selected_test_types
        has_unit = 'Unit Test' in selected_test_types
    
    # Generate appropriate name
    if repo_name:
        if has_functional and has_unit:
            return f"Functional and Unit test cases for {repo_name}"
        elif has_functional:
            return f"Functional test cases for {repo_name}"
        elif has_unit:
            return f"Unit test cases for {repo_name}"
        else:
            # Default if no specific test type mentioned but repo present
            return f"Test cases for {repo_name}"
    else:
        # No repo found, use generic naming from first message
        words = first_message.strip().split()
        name_words = words[:5]
        name = ' '.join(name_words)
        if len(words) > 5:
            name += "..."
        # Clean special characters
        name = ''.join(c if c.isalnum() or c == ' ' else '_' for c in name)
        return name[:50] if name else "chat"


def remove_test_cases_from_csv(csv_path, deleted_files=None, removed_functions=None, modified_files=None):
    """
    Remove test cases from CSV for:
    1. Deleted files (all tests for those files)
    2. Removed functions (specific tests for those functions)
    3. Modified files (all tests - will be regenerated)
    
    Returns: Path to cleaned CSV, count of removed tests, dict of removal breakdown
    """
    import csv as csv_module
    import tempfile
    
    if not deleted_files and not removed_functions and not modified_files:
        return csv_path, 0, {}
    
    deleted_files = deleted_files or []
    removed_functions = removed_functions or {}
    modified_files = modified_files or []
    
    # Read existing CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv_module.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)
    
    original_count = len(all_rows)
    filtered_rows = []
    
    # Prepare file names for comparison
    deleted_file_names = [Path(f).name for f in deleted_files] if deleted_files else []
    modified_file_names = [Path(f).name for f in modified_files] if modified_files else []
    
    removal_stats = {
        'deleted_files': 0,
        'modified_files': 0,
        'removed_functions': 0
    }
    
    for row in all_rows:
        # Get file name from various possible column names
        file_name = (
            Path(row.get('File', '')).name or
            Path(row.get('Source File', '')).name or
            Path(row.get('file', '')).name or
            Path(row.get('Target File', '')).name or
            ''
        )
        
        should_remove = False
        removal_reason = None
        
        # Check if file was deleted
        if file_name and file_name in deleted_file_names:
            logger.info(f"🗑️ Removing test for deleted file: {file_name}")
            should_remove = True
            removal_reason = 'deleted_file'
            removal_stats['deleted_files'] += 1
        
        # Check if file was modified (regenerate all tests for this file)
        elif file_name and file_name in modified_file_names:
            logger.info(f"🔄 Removing test for modified file (will regenerate): {file_name}")
            should_remove = True
            removal_reason = 'modified_file'
            removal_stats['modified_files'] += 1
        
        # Check if function was removed (only if file not already removed)
        elif not should_remove and removed_functions and file_name in removed_functions:
            # Get function/target name from test case
            target = (
                row.get('Target', '') or
                row.get('target', '') or
                row.get('Function', '') or
                row.get('function', '') or
                row.get('Test Name', '') or
                row.get('name', '') or
                row.get('Description', '') or
                row.get('description', '') or
                ''
            )
            
            # Check if this test is for a removed function
            for removed_func in removed_functions[file_name]:
                # Enhanced matching patterns
                target_lower = target.lower()
                removed_func_lower = removed_func.lower()
                
                # Multiple matching strategies
                match_patterns = [
                    removed_func in target,  # Exact match
                    removed_func_lower in target_lower,  # Case-insensitive
                    f"test_{removed_func_lower}" in target_lower,  # test_function pattern
                    f"{removed_func_lower}()" in target_lower,  # function() pattern
                    f"{removed_func_lower}_" in target_lower,  # function_ pattern
                    target_lower.startswith(removed_func_lower),  # Starts with function name
                    target_lower.endswith(removed_func_lower),  # Ends with function name
                ]
                
                if any(match_patterns):
                    logger.info(f"🗑️ Removing test for removed function: {removed_func} in {file_name}")
                    logger.info(f"   Matched test: {target}")
                    should_remove = True
                    removal_reason = 'removed_function'
                    removal_stats['removed_functions'] += 1
                    break
        
        if not should_remove:
            filtered_rows.append(row)
        else:
            # Debug logging
            logger.debug(f"Removed test: {file_name} - Reason: {removal_reason}")
    
    removed_count = original_count - len(filtered_rows)
    
    if removed_count == 0:
        logger.info("✅ No test cases needed to be removed")
        return csv_path, 0, removal_stats
    
    # Write filtered CSV to temp file
    temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
    writer = csv_module.DictWriter(temp_csv, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(filtered_rows)
    temp_csv.close()
    
    logger.info(f"✅ Removed {removed_count} test cases from CSV")
    logger.info(f"   Breakdown: {removal_stats}")
    
    return Path(temp_csv.name), removed_count, removal_stats


def normalize_change_info(change_info):
    """
    Normalize change_info to ensure it's a proper dictionary.
    Handles cases where git_handler returns a list or malformed data.
    """
    if isinstance(change_info, dict) and "has_changes" in change_info:
        return change_info
    
    if isinstance(change_info, list):
        logger.warning(f"⚠️ change_info is a list, converting to dict: {change_info}")
        return {
            "has_changes": True,
            "is_new_repo": False,
            "changed_files": change_info if change_info else [],
            "commit_info": {}
        }
    
    logger.warning(f"⚠️ Unexpected change_info type: {type(change_info)}, using defaults")
    return {
        "has_changes": True,
        "is_new_repo": True,
        "changed_files": [],
        "commit_info": {}
    }

def clear_session_context():
    """Clear all session context for a fresh start"""
    logger.info("🧹 Clearing session context")
    
    st.session_state.chat_history = []
    st.session_state.uploaded_files = {}
    st.session_state.previous_code = {}
    st.session_state.generated_tests = {}
    st.session_state.last_repo_info = {}
    st.session_state.pending_git = None
    st.session_state.current_repo_path = None
    st.session_state.current_repo_csv = {}
    st.session_state.current_chat_file = None
    
    try:
        if hasattr(st.session_state, "rag_system"):
            st.session_state.rag_system.code_documents = {}
            st.session_state.rag_system.test_cases = {}
            logger.info("✅ RAG system cleared")
    except Exception as e:
        logger.warning(f"⚠️ Error clearing RAG system: {e}")
    
    logger.info("✅ Session context cleared")


def has_context() -> bool:
    """Check if there's any context available"""
    # if st.session_state.uploaded_files:
    #     return True
    if st.session_state.current_repo_path:
        return True
    for message in st.session_state.chat_history:
        if message.get("role") == "assistant" and "test_results" in message:
            return True
    if st.session_state.rag_system.code_documents:
        return True
    return False


def auto_save_chat():
    """Auto-save chat after significant interactions"""
    if st.session_state.chat_history and len(st.session_state.chat_history) >= 2:
        selected_types = st.session_state.get('selected_test_types', ['Unit Test', 'Functional Test'])
        save_chat_history(selected_types)


def save_chat_history(selected_test_types: list = None):
    """Save chat history to file with smart naming"""
    if not st.session_state.chat_history:
        return None
    
    history_dir = Path("chat_history")
    history_dir.mkdir(exist_ok=True)
    
    # Generate smart name based on content and selected test types
    chat_name = generate_smart_chat_name(st.session_state.chat_history, selected_test_types)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = history_dir / f"{chat_name}_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(st.session_state.chat_history, f, indent=2)
    
    # Track current chat file for deletion
    st.session_state.current_chat_file = str(filename)
    
    logger.info(f"💾 Chat saved as: {chat_name}")
    
    return filename

def load_chat_history(filename):
    """Load chat history from file"""
    with open(filename, 'r') as f:
        return json.load(f)
    
def delete_chat_file(filepath):
    """Delete a chat file from disk"""
    try:
        Path(filepath).unlink()
        logger.info(f"🗑️ Deleted chat file: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error deleting chat file {filepath}: {e}")
        return False
# ---- Helper: change detection ---------------------------------------------------
def detect_code_changes(file_name, current_code):
    if file_name in st.session_state.previous_code:
        prev = st.session_state.previous_code[file_name]
        if prev != current_code:
            prev_lines = set(prev.split("\n"))
            cur_lines = set(current_code.split("\n"))
            added = cur_lines - prev_lines
            removed = prev_lines - cur_lines
            return {
                "changed": True,
                "added_lines": len(added),
                "removed_lines": len(removed),
                "added": list(added)[:5],
                "removed": list(removed)[:5],
            }
    return {"changed": False}


# ---- Helper: test display -------------------------------------------------------
def display_professional_test(test, index):
    test_id = test.get("test_case_id", test.get("name", f"TC-{index:03d}"))
    with st.container():
        st.markdown(f"### {test_id}")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**Description:** {test.get('description', 'N/A')}")
        with col2:
            pri = "High" if "Functional" in test.get("type", "") else "Medium"
            st.markdown(f"**Priority:** {pri}")
        st.markdown("**Target:** " + test.get("target", "N/A"))
        if test.get("file"):
            st.markdown("**File:** " + test.get("file", "N/A"))

        st.markdown("#### Steps")
        steps = test.get("steps", "N/A")
        if steps != "N/A":
            for s in steps.split("\n"):
                if s.strip():
                    st.markdown(f"- {s.strip()}")
        else:
            st.markdown("_No steps_")

        st.markdown("#### Expected Result")
        st.info(test.get("expected_result", "N/A"))
        st.divider()


def display_code_test(test, index):
    name = test.get("name", f"Test {index}")
    code = test.get("code", "No code")
    desc = test.get("description", "")
    file = test.get("file", "N/A")
    chunk = test.get("chunk_name", "N/A")
    st.markdown(f"**Test {index}:** {name}")
    st.caption(f"{file} | Chunk: {chunk}")
    if desc:
        st.caption(desc)
    st.code(code, language="python")


# ---- Sidebar --------------------------------------------------------
def display_sidebar():
    with st.sidebar:
        st.title("🧪 Test Generator")
        
        st.subheader("Test Case Types")
        test_types = st.multiselect(
            "Select test case types:",
            ["Unit Test", "Functional Test"],
            default=["Unit Test", "Functional Test"],
        )
        
        # Store in session state so it's accessible everywhere
        st.session_state.selected_test_types = test_types

        st.divider()
        
        # Chat history management
        st.subheader("💬 Chat History")
        
        if st.button("🆕 New", use_container_width=True, help="Start a new chat"):
            # Auto-save current chat before clearing
            if st.session_state.chat_history:
                auto_save_chat()
            clear_session_context()
            st.success("New chat started!")
            st.rerun()
        
        st.divider()
        
        # Display saved chats with individual delete buttons
        history_dir = Path("chat_history")
        if history_dir.exists():
            chat_files = sorted(history_dir.glob("*.json"), reverse=True)
            if chat_files:
                st.write("**Recent Chats:**")
                for chat_file in chat_files[:10]:
                    # Extract readable name from filename
                    name = chat_file.stem
                    # Remove timestamp if present
                    parts = name.rsplit('_', 2)  # Split from right to preserve underscores in name
                    if len(parts) >= 3:
                        display_name = parts[0]  # Everything before the timestamp
                    else:
                        display_name = name
                    
                    # Limit display name length
                    if len(display_name) > 35:
                        display_name = display_name[:35] + "..."
                    
                    # Create columns for chat button and delete button
                    col_chat, col_del = st.columns([4, 1])
                    
                    with col_chat:
                        if st.button(f"📄 {display_name}", key=f"load_{chat_file.name}", use_container_width=True):
                            st.session_state.chat_history = load_chat_history(chat_file)
                            st.session_state.current_chat_file = str(chat_file)
                            st.rerun()
                    
                    with col_del:
                        if st.button("🗑️", key=f"del_{chat_file.name}", help="Delete this chat"):
                            if delete_chat_file(chat_file):
                                st.success("Deleted!")
                                st.rerun()
                            else:
                                st.error("Failed!")
        
        return test_types

# ---- Unified Chat UI ------------------------------------------------------------
def display_chat():
    st.subheader("AI Test Case Generator")
    # Input section
    with st.container():
        #---------lld ui----------------
        user_input = st.chat_input("Ask, paste Git URL, upload LLD, or type 'generate'...")

        lld_file = st.file_uploader(
        "📄 Upload LLD Word Document (.docx)",
        type=["docx"],
        key="lld_uploader",
        label_visibility="collapsed",
        )

        if lld_file is not None:
            file_bytes = lld_file.read()
            filename = lld_file.name

            # Acknowledge upload in chat
            upload_msg = f"📄 LLD document uploaded: **{filename}**. Generating test cases..."
            st.session_state.chat_history.append(
                {"role": "user", "content": f"Uploaded LLD: {filename}", "timestamp": datetime.now().isoformat()}
            )
            with st.chat_message("user"):
                st.markdown(f"Uploaded LLD: **{filename}**")

            with st.chat_message("assistant"):
                with st.spinner("Reading LLD and generating test cases..."):
                    import time
                    start = time.time()

                    # Use the LLD handler
                    lld = st.session_state.lld_handler
                    test_types = st.session_state.get("selected_test_types", ["Unit Test", "Functional Test"])
                    tests = lld.process_lld_file(file_bytes, filename, test_types)

                    st.session_state.generated_tests = tests
                    st.session_state.rag_system.add_test_cases(tests, session_id="current")

                    unit_count = len(tests.get("Unit Test", []))
                    functional_count = len(tests.get("Functional Test", []))
                    total = unit_count + functional_count
                    elapsed = time.time() - start

                    st.success(f"Generated **{total}** test cases from LLD in {elapsed:.2f}s")

                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Total", total)
                    with c2: st.metric("Unit", unit_count)
                    with c3: st.metric("Functional", functional_count)

                    # Download buttons
                    csv_h = CSVHandler()
                    csv_file = csv_h.generate_csv_with_repo_name(
                        tests, filename.replace(".docx", ""), change_info={}
                    )
                    report_file = csv_h.generate_professional_test_report(tests)

                    d1, d2 = st.columns(2)
                    with d1:
                        with open(csv_file, "rb") as f:
                            st.download_button(
                                "📥 Download CSV", data=f,
                                file_name=f"lld_tests_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                mime="text/csv",
                            )
                    with d2:
                        with open(report_file, "rb") as f:
                            st.download_button(
                                "📥 Download Report", data=f,
                                file_name=f"lld_report_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                mime="text/plain",
                            )

                    # Show test preview
                    for ttype in test_types:
                        lst = tests.get(ttype, [])
                        if lst:
                            with st.expander(f"{ttype}s ({len(lst)})", expanded=True):
                                for i, t in enumerate(lst[:10], 1):
                                    if t.get("format") == "professional":
                                        display_professional_test(t, i)
                                    else:
                                        display_code_test(t, i)
                                if len(lst) > 10:
                                    st.info(f"... and {len(lst)-10} more (download CSV)")

                    # Save to chat history
                    bot_msg = (
                        f"✅ Generated **{total}** test cases from LLD **{filename}**\n"
                        f"- Unit Tests: {unit_count}\n"
                        f"- Functional Tests: {functional_count}\n"
                        f"- Time: {elapsed:.2f}s"
                    )
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": bot_msg, "timestamp": datetime.now().isoformat()}
                    )
                    auto_save_chat()
                    st.caption("💾 Chat auto-saved")

#---------lld ui end----------------

        uploaded_files = None  #newline to remove fileupld
        # uploaded_files = st.file_uploader(
        #     "Attach code files",
        #     accept_multiple_files=True,
        #     type=["py", "js", "java", "cpp", "c", "cs", "go", "rb", "php", "swift", "kt", "ts", "rs"],
        #     key="chat_uploader",
        #     label_visibility="collapsed",
        # )

    # Show chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Process uploaded files
    # if uploaded_files:
    #     names = []
    #     for uf in uploaded_files:
    #         try:
    #             txt = uf.read().decode("utf-8")
    #             changes = detect_code_changes(uf.name, txt)
    #             st.session_state.uploaded_files[uf.name] = txt
    #             st.session_state.previous_code[uf.name] = txt
    #             if changes["changed"]:
    #                 st.warning(f"Changes in **{uf.name}**")
    #                 with st.expander("View diff"):
    #                     st.write(f"+{changes['added_lines']}  -{changes['removed_lines']} lines")
    #                     if changes["added"]:
    #                         st.write("**Added:** " + ", ".join(changes["added"]))
    #                     if changes["removed"]:
    #                         st.write("**Removed:** " + ", ".join(changes["removed"]))
    #             lines = len(txt.splitlines())
    #             with st.expander(f"{uf.name} ({lines} lines)"):
    #                 st.code(txt[:1000], language="python")
    #                 if len(txt) > 1000:
    #                     st.caption(f"... ({len(txt)} chars total)")
    #             names.append(f"`{uf.name}`")
    #         except Exception as e:
    #             st.error(f"Error reading {uf.name}: {e}")
    #     if names:
    #         msg = f"Uploaded: {', '.join(names)}"
    #         st.session_state.chat_history.append(
    #             {"role": "user", "content": msg, "timestamp": datetime.now().isoformat()}
    #         )
    #         with st.chat_message("user"):
    #             st.markdown(msg)

    # Process text input
    if user_input:
        sanitized = st.session_state.security_manager.sanitize_input(user_input)
        st.session_state.chat_history.append(
            {"role": "user", "content": sanitized, "timestamp": datetime.now().isoformat()}
        )
        with st.chat_message("user"):
            st.markdown(sanitized)

        # Git URL detection
        git_pat = re.compile(r"(https?://|git@)[\w\.\-@:/~]+?\.git", re.IGNORECASE)
        m = git_pat.search(sanitized)
        if m:
            url = m.group(0).strip()
            
            # Save the current message before clearing (it contains the Git URL)
            git_url_message = st.session_state.chat_history[-1].copy()
            
            # Clear previous session context for fresh start
            clear_session_context()
            
            # Restore the Git URL message so it's the first message in the new chat
            st.session_state.chat_history.append(git_url_message)
            
            st.session_state.pending_git = {"url": url, "stage": "ask_branch"}
            bot = (
                f"Found repository: **{url}**\n"
                "Please tell me the **branch** (default: `main`):"
            )
            st.session_state.chat_history.append(
                {"role": "assistant", "content": bot, "timestamp": datetime.now().isoformat()}
            )
            with st.chat_message("assistant"):
                st.markdown(bot)
            return

        # Generate from uploaded files
        if "generate" in sanitized.lower() and st.session_state.uploaded_files:
            with st.chat_message("assistant"):
                with st.spinner("Generating tests from uploaded files..."):
                    start = time.time()
                    parser = CodeParser()
                    parsed = {
                        n: parser.parse_code(c, n)
                        for n, c in st.session_state.uploaded_files.items()
                    }
                    st.session_state.rag_system.add_code_documents(parsed)

                    gen = TestGenerator(st.session_state.llm_handler, st.session_state.rag_system)
                    tests = gen.generate_tests(parsed, test_types, module_level=True)
                    st.session_state.generated_tests = tests
                    st.session_state.rag_system.add_test_cases(tests, session_id="current")

                    # Count tests properly
                    unit_count = len(tests.get("Unit Test", []))
                    functional_count = len(tests.get("Functional Test", []))
                    total = unit_count + functional_count
                    elapsed = time.time() - start

                    st.success(f"Generated **{total}** tests in {elapsed:.2f}s")

                    # Metrics
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Total", total)
                    with c2: st.metric("Unit", unit_count)
                    with c3: st.metric("Functional", functional_count)

                    # Download buttons
                    csv_h = CSVHandler()
                    csv_file = csv_h.generate_csv(tests)
                    report_file = csv_h.generate_professional_test_report(tests)
                    d1, d2 = st.columns(2)
                    with d1:
                        with open(csv_file, "rb") as f:
                            st.download_button(
                                "📥 Download CSV", data=f,
                                file_name=f"tests_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                mime="text/csv",
                            )
                    with d2:
                        with open(report_file, "rb") as f:
                            st.download_button(
                                "📥 Download Report", data=f,
                                file_name=f"report_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                mime="text/plain",
                            )

                    # Show tests
                    for ttype in test_types:
                        lst = tests.get(ttype, [])
                        if lst:
                            with st.expander(f"{ttype}s ({len(lst)})", expanded=True):
                                for i, t in enumerate(lst[:10], 1):
                                    if t.get("format") == "professional":
                                        display_professional_test(t, i)
                                    else:
                                        display_code_test(t, i)
                                if len(lst) > 10:
                                    st.info(f"... and {len(lst)-10} more (download CSV)")

                    auto_save_chat()
                    st.caption("💾 Chat auto-saved")

            return

        # Check for pending Git flow
        if st.session_state.pending_git:
            pend = st.session_state.pending_git
            if pend["stage"] == "ask_branch":
                branch = sanitized.strip() or "main"
                pend["branch"] = branch
                pend["stage"] = "processing"

                bot = f"Understood. The branch `{branch}` has been selected. Will clone and generate test cases."
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": bot, "timestamp": datetime.now().isoformat()}
                )
                with st.chat_message("assistant"):
                    st.markdown(bot)
        
        # Normal LLM chat
        if not st.session_state.pending_git:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    ctx = st.session_state.rag_system.get_relevant_context(sanitized)
                    reply = st.session_state.llm_handler.generate_chat_response(
                        sanitized, ctx, st.session_state.chat_history
                    )
                    st.markdown(reply)
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": reply, "timestamp": datetime.now().isoformat()}
                    )

    if st.session_state.pending_git and user_input:
        pend = st.session_state.pending_git
        if pend["stage"] == "processing":
            with st.spinner("Cloning & analysing repository…"):
                try:
                    gh = GitHandler()
                    repo_path, _ = gh.clone_or_pull_repository(pend["url"], pend["branch"], depth=1)

                    # Parse all code files
                    code_files = gh.get_code_files(repo_path)
                    if not code_files:
                        st.error("No code files found in repository.")
                        st.session_state.pending_git = None
                        return

                    parser = CodeParser()
                    parsed = {}
                    prog = st.progress(0)
                    for i, fp in enumerate(code_files):
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                parsed[fp.name] = parser.parse_code(f.read(), fp.name)
                        except Exception as e:
                            logger.warning(f"Parse error {fp}: {e}")
                        prog.progress((i + 1) / len(code_files))
                    prog.empty()

                    # Add parsed code to RAG system
                    st.session_state.rag_system.add_code_documents(parsed)

                    # Generate tests
                    gen = TestGenerator(st.session_state.llm_handler, st.session_state.rag_system)
                    test_types = st.session_state.get("selected_test_types", ["Unit Test", "Functional Test"])
                    tests = gen.generate_tests(parsed, test_types, module_level=True)
                    st.session_state.generated_tests = tests
                    st.session_state.rag_system.add_test_cases(tests, session_id="current")

                    # Always generate a fresh CSV (ignore previous CSVs)
                    csv_h = CSVHandler()
                    csv_file = csv_h.generate_csv_with_repo_name(
                        tests, gh._sanitize_repo_name(pend["url"]), change_info={}
                    )
                    st.session_state.current_repo_csv[pend["url"]] = str(csv_file)

                    # Show download buttons
                    report_file = csv_h.generate_professional_test_report(tests)
                    d1, d2 = st.columns(2)
                    with d1:
                        with open(csv_file, "rb") as f:
                            st.download_button(
                                "📥 Download CSV", data=f,
                                file_name=f"tests_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                mime="text/csv",
                            )
                    with d2:
                        with open(report_file, "rb") as f:
                            st.download_button(
                                "📥 Download Report", data=f,
                                file_name=f"report_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                mime="text/plain",
                            )

                    # Display tests (optional, top 10)
                    for ttype in test_types:
                        lst = tests.get(ttype, [])
                        if lst:
                            with st.expander(f"{ttype}s ({len(lst)})", expanded=False):
                                for i, t in enumerate(lst[:10], 1):
                                    if t.get("format") == "professional":
                                        display_professional_test(t, i)
                                    else:
                                        display_code_test(t, i)
                                if len(lst) > 10:
                                    st.info(f"... and {len(lst)-10} more (download CSV)")

                    auto_save_chat()
                    st.caption("💾 Chat auto-saved")

                    st.session_state.pending_git = None

                except Exception as e:
                    st.error(f"Git processing failed: {e}")
                    logger.error(f"Git processing error details: {e}", exc_info=True)
                    st.session_state.pending_git = None


# ---- Main -----------------------------------------------------------------------
def main():
    global test_types
    test_types = display_sidebar()
    display_chat()


if __name__ == "__main__":
    main()