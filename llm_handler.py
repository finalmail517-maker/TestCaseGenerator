"""
LLM Handler with Google LLM API integration
"""
import os
from typing import List, Dict, Optional
import json
import time
import google.generativeai as genai
from logger import get_app_logger
from config import config

logger = get_app_logger("llm_handler")

class LLMHandler:
    """Handler for LLM interactions using Google LLM"""
    
    def __init__(self):
        """Initialize LLM handler with LLM"""
        self.api_key = config.LLM_API_KEY
        self.model_name = config.LLM_MODEL
        
        if not self.api_key:
            logger.error("LLM API key not found!")
            raise ValueError("LLM_API_KEY not set in environment variables")
        
        # Configure LLM
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": config.LLM_TEMPERATURE,
                "max_output_tokens": config.LLM_MAX_TOKENS,
            }
        )
        
        logger.info(f"✅ LLM Handler initialized with LLM model: {self.model_name}")
        
        # System prompt
#         self.system_prompt = """You are a specialized AI assistant for test case generation ONLY.

# Generate comprehensive test cases.
# Always return: [{"name": "test_name", "description": "desc", "code": "test code", "target": "function_name"}]"""
#         self.system_prompt = """You are a specialized AI assistant for test case generation ONLY.

# YOUR SOLE PURPOSE: Generate unit tests and functional tests for code.

# STRICT BOUNDARIES:
# - You can ONLY discuss and help with: test case generation, testing strategies, code analysis for testing purposes, test coverage, and testing best practices.
# - You CANNOT: write production code (only test code), discuss non-testing topics, answer general questions, or perform any other tasks.
# - If asked about anything unrelated to test generation, respond: "I can only assist with generating test cases. Please ask questions related to test case generation, code analysis, or testing strategies."

# CAPABILITIES:
# - Analyze code structure and logic
# - Generate unit tests with assertions
# - Create regression tests for changed code
# - Design functional tests for features
# - Suggest edge cases and boundary conditions
# - Provide test coverage recommendations

# Always generate test cases that are:
# - Clear and well-documented
# - Follow testing best practices
# - Include proper assertions
# - Cover edge cases
# - Are maintainable and readable"""
        self.system_prompt="""You are a specialized AI assistant for test case generation.

Your purpose is to:
- Analyze code and generate unit, functional .
- Focus on testing strategies, edge cases, and best practices.

Strict Boundaries:
-Do not show anything internal and do not show test senario in the answer .
- You can only assist with generating test cases and related tasks.
- While not generating test cases then If asked about anything else, respond with: "I can only assist with generating test cases. Please ask questions related to test case generation."

Test case requirements:
- Well-documented, clear, and maintainable
- Proper assertions and edge cases
- Follow testing best practices"""



    def _make_request(self, prompt: str, context: str = "", max_retries: int = 3) -> str:
        """Make request to LLM API with retry logic"""
        
        full_prompt = f"{self.system_prompt}\n\n"
        
        if context:
            full_prompt += f"CONTEXT:\n{context}\n\n"
        
        full_prompt += f"USER REQUEST:\n{prompt}\n\nRESPONSE:"
        
        logger.info(f"📤 Making LLM API request...")
        logger.debug(f"Prompt length: {len(full_prompt)} characters")
        
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                response = self.model.generate_content(full_prompt)
                
                elapsed = time.time() - start_time
                
                if response.text:
                    logger.info(f"✅ LLM response received in {elapsed:.2f}s ({len(response.text)} chars)")
                    logger.debug(f"Response preview: {response.text[:200]}...")
                    return response.text
                else:
                    logger.warning(f"⚠️ Empty response from LLM (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return "Error: Empty response from LLM"
                    
            except Exception as e:
                logger.error(f"❌ LLM API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if "quota" in str(e).lower():
                    return "Error: API quota exceeded. Please check your LLM API usage."
                elif "api key" in str(e).lower():
                    return "Error: Invalid API key. Please check your LLM_API_KEY."
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
                return f"Error: {str(e)}"
        
        return "Error: Max retries exceeded"
    
    def generate_tests_for_chunk(
        self,
        chunk: Dict,
        test_type: str,
        file_name: str = ""
    ) -> List[Dict]:
        """Generate tests for a specific code chunk"""
        
        logger.info(f"🔧 Generating {test_type} for chunk: {chunk['name']} ({chunk['type']})")
        
        chunk_code = chunk['code']
        chunk_name = chunk['name']
        chunk_type = chunk['type']
        
        # Build prompt based on test type
        if test_type == "Unit Test":
            prompt = self._build_unit_test_prompt(chunk_code, chunk_name, chunk_type)
        elif test_type == "Functional Test":
            prompt = self._build_functional_test_prompt(chunk_code, chunk_name, chunk_type)
        # elif test_type == "Regression Test":
        #     prompt = self._build_regression_test_prompt(chunk_code, chunk_name, chunk_type)
        else:
            prompt = self._build_generic_test_prompt(chunk_code, chunk_name, test_type)
        
        response = self._make_request(prompt)
        
        if response.startswith("Error:"):
            logger.error(f"❌ LLM error for {chunk_name}: {response}")
            return self._generate_fallback_tests(chunk, test_type, file_name)
        
        tests = self._parse_test_response(response, test_type)
        
        # Add metadata
        for test in tests:
            test['file'] = file_name
            test['chunk_name'] = chunk_name
            test['chunk_type'] = chunk_type
            test['line_start'] = chunk.get('line_start', 0)
            test['line_end'] = chunk.get('line_end', 0)
        
        logger.info(f"✅ Generated {len(tests)} tests for chunk {chunk_name}")
        return tests
    
    def _build_unit_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for unit test generation"""
        
        if chunk_type == 'function':
            prompt = f"""Generate unit tests for this function.

FUNCTION: {chunk_name}
```
{code}
```

Generate 2-3 unit tests covering:
1. Normal/happy path
2. Edge cases
3. Error conditions if applicable

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        elif chunk_type == 'class':
            prompt = f"""Generate unit tests for this class.

CLASS: {chunk_name}
```
{code}
```

Generate 3-5 unit tests covering different methods and scenarios.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "method_name"}}]"""
        
        else:
            prompt = f"""Generate unit tests for this code.

CODE:
```
{code}
```

Generate 2-4 unit tests.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "general"}}]"""
        
        return prompt
    
    def _build_functional_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for functional test generation"""
        
        prompt = f"""Generate functional test cases for this code in PROFESSIONAL TEST CASE FORMAT.

{chunk_type.upper()}: {chunk_name}
```
{code}
```

Generate 3-5 functional test cases covering:
1. Valid/happy path scenarios
2. Invalid input scenarios
3. Edge cases
4. Error handling
5. Integration scenarios

Return test cases in this EXACT JSON format:
[
  {{
    "test_case_id": "TC-XXX-01",
    "description": "Brief description of what is being tested",
    "steps": "Step 1: Do something\\nStep 2: Do something else\\nStep 3: Verify result",
    "expected_result": "Detailed expected outcome of the test"
  }}
]

Return ONLY the JSON array, no other text."""
        
        return prompt
    
    def _build_regression_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for regression test generation"""
        
        prompt = f"""Generate regression tests for this code.

{chunk_type.upper()}: {chunk_name}
```
{code}
```

Generate 2-3 regression tests that ensure:
1. Existing functionality is preserved
2. No breaking changes
3. Backward compatibility

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        return prompt
    
    def _build_generic_test_prompt(self, code: str, chunk_name: str, test_type: str) -> str:
        """Build generic test prompt"""
        
        prompt = f"""Generate {test_type}s for this code.

CODE: {chunk_name}
```
{code}
```

Generate 2-3 {test_type.lower()}s.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        return prompt
    
    def _parse_test_response(self, response: str, test_type: str) -> List[Dict]:
        """Parse LLM response into structured test cases"""
        
        if not response or response.startswith("Error:"):
            logger.warning(f"⚠️ Empty or error response for {test_type}")
            return []
        
        try:
            # Try to extract JSON from response
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                tests = json.loads(json_str)
                
                # Validate and structure tests
                valid_tests = []
                for i, test in enumerate(tests):
                    if isinstance(test, dict):
                        if 'test_case_id' in test and test_type == 'Functional Test':
                            # Professional format
                            valid_test = {
                                'name': test.get('test_case_id', f'TC-FN-{i+1:02d}'),
                                'test_case_id': test.get('test_case_id', f'TC-FN-{i+1:02d}'),
                                'description': test.get('description', 'Test case'),
                                'steps': test.get('steps', 'No steps provided'),
                                'expected_result': test.get('expected_result', 'No expected result'),
                                'type': test_type,
                                'target': test.get('target', 'general'),
                                'format': 'professional'
                            }
                        else:
                            # Code format
                            valid_test = {
                                'name': test.get('name', f'{test_type.lower().replace(" ", "_")}_{i+1}'),
                                'description': test.get('description', 'Test case'),
                                'code': test.get('code', '# No code generated'),
                                'type': test_type,
                                'target': test.get('target', 'general'),
                                'format': 'code'
                            }
                        valid_tests.append(valid_test)
                
                if valid_tests:
                    logger.info(f"✅ Parsed {len(valid_tests)} tests from JSON")
                    return valid_tests
            
            # Fallback to plain text parsing
            logger.info("⚠️ Attempting plain text parsing")
            return self._parse_plain_text_tests(response, test_type)
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            return self._parse_plain_text_tests(response, test_type)
        except Exception as e:
            logger.error(f"❌ Error parsing test response: {e}", exc_info=True)
            return []
    
    def _parse_plain_text_tests(self, response: str, test_type: str) -> List[Dict]:
        """Parse plain text response into test cases"""
        import re
        
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL)
        
        if code_blocks:
            logger.info(f"📝 Found {len(code_blocks)} code blocks")
            tests = []
            for i, code in enumerate(code_blocks, 1):
                tests.append({
                    'name': f'{test_type.lower().replace(" ", "_")}_{i}',
                    'description': f'Generated {test_type}',
                    'code': code.strip(),
                    'type': test_type,
                    'target': 'general',
                    'format': 'code'
                })
            return tests
        
        return []
    
    def _generate_fallback_tests(self, chunk: Dict, test_type: str, file_name: str) -> List[Dict]:
        """Generate fallback tests when LLM fails"""
        logger.warning(f"⚠️ Generating fallback tests for {chunk['name']}")
        
        chunk_name = chunk['name']
        chunk_type = chunk['type']
        
        if test_type == "Functional Test":
            return [{
                'name': f'TC-FN-01',
                'test_case_id': f'TC-FN-01',
                'description': f'Functional test for {chunk_name} ({chunk_type})',
                'steps': f'Step 1: Initialize {chunk_name}\nStep 2: Execute main functionality\nStep 3: Verify expected behavior',
                'expected_result': f'{chunk_name} should execute successfully and return expected output',
                'type': test_type,
                'target': chunk_name,
                'file': file_name,
                'fallback': True,
                'format': 'professional'
            }]
        else:
            test_name = f"test_{chunk_name}_{test_type.lower().replace(' ', '_')}"
            return [{
                'name': test_name,
                'description': f'{test_type} for {chunk_name} (fallback)',
                'code': f"""def {test_name}():
    \"\"\"
    {test_type} for {chunk_name} ({chunk_type})
    File: {file_name}
    
    TODO: LLM generation failed. Implement test manually.
    \"\"\"
    pass""",
                'type': test_type,
                'target': chunk_name,
                'file': file_name,
                'fallback': True,
                'format': 'code'
            }]
    

    def generate_chat_response(
        self,
        user_message: str,
        context: str = "",
        chat_history: List[Dict] = None
    ) -> str:
        """Generate response for chat interface"""
        
        logger.info(f"💬 Generating chat response for: {user_message[:50]}...")
        
        # Build conversation context
        history_text = ""
        if chat_history:
            history_text = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in chat_history[-5:]  # Last 5 messages
            ])
        
        # Updated system prompt to request plain text output
        prompt = f"""You are a helpful AI assistant for test case generation.

    Previous conversation:
    {history_text}

    Context (if any):
    {context}
    
    Current question: {user_message}

    Provide a clear, helpful response focused on test case generation, code analysis, or testing strategies.
    Respond in plain text, without using structured formats like JSON, unless specifically requested."""
        
        # Make the request to the model
        response = self._make_request(prompt)
        logger.info(f"✅ Chat response generated ({len(response)} chars)")
        
        return response
