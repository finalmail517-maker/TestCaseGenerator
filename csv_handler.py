import csv
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json
class CSVHandler:
    """Handle CSV export of test cases with support for different formats and incremental updates"""
    def __init__(self):
        self.output_dir = Path("test_outputs")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_csv_with_repo_name(
        self,
        test_cases: Dict[str, List[Dict]],
        repo_name: str,
        change_info: Optional[Dict] = None
    ) -> Path:
        """
        Generate CSV file from test cases with repository name
        
        Args:
            test_cases: Dictionary of test cases by type
            repo_name: Name of repository
            change_info: Information about code changes
            
        Returns:
            Path to generated CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"test_cases_{repo_name}_{timestamp}.csv"
        
        # Check if we have professional format functional tests
        has_professional_format = any(
            test.get('format') == 'professional' 
            for tests in test_cases.values() 
            for test in tests
        )
        
        if has_professional_format:
            return self._generate_professional_csv(test_cases, csv_file, change_info)
        else:
            return self._generate_standard_csv(test_cases, csv_file, change_info)
    
    def append_to_previous_csv(
        self,
        previous_csv: Path,
        new_test_cases: Dict[str, List[Dict]],
        change_info: Dict
    ) -> Path:
        """
        Append new test cases to previous CSV file
        
        Args:
            previous_csv: Path to previous CSV file
            new_test_cases: New test cases to append
            change_info: Information about what changed
            
        Returns:
            Path to updated CSV file
        """
        # Create new file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = previous_csv.stem
        new_csv = self.output_dir / f"{base_name}_updated_{timestamp}.csv"
        
        # Read previous tests
        previous_tests = []
        try:
            with open(previous_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                previous_tests = list(reader)
        except Exception as e:
            print(f"Error reading previous CSV: {e}")
            # If we can't read previous, just create new file
            return self.generate_csv(new_test_cases)
        
        # Determine format from first row
        if previous_tests and 'Test Case ID' in previous_tests[0]:
            # Professional format
            return self._append_professional_csv(
                previous_tests,
                new_test_cases,
                new_csv,
                change_info
            )
        else:
            # Standard format
            return self._append_standard_csv(
                previous_tests,
                new_test_cases,
                new_csv,
                change_info
            )
    
    def generate_no_changes_report(
        self,
        previous_csv: Path,
        repo_name: str,
        commit_info: Dict
    ) -> Path:
        """
        Generate a report stating no changes detected
        
        Args:
            previous_csv: Path to previous CSV file
            repo_name: Repository name
            commit_info: Commit information
            
        Returns:
            Path to report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"no_changes_report_{repo_name}_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TEST GENERATION REPORT - NO CHANGES DETECTED\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Repository: {repo_name}\n")
            f.write(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Current commit: {commit_info.get('hash', 'unknown')}\n")
            f.write(f"Commit message: {commit_info.get('message', 'unknown')}\n")
            f.write(f"Author: {commit_info.get('author', 'unknown')}\n")
            f.write(f"Date: {commit_info.get('date', 'unknown')}\n\n")
            f.write("=" * 80 + "\n")
            f.write("STATUS: No code changes detected since last test generation.\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Previous test cases are still valid and can be found at:\n")
            f.write(f"{previous_csv}\n\n")
            f.write("No new test cases were generated.\n")
            f.write("The code is up-to-date with the last test suite.\n")
        
        return report_file
    
    def _append_professional_csv(
        self,
        previous_tests: List[Dict],
        new_test_cases: Dict[str, List[Dict]],
        csv_file: Path,
        change_info: Dict
    ) -> Path:
        """Append new tests in professional format"""
        functional_headers = [
            'Test Case ID',
            'Test Type',
            'Description',
            'Steps',
            'Expected Result',
            'Target Function/Class',
            'Source File',
            'Priority',
            'Status',
            'Created Date',
            'Change Type'
        ]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=functional_headers)
            writer.writeheader()
            
            # Write previous tests (mark as existing)
            for test in previous_tests:
                test['Change Type'] = 'Existing'
                writer.writerow(test)
            
            # Write new tests (mark with change type)
            test_id_counter = {'Unit Test': len([t for t in previous_tests if t.get('Test Type') == 'Unit Test']) + 1,
                             'Regression Test': len([t for t in previous_tests if t.get('Test Type') == 'Regression Test']) + 1,
                             'Functional Test': len([t for t in previous_tests if t.get('Test Type') == 'Functional Test']) + 1}
            
            for test_type, tests in new_test_cases.items():
                for test in tests:
                    # Determine change type
                    change_type = 'New'
                    if test.get('file') in change_info.get('modified_files', []):
                        change_type = 'Modified File'
                    elif test.get('file') in change_info.get('new_files', []):
                        change_type = 'New File'
                    
                    if test.get('format') == 'professional':
                        row = {
                            'Test Case ID': test.get('test_case_id', test.get('name', f'TC-{test_id_counter[test_type]:03d}')),
                            'Test Type': test_type,
                            'Description': test.get('description', ''),
                            'Steps': test.get('steps', 'N/A'),
                            'Expected Result': test.get('expected_result', 'N/A'),
                            'Target Function/Class': test.get('target', 'N/A'),
                            'Source File': test.get('file', 'N/A'),
                            'Priority': self._get_priority(test_type, test),
                            'Status': 'Not Executed',
                            'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'Change Type': change_type
                        }
                    else:
                        row = {
                            'Test Case ID': f'TC-{test_type[:3].upper()}-{test_id_counter[test_type]:02d}',
                            'Test Type': test_type,
                            'Description': test.get('description', ''),
                            'Steps': self._code_to_steps(test.get('code', '')),
                            'Expected Result': f'Test passes without errors. Expected behavior validated.',
                            'Target Function/Class': test.get('target', 'N/A'),
                            'Source File': test.get('file', 'N/A'),
                            'Priority': self._get_priority(test_type, test),
                            'Status': 'Not Executed',
                            'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'Change Type': change_type
                        }
                    
                    writer.writerow(row)
                    test_id_counter[test_type] += 1
        
        return csv_file
    
    def _append_standard_csv(
        self,
        previous_tests: List[Dict],
        new_test_cases: Dict[str, List[Dict]],
        csv_file: Path,
        change_info: Dict
    ) -> Path:
        """Append new tests in standard format"""
        headers = [
            'Test ID',
            'Test Type',
            'Test Name',
            'Description',
            'Target Function/Class',
            'Source File',
            'Test Code',
            'Priority',
            'Status',
            'Created Date',
            'Change Type'
        ]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            # Write previous tests
            for test in previous_tests:
                test['Change Type'] = 'Existing'
                writer.writerow(test)
            
            # Write new tests
            test_id = len(previous_tests) + 1
            
            for test_type, tests in new_test_cases.items():
                for test in tests:
                    # Determine change type
                    change_type = 'New'
                    if test.get('file') in change_info.get('modified_files', []):
                        change_type = 'Modified File'
                    elif test.get('file') in change_info.get('new_files', []):
                        change_type = 'New File'
                    
                    row = {
                        'Test ID': f"TC{test_id:04d}",
                        'Test Type': test_type,
                        'Test Name': test.get('name', f'Test_{test_id}'),
                        'Description': test.get('description', ''),
                        'Target Function/Class': test.get('target', 'N/A'),
                        'Source File': test.get('file', 'N/A'),
                        'Test Code': self._format_code_for_csv(test.get('code', '')),
                        'Priority': self._get_priority(test_type, test),
                        'Status': 'Not Executed',
                        'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Change Type': change_type
                    }
                    
                    writer.writerow(row)
                    test_id += 1
        
        return csv_file
    
    # Keep all existing methods from original CSVHandler...
    def generate_csv(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """
        Generate CSV file from test cases
        
        Args:
            test_cases: Dictionary of test cases by type
            
        Returns:
            Path to generated CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"test_cases_{timestamp}.csv"
        has_professional_format = any(
            test.get('format') == 'professional' 
            for tests in test_cases.values() 
            for test in tests
        )
        
        if has_professional_format:
            return self._generate_professional_csv(test_cases, csv_file)
        else:
            return self._generate_standard_csv(test_cases, csv_file)
    
    def _generate_professional_csv(
        self,
        test_cases: Dict[str, List[Dict]],
        csv_file: Path,
        change_info: Optional[Dict] = None
    ) -> Path:
        """Generate CSV with professional test case format"""
        functional_headers = [
            'Test Case ID',
            'Test Type',
            'Description',
            'Steps',
            'Expected Result',
            'Target Function/Class',
            'Source File',
            'Priority',
            'Status',
            'Created Date'
        ]
        
        if change_info:
            functional_headers.append('Change Type')
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=functional_headers)
            writer.writeheader()
            
            test_id_counter = {'Unit Test': 1, 'Regression Test': 1, 'Functional Test': 1}
            
            for test_type, tests in test_cases.items():
                for test in tests:
                    if test.get('format') == 'professional':
                        row = {
                            'Test Case ID': test.get('test_case_id', test.get('name', f'TC-{test_id_counter[test_type]:03d}')),
                            'Test Type': test_type,
                            'Description': test.get('description', ''),
                            'Steps': test.get('steps', 'N/A'),
                            'Expected Result': test.get('expected_result', 'N/A'),
                            'Target Function/Class': test.get('target', 'N/A'),
                            'Source File': test.get('file', 'N/A'),
                            'Priority': self._get_priority(test_type, test),
                            'Status': 'Not Executed',
                            'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    else:
                        row = {
                            'Test Case ID': f'TC-{test_type[:3].upper()}-{test_id_counter[test_type]:02d}',
                            'Test Type': test_type,
                            'Description': test.get('description', ''),
                            'Steps': self._code_to_steps(test.get('code', '')),
                            'Expected Result': f'Test passes without errors. Expected behavior validated.',
                            'Target Function/Class': test.get('target', 'N/A'),
                            'Source File': test.get('file', 'N/A'),
                            'Priority': self._get_priority(test_type, test),
                            'Status': 'Not Executed',
                            'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    if change_info:
                        row['Change Type'] = 'New'
                    
                    writer.writerow(row)
                    test_id_counter[test_type] += 1
        
        return csv_file
    
    def _generate_standard_csv(
        self,
        test_cases: Dict[str, List[Dict]],
        csv_file: Path,
        change_info: Optional[Dict] = None
    ) -> Path:
        """Generate standard CSV with code-based tests"""
        headers = [
            'Test ID',
            'Test Type',
            'Test Name',
            'Description',
            'Target Function/Class',
            'Source File',
            'Test Code',
            'Priority',
            'Status',
            'Created Date'
        ]
        
        if change_info:
            headers.append('Change Type')
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            test_id = 1
            
            for test_type, tests in test_cases.items():
                for test in tests:
                    row = {
                        'Test ID': f"TC{test_id:04d}",
                        'Test Type': test_type,
                        'Test Name': test.get('name', f'Test_{test_id}'),
                        'Description': test.get('description', ''),
                        'Target Function/Class': test.get('target', 'N/A'),
                        'Source File': test.get('file', 'N/A'),
                        'Test Code': self._format_code_for_csv(test.get('code', '')),
                        'Priority': self._get_priority(test_type, test),
                        'Status': 'Not Executed',
                        'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if change_info:
                        row['Change Type'] = 'New'
                    
                    writer.writerow(row)
                    test_id += 1
        
        return csv_file
    
    def _code_to_steps(self, code: str) -> str:
        """Convert test code to test steps"""
        if not code or code == '# No code generated':
            return 'Step 1: Execute test\nStep 2: Verify results'
        
        lines = code.split('\n')
        steps = []
        step_num = 1
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') and len(line) > 2:
                steps.append(f"Step {step_num}: {line[1:].strip()}")
                step_num += 1
            elif 'assert' in line.lower():
                steps.append(f"Step {step_num}: Verify {line}")
                step_num += 1
        
        if not steps:
            return 'Step 1: Execute test function\nStep 2: Verify expected behavior\nStep 3: Check for errors'
        
        return '\n'.join(steps[:5])
    
    def _get_priority(self, test_type: str, test: Dict) -> str:
        """Determine test priority"""
        if test_type == "Unit Test":
            return "High"
        elif test_type == "Regression Test":
            if test.get('changes', {}).get('has_changes'):
                return "Critical"
            return "High"
        elif test_type == "Functional Test":
            if test.get('scope') == 'module':
                return "Medium"
            return "High"
        
        return "Medium"
    
    def _format_code_for_csv(self, code: str) -> str:
        """Format code for CSV (escape quotes, limit length)"""
        code = code.replace('"', "'")
        
        max_length = 5000
        if len(code) > max_length:
            code = code[:max_length] + "\n... (truncated)"
        
        return code
    
    def generate_professional_test_report(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Generate a detailed professional test case document"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"test_cases_report_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TEST CASES SPECIFICATION DOCUMENT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for test_type, tests in test_cases.items():
                if not tests:
                    continue
                
                f.write(f"\n{'=' * 80}\n")
                f.write(f"{test_type.upper()}S ({len(tests)} test cases)\n")
                f.write(f"{'=' * 80}\n\n")
                
                for i, test in enumerate(tests, 1):
                    if test.get('format') == 'professional':
                        f.write(f"Test Case ID: {test.get('test_case_id', test.get('name'))}\n")
                        f.write(f"Description: {test.get('description', 'N/A')}\n")
                        f.write(f"Target: {test.get('target', 'N/A')}\n")
                        f.write(f"File: {test.get('file', 'N/A')}\n\n")
                        
                        f.write("Steps:\n")
                        steps = test.get('steps', 'N/A')
                        if steps != 'N/A':
                            for step in steps.split('\n'):
                                f.write(f"  {step}\n")
                        else:
                            f.write("  N/A\n")
                        f.write("\n")
                        
                        f.write("Expected Result:\n")
                        f.write(f"  {test.get('expected_result', 'N/A')}\n")
                    else:
                        f.write(f"Test {i}: {test.get('name', 'Unnamed')}\n")
                        f.write(f"Description: {test.get('description', 'N/A')}\n")
                        f.write(f"Target: {test.get('target', 'N/A')}\n")
                        f.write(f"File: {test.get('file', 'N/A')}\n")
                        f.write(f"\nCode:\n{'-' * 40}\n")
                        f.write(test.get('code', 'No code available'))
                        f.write(f"\n{'-' * 40}\n")
                    
                    f.write("\n" + "-" * 80 + "\n\n")
        
        return report_file
    
    def cleanup_old_files(self, days: int = 7):
        """Clean up old test output files"""
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        for file in self.output_dir.glob("*"):
            if file.is_file() and file.stat().st_mtime < cutoff_time:
                file.unlink()