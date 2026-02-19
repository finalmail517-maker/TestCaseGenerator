from typing import Dict, List
from llm_handler import LLMHandler
from rag_system import RAGSystem
from code_chunker import CodeChunker
from logger import get_app_logger

logger = get_app_logger("test_generator")

class TestGenerator:
    """Generate unit and functional test cases using code chunking"""
    
    def __init__(self, llm_handler: LLMHandler, rag_system: RAGSystem):
        self.llm = llm_handler
        self.rag = rag_system
        self.chunker = CodeChunker(max_chunk_size=1500)
        logger.info("TestGenerator initialized (Unit & Functional tests only)")
    
    def generate_tests(
        self,
        parsed_data: Dict[str, Dict],
        test_types: List[str],
        module_level: bool = False
    ) -> Dict[str, List[Dict]]:
        """
        Generate test cases based on parsed code using chunking
        
        Args:
            parsed_data: Dictionary of parsed code files
            test_types: List of test types to generate (Unit Test, Functional Test)
            module_level: Whether to generate module-level tests
            
        Returns:
            Dictionary mapping test types to lists of test cases
        """
        logger.info(f"Starting test generation for types: {test_types}")
        logger.info(f"Module level: {module_level}")
        logger.info(f"Number of files: {len(parsed_data)}")
        
        all_tests = {
            'Unit Test': [],
            'Functional Test': []
        }
        
        # Generate unit tests
        if 'Unit Test' in test_types:
            logger.info("Generating unit tests with chunking...")
            try:
                all_tests['Unit Test'] = self._generate_unit_tests_chunked(parsed_data)
                logger.info(f"✅ Generated {len(all_tests['Unit Test'])} unit tests")
            except Exception as e:
                logger.error(f"Error generating unit tests: {e}", exc_info=True)
        
        # Generate functional tests
        if 'Functional Test' in test_types:
            logger.info("Generating functional tests with chunking...")
            try:
                all_tests['Functional Test'] = self._generate_functional_tests_chunked(
                    parsed_data,
                    module_level
                )
                logger.info(f"✅ Generated {len(all_tests['Functional Test'])} functional tests")
            except Exception as e:
                logger.error(f"Error generating functional tests: {e}", exc_info=True)
        
        # Log summary
        total = sum(len(tests) for tests in all_tests.values())
        logger.info("="*60)
        logger.info(f"TEST GENERATION COMPLETE: {total} total tests")
        for test_type, tests in all_tests.items():
            logger.info(f"  {test_type}: {len(tests)} tests")
        logger.info("="*60)
        
        return all_tests
    
    def _generate_unit_tests_chunked(self, parsed_data: Dict) -> List[Dict]:
        """Generate unit tests using code chunking"""
        logger.info("="*60)
        logger.info("UNIT TEST GENERATION")
        logger.info("="*60)
        
        all_unit_tests = []
        
        for filename, data in parsed_data.items():
            logger.info(f"\n📝 Processing file: {filename}")
            
            # Chunk the code
            chunks = self.chunker.chunk_code(data['code'], data)
            chunk_summary = self.chunker.get_chunk_summary(chunks)
            
            logger.info(f"Created {chunk_summary['total_chunks']} chunks:")
            for chunk_type, count in chunk_summary['by_type'].items():
                logger.info(f"  - {chunk_type}: {count}")
            
            # Generate tests for each chunk
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"  Chunk {i}/{len(chunks)}: {chunk['name']} ({chunk['type']})")
                
                try:
                    chunk_tests = self.llm.generate_tests_for_chunk(
                        chunk,
                        "Unit Test",
                        filename
                    )
                    
                    logger.info(f"    ✅ Generated {len(chunk_tests)} tests")
                    all_unit_tests.extend(chunk_tests)
                    
                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")
                    continue
        
        logger.info(f"\n📊 Total unit tests: {len(all_unit_tests)}")
        return all_unit_tests
    
    def _generate_functional_tests_chunked(self, parsed_data: Dict, module_level: bool) -> List[Dict]:
        """Generate functional tests using code chunking"""
        logger.info("="*60)
        logger.info("FUNCTIONAL TEST GENERATION")
        logger.info("="*60)
        logger.info(f"Module level: {module_level}")
        
        all_functional_tests = []
        
        if module_level:
            logger.info("📦 Generating MODULE-LEVEL functional tests")
            
            # Combine all files and chunk
            all_code = ""
            combined_data = {
                'language': 'unknown',
                'functions': [],
                'classes': [],
                'code': ''
            }
            
            for filename, data in parsed_data.items():
                all_code += f"\n\n# File: {filename}\n{data['code']}"
                combined_data['functions'].extend(data.get('functions', []))
                combined_data['classes'].extend(data.get('classes', []))
                if not combined_data['language'] or combined_data['language'] == 'unknown':
                    combined_data['language'] = data.get('language', 'unknown')
            
            combined_data['code'] = all_code
            
            # Chunk the combined code
            chunks = self.chunker.chunk_code(all_code, combined_data)
            logger.info(f"Created {len(chunks)} module chunks")
            
            # Generate functional tests for each chunk
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"  Module chunk {i}/{len(chunks)}: {chunk['name']}")
                
                try:
                    chunk_tests = self.llm.generate_tests_for_chunk(
                        chunk,
                        "Functional Test",
                        "module"
                    )
                    
                    # Mark as module-level tests
                    for test in chunk_tests:
                        test['scope'] = 'module'
                    
                    logger.info(f"    ✅ Generated {len(chunk_tests)} tests")
                    all_functional_tests.extend(chunk_tests)
                    
                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")
                    continue
        
        else:
            logger.info("📄 Generating FILE-LEVEL functional tests")
            
            # Process each file separately
            for filename, data in parsed_data.items():
                logger.info(f"\n📝 Processing file: {filename}")
                
                # Chunk the code
                chunks = self.chunker.chunk_code(data['code'], data)
                logger.info(f"Created {len(chunks)} chunks")
                
                # Generate functional tests for each chunk
                for i, chunk in enumerate(chunks, 1):
                    logger.info(f"  Chunk {i}/{len(chunks)}: {chunk['name']}")
                    
                    try:
                        chunk_tests = self.llm.generate_tests_for_chunk(
                            chunk,
                            "Functional Test",
                            filename
                        )
                        
                        # Mark as file-level tests
                        for test in chunk_tests:
                            test['scope'] = 'file'
                        
                        logger.info(f"    ✅ Generated {len(chunk_tests)} tests")
                        all_functional_tests.extend(chunk_tests)
                        
                    except Exception as e:
                        logger.error(f"    ❌ Error: {e}")
                        continue
        
        logger.info("="*60)
        logger.info(f"📊 Total functional tests: {len(all_functional_tests)}")
        logger.info("="*60)
        
        return all_functional_tests
    
    def generate_test_summary(self, all_tests: Dict) -> Dict:
        """Generate summary statistics for generated tests"""
        summary = {
            'total_tests': 0,
            'by_type': {},
            'by_file': {},
            'by_chunk': {},
            'coverage_estimate': 0
        }
        
        for test_type, tests in all_tests.items():
            summary['by_type'][test_type] = len(tests)
            summary['total_tests'] += len(tests)
            
            for test in tests:
                filename = test.get('file', 'unknown')
                summary['by_file'][filename] = summary['by_file'].get(filename, 0) + 1
                
                chunk_name = test.get('chunk_name', 'unknown')
                summary['by_chunk'][chunk_name] = summary['by_chunk'].get(chunk_name, 0) + 1
        
        # Calculate coverage estimate
        if summary['total_tests'] > 0:
            chunks_covered = len(summary['by_chunk'])
            summary['coverage_estimate'] = min(100, chunks_covered * 10 + summary['total_tests'] * 2)
        return summary