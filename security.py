"""
Security Manager with comprehensive input validation and logging
"""
import re
from typing import List, Dict, Tuple
from datetime import datetime
from pathlib import Path
from logger import get_app_logger

logger = get_app_logger("security")

class SecurityManager:
    """Manage security and input sanitization"""
    
    def __init__(self):
        logger.info(" Security Manager initialized")
        
        # Malicious patterns to detect
        self.malicious_patterns = [
            # SQL injection attempts
            r"(\bDROP\b|\bDELETE\b|\bINSERT\b|\bUPDATE\b).*\bTABLE\b",
            # Command injection
            r";\s*(rm|del|format|shutdown|reboot|wget|curl)",
            # Path traversal
            r"\.\./|\.\.\\",
            # Script injection
            r"<script[^>]*>.*?</script>",
            # System commands
            r"(eval|exec|system|subprocess\.call|os\.system)",
        ]
        
        # Non-testing keywords that should trigger warnings
        self.non_testing_keywords = [
            'hack', 'exploit', 'crack', 'bypass', 'malware',
            'virus', 'trojan', 'ddos', 'attack', 'phishing',
            'steal', 'fraud', 'scam', 'illegal', 'weapon'
        ]
        
        # Allowed testing-related keywords
        self.testing_keywords = [
            'test', 'testing', 'unit', 'regression', 'functional',
            'integration', 'assertion', 'mock', 'fixture', 'coverage',
            'debug', 'validate', 'verify', 'check', 'assert',
            'edge case', 'boundary', 'scenario', 'suite'
        ]
        
        # Maximum input length
        self.max_input_length = 10000
        
        # Security event counter
        self.security_events = {
            'malicious_patterns': 0,
            'invalid_queries': 0,
            'large_inputs': 0,
            'suspicious_code': 0
        }
    
    def sanitize_input(self, user_input: str) -> str:
        """
        Sanitize user input
        
        Args:
            user_input: Raw user input
            
        Returns:
            Sanitized input
        """
        original_length = len(user_input)
        
        # Check length
        if len(user_input) > self.max_input_length:
            logger.warning(f" Input exceeds maximum length: {len(user_input)} > {self.max_input_length}")
            user_input = user_input[:self.max_input_length]
            self.security_events['large_inputs'] += 1
        
        # Remove null bytes
        user_input = user_input.replace('\x00', '')
        
        # Remove excessive whitespace
        user_input = re.sub(r'\s+', ' ', user_input)
        
        # Remove control characters except newlines and tabs
        user_input = ''.join(
            char for char in user_input
            if char.isprintable() or char in '\n\t'
        )
        
        sanitized = user_input.strip()
        
        if len(sanitized) != original_length:
            logger.debug(f"🧹 Sanitized input: {original_length} → {len(sanitized)} chars")
        
        return sanitized
    
    def is_valid_test_query(self, query: str) -> bool:
        """
        Validate if query is related to test generation
        
        Args:
            query: User query
            
        Returns:
            True if valid test query, False otherwise
        """
        query_lower = query.lower()
        
        # Check for malicious patterns
        if self._contains_malicious_pattern(query):
            logger.warning(f" Malicious pattern detected in query: {query[:50]}...")
            self.security_events['malicious_patterns'] += 1
            self._log_security_event('malicious_pattern', query[:100])
            return False
        
        # Check for non-testing keywords
        found_bad_keywords = [kw for kw in self.non_testing_keywords if kw in query_lower]
        if found_bad_keywords:
            logger.warning(f" Suspicious keywords found: {', '.join(found_bad_keywords)}")
            self.security_events['invalid_queries'] += 1
            return False
        
        # Check if query contains testing-related keywords
        has_testing_keyword = any(
            keyword in query_lower
            for keyword in self.testing_keywords
        )
        
        # Additional patterns that indicate testing intent
        testing_patterns = [
            r'\btest\b',
            r'\bassert\b',
            r'\bcheck\b',
            r'\bvalidat',
            r'\bverif',
            r'how (to|do|can)',
            r'generate.*test',
            r'create.*test',
            r'write.*test',
            r'test.*case',
            r'code.*coverage',
            r'unit.*test',
            r'regression.*test',
            r'functional.*test'
        ]
        
        has_testing_pattern = any(
            re.search(pattern, query_lower)
            for pattern in testing_patterns
        )
        
        is_valid = has_testing_keyword or has_testing_pattern
        
        if not is_valid:
            logger.debug(f" Query does not appear to be test-related: {query[:50]}...")
        else:
            logger.debug(f" Valid test query detected")
        
        return is_valid
    
    def _contains_malicious_pattern(self, text: str) -> bool:
        """Check if text contains malicious patterns"""
        for pattern in self.malicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f" Malicious pattern matched: {pattern}")
                return True
        return False
    
    def validate_code_input(self, code: str) -> Tuple[bool, str]:
        """
        Validate uploaded code for security issues
        
        Args:
            code: Code content
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug(f" Validating code input ({len(code)} chars)")
        
        # Check for extremely long code
        if len(code) > 500000:  # 500KB
            logger.warning(" Code file is too large")
            return False, "Code file is too large (max 500KB)"
        
        # Check for malicious patterns
        if self._contains_malicious_pattern(code):
            logger.warning(" Code contains potentially malicious patterns")
            self.security_events['suspicious_code'] += 1
            return False, "Code contains potentially malicious patterns"
        
        # Check for suspicious imports (relaxed for legitimate code)
        suspicious_imports = [
            'os.system', 'subprocess.call', 'eval(', 'exec(',
            '__import__', 'compile('
        ]
        
        code_lower = code.lower()
        found_suspicious = [
            imp for imp in suspicious_imports
            if imp.lower() in code_lower
        ]
        
        if found_suspicious:
            logger.info(f"ℹ Code contains potentially dangerous functions: {', '.join(found_suspicious)}")
            return True, f"Warning: Code contains potentially dangerous functions: {', '.join(found_suspicious)}"
        
        logger.debug(" Code validation passed")
        return True, ""
    
    def validate_git_url(self, url: str) -> Tuple[bool, str]:
        """
        Validate Git repository URL
        
        Args:
            url: Git repository URL
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug(f" Validating Git URL: {url}")
        
        # Check for valid URL format
        git_url_patterns = [
            r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?\.git$',
            r'^https?://github\.com/[\w-]+/[\w.-]+/?$',
            r'^https?://gitlab\.com/[\w-]+/[\w.-]+/?$',
            r'^https?://bitbucket\.org/[\w-]+/[\w.-]+/?$',
        ]
        
        is_valid_format = any(re.match(pattern, url) for pattern in git_url_patterns)
        
        if not is_valid_format:
            logger.warning(f"⚠️ Invalid Git URL format: {url}")
            return False, "Invalid Git repository URL format"
        
        # Check for localhost or private IPs
        private_patterns = [
            r'localhost',
            r'127\.0\.0\.1',
            r'192\.168\.',
            r'10\.',
            r'172\.(1[6-9]|2[0-9]|3[0-1])\.'
        ]
        
        for pattern in private_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f" Attempted to access local/private repository: {url}")
                return False, "Cannot access local or private repositories"
        
        logger.debug(" Git URL validation passed")
        return True, ""
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe storage
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        original = filename
        
        # Remove directory traversal
        filename = filename.replace('..', '').replace('/', '_').replace('\\', '_')
        
        # Keep only alphanumeric, underscore, hyphen, and dot
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        if filename != original:
            logger.debug(f" Sanitized filename: {original} → {filename}")
        
        return filename
    
    def rate_limit_check(self, user_id: str, action: str) -> bool:
        """
        Simple rate limiting check
        
        Args:
            user_id: User identifier
            action: Action type
            
        Returns:
            True if within rate limits, False otherwise
        """
        # Placeholder - implement actual rate limiting with Redis or similar
        logger.debug(f" Rate limit check: user={user_id}, action={action}")
        return True
    
    def _log_security_event(self, event_type: str, details: str):
        """
        Log security events
        
        Args:
            event_type: Type of security event
            details: Event details
        """
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "security_events.log"
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details
        }
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f" Error logging security event: {e}")
    
    def get_safe_response_template(self) -> str:
        """Get template for safe rejection responses"""
        return """I can only assist with generating test cases for code.

I cannot help with:
- Writing production code (only test code)
- Security exploits or malicious activities
- Non-testing related programming tasks
- General questions unrelated to testing

Please ask questions related to:
- Test case generation
- Testing strategies and best practices
- Code analysis for testing purposes
- Test coverage and quality"""
    
    def get_security_statistics(self) -> Dict:
        """Get security event statistics"""
        stats = {
            'total_events': sum(self.security_events.values()),
            'by_type': self.security_events.copy(),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.debug(f" Security stats: {stats['total_events']} total events")
        
        return stats

# Required for security event logging
import json