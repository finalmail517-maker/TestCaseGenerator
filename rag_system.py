from typing import List, Dict, Optional
import json
from pathlib import Path
from datetime import datetime
import hashlib

class RAGSystem:
    """Enhanced RAG system for code context retrieval with test case storage"""
    
    def __init__(self):
        self.storage_dir = Path("rag_storage")
        self.storage_dir.mkdir(exist_ok=True)
        
        # In-memory storage for quick access
        self.code_documents = {}
        self.embeddings = {}
        self.metadata = {}
        
        # NEW: Storage for test cases
        self.test_cases_storage = {}
        self.test_summaries = {}
        
        # Load existing data
        self._load_storage()
    
    def add_test_cases(self, test_cases: Dict[str, List[Dict]], session_id: str = "current"):
        """
        Add generated test cases to RAG for context-aware queries
        
        Args:
            test_cases: Dictionary of test cases by type
            session_id: Identifier for this test generation session
        """
        self.test_cases_storage[session_id] = {
            'test_cases': test_cases,
            'timestamp': datetime.now().isoformat(),
            'summary': self._generate_test_summary(test_cases)
        }
        
        # Create embeddings for test queries
        self._index_test_cases(test_cases, session_id)
        
        # Save to disk
        self._save_storage()
    
    def _generate_test_summary(self, test_cases: Dict[str, List[Dict]]) -> Dict:
        """Generate detailed summary of test cases including edge cases"""
        summary = {
            'total_tests': 0,
            'by_type': {},
            'edge_cases': [],
            'boundary_conditions': [],
            'error_scenarios': [],
            'normal_cases': [],
            'integration_scenarios': [],
            'targets_covered': set(),
            'files_covered': set()
        }
        
        for test_type, tests in test_cases.items():
            summary['by_type'][test_type] = len(tests)
            summary['total_tests'] += len(tests)
            
            for test in tests:
                # Track coverage
                if test.get('target'):
                    summary['targets_covered'].add(test.get('target'))
                if test.get('file'):
                    summary['files_covered'].add(test.get('file'))
                
                # Categorize tests by their description
                desc = test.get('description', '').lower()
                name = test.get('name', '').lower()
                steps = test.get('steps', '').lower()
                code = test.get('code', '').lower()
                
                # Combine all text for analysis
                test_text = f"{desc} {name} {steps} {code}"
                
                # Identify edge cases
                edge_case_keywords = [
                    'edge', 'boundary', 'limit', 'maximum', 'minimum',
                    'empty', 'null', 'zero', 'negative', 'overflow',
                    'underflow', 'extreme', 'corner', 'special case'
                ]
                
                if any(keyword in test_text for keyword in edge_case_keywords):
                    summary['edge_cases'].append({
                        'test_id': test.get('test_case_id', test.get('name')),
                        'description': test.get('description', ''),
                        'type': test_type,
                        'target': test.get('target', 'N/A'),
                        'file': test.get('file', 'N/A')
                    })
                
                # Identify boundary conditions
                boundary_keywords = [
                    'boundary', 'limit', 'maximum', 'minimum', 'threshold',
                    'range', 'first', 'last', 'start', 'end'
                ]
                
                if any(keyword in test_text for keyword in boundary_keywords):
                    summary['boundary_conditions'].append({
                        'test_id': test.get('test_case_id', test.get('name')),
                        'description': test.get('description', ''),
                        'type': test_type
                    })
                
                # Identify error scenarios
                error_keywords = [
                    'error', 'exception', 'invalid', 'failure', 'reject',
                    'raise', 'throw', 'catch', 'handle', 'malformed'
                ]
                
                if any(keyword in test_text for keyword in error_keywords):
                    summary['error_scenarios'].append({
                        'test_id': test.get('test_case_id', test.get('name')),
                        'description': test.get('description', ''),
                        'type': test_type
                    })
                
                # Identify normal/happy path cases
                normal_keywords = [
                    'valid', 'normal', 'happy', 'success', 'correct',
                    'expected', 'typical', 'standard'
                ]
                
                if any(keyword in test_text for keyword in normal_keywords):
                    summary['normal_cases'].append({
                        'test_id': test.get('test_case_id', test.get('name')),
                        'description': test.get('description', ''),
                        'type': test_type
                    })
                
                # Identify integration scenarios
                integration_keywords = [
                    'integration', 'interact', 'combine', 'multiple',
                    'together', 'workflow', 'end-to-end', 'e2e'
                ]
                
                if any(keyword in test_text for keyword in integration_keywords):
                    summary['integration_scenarios'].append({
                        'test_id': test.get('test_case_id', test.get('name')),
                        'description': test.get('description', ''),
                        'type': test_type
                    })
        
        # Convert sets to lists for JSON serialization
        summary['targets_covered'] = list(summary['targets_covered'])
        summary['files_covered'] = list(summary['files_covered'])
        
        return summary
    
    def _index_test_cases(self, test_cases: Dict[str, List[Dict]], session_id: str):
        """Create searchable index of test cases"""
        # Store in session-specific key
        doc_id = f"tests_{session_id}"
        
        # Create searchable document
        all_tests_text = []
        for test_type, tests in test_cases.items():
            for test in tests:
                test_text = f"{test.get('name', '')} {test.get('description', '')} {test.get('steps', '')} {test_type}"
                all_tests_text.append(test_text)
        
        # Create embedding
        self.embeddings[doc_id] = self._create_simple_embedding({
            'language': 'test_cases',
            'code': ' '.join(all_tests_text),
            'functions': [],
            'classes': [],
            'imports': [],
            'filename': 'test_cases'
        })
    
    def get_test_context(self, query: str, session_id: str = "current") -> str:
        """
        Get relevant test context for a query
        
        Args:
            query: User query about tests
            session_id: Session identifier
            
        Returns:
            Formatted context about test cases
        """
        if session_id not in self.test_cases_storage:
            return "No test cases have been generated yet in this session."
        
        test_data = self.test_cases_storage[session_id]
        summary = test_data['summary']
        
        query_lower = query.lower()
        
        # Build context based on query
        context_parts = []
        
        # General test overview
        context_parts.append(
            f"Generated {summary['total_tests']} test cases covering:\n" +
            "\n".join([f"  - {test_type}: {count} tests" 
                      for test_type, count in summary['by_type'].items()])
        )
        
        # Edge cases query
        if any(word in query_lower for word in ['edge', 'edge case', 'corner', 'boundary']):
            if summary['edge_cases']:
                context_parts.append(f"\n**Edge Cases Covered ({len(summary['edge_cases'])} tests):**")
                for i, edge_case in enumerate(summary['edge_cases'][:10], 1):
                    context_parts.append(
                        f"{i}. {edge_case['test_id']}: {edge_case['description']}\n"
                        f"   Target: {edge_case['target']} | File: {edge_case['file']}"
                    )
                if len(summary['edge_cases']) > 10:
                    context_parts.append(f"... and {len(summary['edge_cases']) - 10} more edge case tests")
            else:
                context_parts.append("\n**Edge Cases:** No specific edge case tests were identified. Consider adding tests for boundary values, empty inputs, null values, and extreme values.")
        
        # Boundary conditions query
        if any(word in query_lower for word in ['boundary', 'limit', 'maximum', 'minimum']):
            if summary['boundary_conditions']:
                context_parts.append(f"\n**Boundary Conditions ({len(summary['boundary_conditions'])} tests):**")
                for i, boundary in enumerate(summary['boundary_conditions'][:5], 1):
                    context_parts.append(
                        f"{i}. {boundary['test_id']}: {boundary['description']}"
                    )
        
        # Error scenarios query
        if any(word in query_lower for word in ['error', 'exception', 'failure', 'invalid']):
            if summary['error_scenarios']:
                context_parts.append(f"\n**Error Scenarios ({len(summary['error_scenarios'])} tests):**")
                for i, error in enumerate(summary['error_scenarios'][:5], 1):
                    context_parts.append(
                        f"{i}. {error['test_id']}: {error['description']}"
                    )
        
        # Normal/happy path query
        if any(word in query_lower for word in ['normal', 'happy', 'valid', 'success']):
            if summary['normal_cases']:
                context_parts.append(f"\n**Normal/Happy Path Cases ({len(summary['normal_cases'])} tests):**")
                for i, normal in enumerate(summary['normal_cases'][:5], 1):
                    context_parts.append(
                        f"{i}. {normal['test_id']}: {normal['description']}"
                    )
        
        # Coverage query
        if any(word in query_lower for word in ['coverage', 'covered', 'target', 'function']):
            context_parts.append(f"\n**Coverage:**")
            context_parts.append(f"  - Functions/Classes Covered: {len(summary['targets_covered'])}")
            if summary['targets_covered']:
                targets_list = ', '.join(list(summary['targets_covered'])[:10])
                context_parts.append(f"  - Targets: {targets_list}")
            context_parts.append(f"  - Files Covered: {len(summary['files_covered'])}")
        
        # Integration scenarios
        if any(word in query_lower for word in ['integration', 'workflow', 'end-to-end']):
            if summary['integration_scenarios']:
                context_parts.append(f"\n**Integration Scenarios ({len(summary['integration_scenarios'])} tests):**")
                for i, integration in enumerate(summary['integration_scenarios'][:5], 1):
                    context_parts.append(
                        f"{i}. {integration['test_id']}: {integration['description']}"
                    )
        
        # If query is very general, provide overview
        if not any(word in query_lower for word in [
            'edge', 'boundary', 'error', 'normal', 'coverage', 'integration'
        ]):
            context_parts.append("\n**Test Breakdown:**")
            context_parts.append(f"  - Edge Cases: {len(summary['edge_cases'])}")
            context_parts.append(f"  - Boundary Conditions: {len(summary['boundary_conditions'])}")
            context_parts.append(f"  - Error Scenarios: {len(summary['error_scenarios'])}")
            context_parts.append(f"  - Normal Cases: {len(summary['normal_cases'])}")
            context_parts.append(f"  - Integration Tests: {len(summary['integration_scenarios'])}")
        
        return "\n".join(context_parts)
    
    def add_code_documents(self, parsed_data: Dict[str, Dict]):
        """
        Add code documents to RAG system
        
        Args:
            parsed_data: Dictionary of parsed code files
        """
        for filename, data in parsed_data.items():
            doc_id = self._generate_doc_id(filename, data['code'])
            
            # Store document
            self.code_documents[doc_id] = {
                'filename': filename,
                'code': data['code'],
                'language': data.get('language', 'unknown'),
                'functions': data.get('functions', []),
                'classes': data.get('classes', []),
                'imports': data.get('imports', []),
                'complexity': data.get('complexity', 'medium'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Create simple embeddings (keyword-based)
            self.embeddings[doc_id] = self._create_simple_embedding(data)
            
            # Store metadata
            self.metadata[doc_id] = {
                'filename': filename,
                'language': data.get('language', 'unknown'),
                'num_functions': len(data.get('functions', [])),
                'num_classes': len(data.get('classes', [])),
                'loc': data.get('lines_of_code', 0)
            }
        
        # Persist to disk
        self._save_storage()
    
    def get_relevant_context(
        self,
        query: str,
        max_results: int = 3,
        session_id: str = "current"
    ) -> str:
        """
        Get relevant code AND test context for a query
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            session_id: Current session ID
            
        Returns:
            Formatted context string
        """
        # Check if query is about tests
        test_keywords = [
            'test', 'edge', 'boundary', 'error', 'scenario',
            'coverage', 'case', 'generated', 'what tests'
        ]
        
        if any(keyword in query.lower() for keyword in test_keywords):
            # Get test context
            test_context = self.get_test_context(query, session_id)
            return test_context
        
        # Otherwise, get code context (original behavior)
        if not self.code_documents:
            return "No code context available."
        
        # Simple keyword matching
        query_keywords = self._extract_keywords(query.lower())
        
        # Score documents
        scores = {}
        for doc_id, embedding in self.embeddings.items():
            score = self._calculate_similarity(query_keywords, embedding)
            scores[doc_id] = score
        
        # Get top results
        sorted_docs = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_results]
        
        # Format context
        context_parts = []
        for doc_id, score in sorted_docs:
            if score > 0:  # Only include relevant results
                if doc_id in self.code_documents:
                    doc = self.code_documents[doc_id]
                    context_parts.append(
                        f"File: {doc['filename']}\n"
                        f"Language: {doc['language']}\n"
                        f"Functions: {', '.join([f['name'] for f in doc['functions'][:5]])}\n"
                        f"Classes: {', '.join([c['name'] for c in doc['classes'][:3]])}\n"
                        f"Code snippet:\n{doc['code'][:500]}...\n"
                    )
        
        return "\n---\n".join(context_parts) if context_parts else "No relevant context found."
    
    # Keep all existing methods...
    def get_code_versions(self, filename: str) -> List[Dict]:
        """Get all versions of a specific file"""
        versions = []
        
        for doc_id, doc in self.code_documents.items():
            if doc['filename'] == filename:
                versions.append(doc)
        
        versions.sort(key=lambda x: x['timestamp'], reverse=True)
        return versions
    
    def search_by_function(self, function_name: str) -> List[Dict]:
        """Search for documents containing a specific function"""
        results = []
        
        for doc_id, doc in self.code_documents.items():
            for func in doc['functions']:
                if function_name.lower() in func['name'].lower():
                    results.append({
                        'doc_id': doc_id,
                        'filename': doc['filename'],
                        'function': func
                    })
        
        return results
    
    def search_by_class(self, class_name: str) -> List[Dict]:
        """Search for documents containing a specific class"""
        results = []
        
        for doc_id, doc in self.code_documents.items():
            for cls in doc['classes']:
                if class_name.lower() in cls['name'].lower():
                    results.append({
                        'doc_id': doc_id,
                        'filename': doc['filename'],
                        'class': cls
                    })
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get RAG system statistics"""
        total_functions = sum(
            len(doc['functions'])
            for doc in self.code_documents.values()
        )
        
        total_classes = sum(
            len(doc['classes'])
            for doc in self.code_documents.values()
        )
        
        languages = set(
            doc['language']
            for doc in self.code_documents.values()
        )
        
        return {
            'total_documents': len(self.code_documents),
            'total_functions': total_functions,
            'total_classes': total_classes,
            'languages': list(languages),
            'storage_size': len(json.dumps(self.code_documents)),
            'total_test_sessions': len(self.test_cases_storage)
        }
    
    def _generate_doc_id(self, filename: str, code: str) -> str:
        """Generate unique document ID"""
        content = f"{filename}:{code}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _create_simple_embedding(self, data: Dict) -> Dict[str, int]:
        """Create simple keyword-based embedding"""
        keywords = {}
        
        # Extract keywords from filename
        filename_words = data.get('filename', '').replace('.', ' ').replace('_', ' ').split()
        for word in filename_words:
            keywords[word.lower()] = keywords.get(word.lower(), 0) + 2
        
        # Extract from function names
        for func in data.get('functions', []):
            name_parts = func.get('name', '').replace('_', ' ').split()
            for part in name_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 3
        
        # Extract from class names
        for cls in data.get('classes', []):
            name_parts = cls.get('name', '').replace('_', ' ').split()
            for part in name_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 3
        
        # Extract from imports
        for imp in data.get('imports', []):
            imp_parts = imp.replace('.', ' ').split()
            for part in imp_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 1
        
        # Add language
        keywords[data.get('language', 'unknown').lower()] = 5
        
        # Extract from code content (for test cases)
        if 'code' in data:
            code_words = data['code'].lower().split()
            for word in code_words[:100]:  # Limit to first 100 words
                if len(word) > 3:
                    keywords[word] = keywords.get(word, 0) + 1
        
        return keywords
    
    def _extract_keywords(self, text: str) -> Dict[str, int]:
        """Extract keywords from text"""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was',
            'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        words = text.lower().split()
        keywords = {}
        
        for word in words:
            word = ''.join(c for c in word if c.isalnum() or c == '_')
            
            if word and word not in stop_words and len(word) > 2:
                keywords[word] = keywords.get(word, 0) + 1
        
        return keywords
    
    def _calculate_similarity(
        self,
        query_keywords: Dict[str, int],
        doc_embedding: Dict[str, int]
    ) -> float:
        """Calculate simple similarity score"""
        score = 0.0
        
        for keyword, query_weight in query_keywords.items():
            if keyword in doc_embedding:
                score += query_weight * doc_embedding[keyword]
        
        return score
    
    def _save_storage(self):
        """Save RAG data to disk"""
        storage_file = self.storage_dir / "rag_data.json"
        
        data = {
            'code_documents': self.code_documents,
            'embeddings': self.embeddings,
            'metadata': self.metadata,
            'test_cases_storage': self.test_cases_storage,
            'test_summaries': self.test_summaries
        }
        
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _load_storage(self):
        """Load RAG data from disk"""
        storage_file = self.storage_dir / "rag_data.json"
        
        if storage_file.exists():
            try:
                with open(storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.code_documents =a.get('code_documents', {})
                self.embeddings = data.get('embeddings', {})
                self.metadata = data.get('metadata', {})
                self.test_cases_storage = data.get('test_cases_storage', {})
                self.test_summaries = data.get('test_summaries', {})
            except Exception:
                pass
    
    def clear_storage(self):
        """Clear all stored data"""
        self.code_documents = {}
        self.embeddings = {}
        self.metadata = {}
        self.test_cases_storage = {}
        self.test_summaries = {}
        self._save_storage()