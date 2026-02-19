"""
Enhanced Universal Code Parser with comprehensive multi-language support
"""
import ast
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from logger import get_app_logger

logger = get_app_logger("code_parser")

class CodeParser:
    """Parse and analyze code files across multiple programming languages"""
    
    def __init__(self):
        self.language_patterns = {
            'python': r'\.py$',
            'javascript': r'\.js$',
            'jsx': r'\.jsx$',
            'typescript': r'\.ts$',
            'tsx': r'\.tsx$',
            'java': r'\.java$',
            'cpp': r'\.(cpp|cc|cxx|hpp|h\+\+)$',
            'c': r'\.(c|h)$',
            'csharp': r'\.cs$',
            'go': r'\.go$',
            'rust': r'\.rs$',
            'ruby': r'\.rb$',
            'php': r'\.php$',
            'swift': r'\.swift$',
            'kotlin': r'\.(kt|kts)$',
            'scala': r'\.scala$',
            'r': r'\.(r|R)$',
            'matlab': r'\.m$',
        }
        
        logger.info("✅ Enhanced Universal CodeParser initialized with support for 15+ languages")
    
    def detect_language(self, filename: str) -> str:
        """Detect programming language from filename"""
        filename_lower = filename.lower()
        
        for lang, pattern in self.language_patterns.items():
            if re.search(pattern, filename_lower, re.IGNORECASE):
                logger.debug(f"🔍 Detected language: {lang} for {filename}")
                return lang
        
        logger.debug(f"⚠️ Unknown language for {filename}")
        return 'unknown'
    
    def parse_code(self, code: str, filename: str) -> Dict:
        """Parse code and extract structure"""
        logger.info(f"📝 Parsing code file: {filename}")
        
        language = self.detect_language(filename)
        
        parsed_data = {
            'filename': filename,
            'language': language,
            'code': code,
            'functions': [],
            'classes': [],
            'imports': [],
            'interfaces': [],
            'enums': [],
            'structs': [],
            'namespaces': [],
            'complexity': 'medium',
            'lines_of_code': len(code.split('\n'))
        }
        
        # Language-specific parsing with error handling
        try:
            if language == 'python':
                parsed_data.update(self._parse_python(code))
            elif language in ['javascript', 'jsx']:
                parsed_data.update(self._parse_javascript(code))
            elif language in ['typescript', 'tsx']:
                parsed_data.update(self._parse_typescript(code))
            elif language == 'java':
                parsed_data.update(self._parse_java(code))
            elif language == 'cpp':
                parsed_data.update(self._parse_cpp(code))
            elif language == 'c':
                parsed_data.update(self._parse_c(code))
            elif language == 'csharp':
                parsed_data.update(self._parse_csharp(code))
            elif language == 'go':
                parsed_data.update(self._parse_go(code))
            elif language == 'rust':
                parsed_data.update(self._parse_rust(code))
            elif language == 'ruby':
                parsed_data.update(self._parse_ruby(code))
            elif language == 'php':
                parsed_data.update(self._parse_php(code))
            elif language == 'swift':
                parsed_data.update(self._parse_swift(code))
            elif language == 'kotlin':
                parsed_data.update(self._parse_kotlin(code))
            else:
                parsed_data.update(self._parse_generic(code))
        except Exception as e:
            logger.error(f"❌ Error parsing {filename}: {e}", exc_info=True)
            parsed_data['parse_error'] = str(e)
        
        # Calculate complexity
        parsed_data['complexity'] = self._calculate_complexity(parsed_data)
        
        logger.info(f"✅ Parsed {filename}: "
                   f"{len(parsed_data['functions'])} functions, "
                   f"{len(parsed_data['classes'])} classes, "
                   f"{len(parsed_data.get('interfaces', []))} interfaces")
        
        return parsed_data
    
    # ==================== PYTHON PARSER ====================
    
    def _parse_python(self, code: str) -> Dict:
        """Parse Python code using AST (most accurate)"""
        result = {
            'functions': [],
            'classes': [],
            'imports': [],
            'decorators': []
        }
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Functions
                if isinstance(node, ast.FunctionDef):
                    result['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node),
                        'decorators': [d.id for d in node.decorator_list if hasattr(d, 'id')],
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    })
                
                # Classes
                elif isinstance(node, ast.ClassDef):
                    methods = [
                        n.name for n in node.body 
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    result['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods,
                        'docstring': ast.get_docstring(node),
                        'bases': [self._get_name(base) for base in node.bases],
                        'decorators': [d.id for d in node.decorator_list if hasattr(d, 'id')]
                    })
                
                # Imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result['imports'].append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        result['imports'].append(f"{module}.{alias.name}" if module else alias.name)
        
        except SyntaxError as e:
            logger.warning(f"⚠️ Python syntax error: {e}")
            result['parse_error'] = str(e)
        
        return result
    
    # ==================== JAVASCRIPT PARSER ====================
    
    def _parse_javascript(self, code: str) -> Dict:
        """Enhanced JavaScript parser"""
        result = {
            'functions': [],
            'classes': [],
            'imports': [],
            'exports': []
        }
        
        # Regular functions
        func_patterns = [
            r'function\s+(\w+)\s*\([^)]*\)',
            r'(?:const|let|var)\s+(\w+)\s*=\s*function\s*\([^)]*\)',
        ]
        
        for pattern in func_patterns:
            for match in re.finditer(pattern, code):
                result['functions'].append({
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1,
                    'type': 'function'
                })
        
        # Arrow functions
        arrow_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>'
        for match in re.finditer(arrow_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'type': 'arrow'
            })
        
        # Classes
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'extends': match.group(2) if match.group(2) else None
            })
        
        # Imports (ES6)
        import_patterns = [
            r'import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s+\*\s+as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in import_patterns:
            for match in re.finditer(pattern, code):
                result['imports'].append(match.group(2) if len(match.groups()) > 1 else match.group(1))
        
        # Require statements
        require_pattern = r'(?:const|let|var)\s+\{?([^}=]+)\}?\s*=\s*require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, code):
            result['imports'].append(match.group(2))
        
        return result
    
    # ==================== TYPESCRIPT PARSER ====================
    
    def _parse_typescript(self, code: str) -> Dict:
        """Enhanced TypeScript parser with interfaces, types, and generics"""
        result = self._parse_javascript(code)  # Start with JS parsing
        result['interfaces'] = []
        result['types'] = []
        result['enums'] = []
        
        # Interfaces
        interface_pattern = r'interface\s+(\w+)(?:<[^>]+>)?\s*(?:extends\s+([^{]+))?\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'extends': match.group(2).strip() if match.group(2) else None
            })
        
        # Type aliases
        type_pattern = r'type\s+(\w+)(?:<[^>]+>)?\s*='
        for match in re.finditer(type_pattern, code):
            result['types'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Enums
        enum_pattern = r'enum\s+(\w+)\s*\{'
        for match in re.finditer(enum_pattern, code):
            result['enums'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Decorators
        decorator_pattern = r'@(\w+)(?:\([^)]*\))?'
        result['decorators'] = [match.group(1) for match in re.finditer(decorator_pattern, code)]
        
        return result
    
    # ==================== JAVA PARSER ====================
    
    def _parse_java(self, code: str) -> Dict:
        """Enhanced Java parser"""
        result = {
            'functions': [],
            'classes': [],
            'interfaces': [],
            'enums': [],
            'imports': [],
            'annotations': []
        }
        
        # Method declarations
        method_pattern = r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*\{'
        for match in re.finditer(method_pattern, code):
            method_name = match.group(1)
            # Skip constructors and common keywords
            if method_name not in ['if', 'while', 'for', 'switch', 'catch', 'class']:
                result['functions'].append({
                    'name': method_name,
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Class declarations
        class_pattern = r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?\s*\{'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'extends': match.group(2) if match.group(2) else None,
                'implements': match.group(3).strip() if match.group(3) else None
            })
        
        # Interfaces
        interface_pattern = r'(?:public\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Enums
        enum_pattern = r'(?:public\s+)?enum\s+(\w+)\s*\{'
        for match in re.finditer(enum_pattern, code):
            result['enums'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Imports
        import_pattern = r'import\s+(?:static\s+)?([\w.]+(?:\.\*)?);'
        for match in re.finditer(import_pattern, code):
            result['imports'].append(match.group(1))
        
        # Annotations
        annotation_pattern = r'@(\w+)(?:\([^)]*\))?'
        result['annotations'] = list(set([match.group(1) for match in re.finditer(annotation_pattern, code)]))
        
        return result
    
    # ==================== C++ PARSER ====================
    
    def _parse_cpp(self, code: str) -> Dict:
        """Enhanced C++ parser with templates and namespaces"""
        result = {
            'functions': [],
            'classes': [],
            'structs': [],
            'namespaces': [],
            'templates': [],
            'includes': []
        }
        
        # Remove comments to avoid false matches
        code_no_comments = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code_no_comments = re.sub(r'/\*.*?\*/', '', code_no_comments, flags=re.DOTALL)
        
        # Function declarations
        func_pattern = r'(?:virtual\s+)?(?:static\s+)?(?:inline\s+)?(?:\w+(?:\s*\*|\s*&)?)\s+(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*(?:;|\{)'
        for match in re.finditer(func_pattern, code_no_comments):
            func_name = match.group(1)
            if func_name not in ['if', 'while', 'for', 'switch', 'return']:
                result['functions'].append({
                    'name': func_name,
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Class declarations
        class_pattern = r'class\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+(\w+))?\s*\{'
        for match in re.finditer(class_pattern, code_no_comments):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'inherits': match.group(2) if match.group(2) else None
            })
        
        # Struct declarations
        struct_pattern = r'struct\s+(\w+)\s*\{'
        for match in re.finditer(struct_pattern, code_no_comments):
            result['structs'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Namespaces
        namespace_pattern = r'namespace\s+(\w+)\s*\{'
        for match in re.finditer(namespace_pattern, code_no_comments):
            result['namespaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Templates
        template_pattern = r'template\s*<([^>]+)>\s*(?:class|struct|typename)\s+(\w+)'
        for match in re.finditer(template_pattern, code_no_comments):
            result['templates'].append({
                'name': match.group(2),
                'parameters': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Includes
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'
        for match in re.finditer(include_pattern, code):
            result['includes'].append(match.group(1))
        
        return result
    
    # ==================== C PARSER ====================
    
    def _parse_c(self, code: str) -> Dict:
        """C language parser"""
        result = {
            'functions': [],
            'structs': [],
            'typedefs': [],
            'includes': []
        }
        
        # Remove comments
        code_no_comments = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code_no_comments = re.sub(r'/\*.*?\*/', '', code_no_comments, flags=re.DOTALL)
        
        # Function declarations
        func_pattern = r'(?:static\s+)?(?:inline\s+)?(?:\w+(?:\s*\*)?)\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(func_pattern, code_no_comments):
            func_name = match.group(1)
            if func_name not in ['if', 'while', 'for', 'switch', 'return']:
                result['functions'].append({
                    'name': func_name,
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Struct declarations
        struct_pattern = r'(?:typedef\s+)?struct\s+(\w+)?\s*\{'
        for match in re.finditer(struct_pattern, code_no_comments):
            if match.group(1):
                result['structs'].append({
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Typedefs
        typedef_pattern = r'typedef\s+(?:struct\s+)?(?:\w+)\s+(\w+);'
        for match in re.finditer(typedef_pattern, code_no_comments):
            result['typedefs'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Includes
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'
        for match in re.finditer(include_pattern, code):
            result['includes'].append(match.group(1))
        
        return result
    
    # ==================== C# PARSER ====================
    
    def _parse_csharp(self, code: str) -> Dict:
        """Enhanced C# parser with properties, attributes, and LINQ"""
        result = {
            'functions': [],
            'classes': [],
            'interfaces': [],
            'properties': [],
            'enums': [],
            'namespaces': [],
            'attributes': [],
            'using_statements': []
        }
        
        # Method declarations
        method_pattern = r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(method_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Property declarations
        property_pattern = r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\{[^}]*\}'
        for match in re.finditer(property_pattern, code):
            result['properties'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Class declarations
        class_pattern = r'(?:public|private|internal)?\s*(?:abstract|sealed)?\s*(?:partial)?\s*class\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'inherits': match.group(2).strip() if match.group(2) else None
            })
        
        # Interfaces
        interface_pattern = r'(?:public|private|internal)?\s*interface\s+(\w+)\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Enums
        enum_pattern = r'(?:public|private|internal)?\s*enum\s+(\w+)\s*\{'
        for match in re.finditer(enum_pattern, code):
            result['enums'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Namespaces
        namespace_pattern = r'namespace\s+([\w.]+)\s*\{'
        for match in re.finditer(namespace_pattern, code):
            result['namespaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Attributes
        attribute_pattern = r'\[(\w+)(?:\([^)]*\))?\]'
        result['attributes'] = list(set([match.group(1) for match in re.finditer(attribute_pattern, code)]))
        
        # Using statements
        using_pattern = r'using\s+([\w.]+);'
        for match in re.finditer(using_pattern, code):
            result['using_statements'].append(match.group(1))
        
        return result
    
    # ==================== GO PARSER ====================
    
    def _parse_go(self, code: str) -> Dict:
        """Go language parser"""
        result = {
            'functions': [],
            'structs': [],
            'interfaces': [],
            'methods': [],
            'imports': []
        }
        
        # Function declarations
        func_pattern = r'func\s+(\w+)\s*\([^)]*\)(?:\s*\([^)]*\))?\s*\{'
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Method declarations (with receiver)
        method_pattern = r'func\s*\([^)]+\)\s*(\w+)\s*\([^)]*\)(?:\s*\([^)]*\))?\s*\{'
        for match in re.finditer(method_pattern, code):
            result['methods'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Struct declarations
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        for match in re.finditer(struct_pattern, code):
            result['structs'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Interface declarations
        interface_pattern = r'type\s+(\w+)\s+interface\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Imports
        import_pattern = r'import\s+(?:\(\s*([^)]+)\s*\)|"([^"]+)")'
        for match in re.finditer(import_pattern, code):
            imports_block = match.group(1) or match.group(2)
            if imports_block:
                for line in imports_block.split('\n'):
                    imp_match = re.search(r'"([^"]+)"', line)
                    if imp_match:
                        result['imports'].append(imp_match.group(1))
        
        return result
    
    # ==================== RUST PARSER ====================
    
    def _parse_rust(self, code: str) -> Dict:
        """Rust language parser"""
        result = {
            'functions': [],
            'structs': [],
            'enums': [],
            'traits': [],
            'impls': [],
            'uses': []
        }
        
        # Function declarations
        func_pattern = r'(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)(?:<[^>]+>)?\s*\('
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Struct declarations
        struct_pattern = r'(?:pub\s+)?struct\s+(\w+)(?:<[^>]+>)?\s*[{\(]'
        for match in re.finditer(struct_pattern, code):
            result['structs'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Enum declarations
        enum_pattern = r'(?:pub\s+)?enum\s+(\w+)(?:<[^>]+>)?\s*\{'
        for match in re.finditer(enum_pattern, code):
            result['enums'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Trait declarations
        trait_pattern = r'(?:pub\s+)?trait\s+(\w+)(?:<[^>]+>)?\s*\{'
        for match in re.finditer(trait_pattern, code):
            result['traits'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Impl blocks
        impl_pattern = r'impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)\s*\{'
        for match in re.finditer(impl_pattern, code):
            result['impls'].append({
                'trait': match.group(1) if match.group(1) else None,
                'type': match.group(2),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Use statements
        use_pattern = r'use\s+([\w:]+(?:\s*as\s+\w+)?);'
        for match in re.finditer(use_pattern, code):
            result['uses'].append(match.group(1))
        
        return result
    
    # ==================== RUBY PARSER ====================
    
    def _parse_ruby(self, code: str) -> Dict:
        """Ruby language parser"""
        result = {
            'functions': [],
            'classes': [],
            'modules': [],
            'requires': []
        }
        
        # Method declarations
        method_pattern = r'def\s+(?:self\.)?(\w+[?!]?)\s*(?:\([^)]*\))?'
        for match in re.finditer(method_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Class declarations
        class_pattern = r'class\s+(\w+)(?:\s*<\s*(\w+))?'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'inherits': match.group(2) if match.group(2) else None
            })
        
        # Module declarations
        module_pattern = r'module\s+(\w+)'
        for match in re.finditer(module_pattern, code):
            result['modules'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Requires
        require_pattern = r'require\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(require_pattern, code):
            result['requires'].append(match.group(1))
        
        return result
    
    # ==================== PHP PARSER ====================
    
    def _parse_php(self, code: str) -> Dict:
        """PHP language parser"""
        result = {
            'functions': [],
            'classes': [],
            'interfaces': [],
            'traits': [],
            'namespaces': [],
            'uses': []
        }
        
        # Function declarations
        func_pattern = r'function\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Class declarations
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?\s*\{'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'extends': match.group(2) if match.group(2) else None,
                'implements': match.group(3) if match.group(3) else None
            })
        
        # Interface declarations
        interface_pattern = r'interface\s+(\w+)\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Trait declarations
        trait_pattern = r'trait\s+(\w+)\s*\{'
        for match in re.finditer(trait_pattern, code):
            result['traits'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Namespaces
        namespace_pattern = r'namespace\s+([\w\\]+);'
        for match in re.finditer(namespace_pattern, code):
            result['namespaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Use statements
        use_pattern = r'use\s+([\w\\]+)(?:\s+as\s+(\w+))?;'
        for match in re.finditer(use_pattern, code):
            result['uses'].append(match.group(1))
        
        return result
    
    # ==================== SWIFT PARSER ====================
    
    def _parse_swift(self, code: str) -> Dict:
        """Swift language parser"""
        result = {
            'functions': [],
            'classes': [],
            'structs': [],
            'protocols': [],
            'extensions': [],
            'imports': []
        }
        
        # Function declarations
        func_pattern = r'func\s+(\w+)(?:<[^>]+>)?\s*\('
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Class declarations
        class_pattern = r'class\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1,
                'conforms': match.group(2).strip() if match.group(2) else None
            })
        
        # Struct declarations
        struct_pattern = r'struct\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{'
        for match in re.finditer(struct_pattern, code):
            result['structs'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Protocol declarations
        protocol_pattern = r'protocol\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{'
        for match in re.finditer(protocol_pattern, code):
            result['protocols'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Extension declarations
        extension_pattern = r'extension\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{'
        for match in re.finditer(extension_pattern, code):
            result['extensions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Imports
        import_pattern = r'import\s+([\w.]+)'
        for match in re.finditer(import_pattern, code):
            result['imports'].append(match.group(1))
        
        return result
    
    # ==================== KOTLIN PARSER ====================
    
    def _parse_kotlin(self, code: str) -> Dict:
        """Kotlin language parser"""
        result = {
            'functions': [],
            'classes': [],
            'interfaces': [],
            'data_classes': [],
            'objects': [],
            'imports': []
        }
        
        # Function declarations
        func_pattern = r'fun\s+(?:<[^>]+>\s+)?(\w+)\s*\('
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Data class declarations
        data_class_pattern = r'data\s+class\s+(\w+)\s*\('
        for match in re.finditer(data_class_pattern, code):
            result['data_classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Regular class declarations
        class_pattern = r'(?:open|abstract)?\s*class\s+(\w+)(?:\s*:\s*([^{(]+))?\s*[{(]'
        for match in re.finditer(class_pattern, code):
            if 'data class' not in code[max(0, match.start()-10):match.start()]:
                result['classes'].append({
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1,
                    'inherits': match.group(2).strip() if match.group(2) else None
                })
        
        # Interface declarations
        interface_pattern = r'interface\s+(\w+)\s*\{'
        for match in re.finditer(interface_pattern, code):
            result['interfaces'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Object declarations
        object_pattern = r'object\s+(\w+)\s*[:{]'
        for match in re.finditer(object_pattern, code):
            result['objects'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Imports
        import_pattern = r'import\s+([\w.]+)'
        for match in re.finditer(import_pattern, code):
            result['imports'].append(match.group(1))
        
        return result
    
    # ==================== GENERIC PARSER ====================
    
    def _parse_generic(self, code: str) -> Dict:
        """Generic parsing for unknown languages"""
        result = {
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        logger.info("⚠️ Using generic parser - may have limited accuracy")
        
        # Try to find function-like patterns
        func_patterns = [
            r'(?:def|function|func|fn|sub|procedure)\s+(\w+)',
            r'(\w+)\s*\([^)]*\)\s*[{:]',
        ]
        
        for pattern in func_patterns:
            for match in re.finditer(pattern, code):
                func_name = match.group(1)
                if len(func_name) > 2 and func_name not in ['if', 'for', 'while', 'return']:
                    result['functions'].append({
                        'name': func_name,
                        'line': code[:match.start()].count('\n') + 1
                    })
        
        # Try to find class-like patterns
        class_pattern = r'(?:class|struct|interface|type|record)\s+(\w+)'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Deduplicate
        result['functions'] = list({f['name']: f for f in result['functions']}.values())
        result['classes'] = list({c['name']: c for c in result['classes']}.values())
        
        return result
    
    # ==================== HELPER METHODS ====================
    
    def _get_name(self, node):
        """Get name from AST node"""
        if hasattr(node, 'id'):
            return node.id
        elif hasattr(node, 'attr'):
            return node.attr
        return 'Unknown'
    
    def _calculate_complexity(self, parsed_data: Dict) -> str:
        """Calculate code complexity level"""
        loc = parsed_data['lines_of_code']
        num_functions = len(parsed_data['functions'])
        num_classes = len(parsed_data['classes'])
        num_interfaces = len(parsed_data.get('interfaces', []))
        
        complexity_score = (loc / 100) + num_functions + (num_classes * 2) + (num_interfaces * 1.5)
        
        if complexity_score < 5:
            return 'low'
        elif complexity_score < 15:
            return 'medium'
        elif complexity_score < 30:
            return 'high'
        else:
            return 'very_high'
    
    def extract_functions_code(self, code: str, language: str) -> List[Dict]:
        """Extract individual function code blocks"""
        functions = []
        
        if language == 'python':
            try:
                tree = ast.parse(code)
                lines = code.split('\n')
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        start_line = node.lineno - 1
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 10
                        func_code = '\n'.join(lines[start_line:end_line])
                        
                        functions.append({
                            'name': node.name,
                            'code': func_code,
                            'start_line': node.lineno,
                            'end_line': end_line
                        })
            except Exception as e:
                logger.error(f"❌ Error extracting functions: {e}")
        
        return functions
    
    def get_summary(self, parsed_data: Dict) -> str:
        """Get human-readable summary of parsed code"""
        summary_parts = []
        
        summary_parts.append(f"Language: {parsed_data['language']}")
        summary_parts.append(f"Lines: {parsed_data['lines_of_code']}")
        summary_parts.append(f"Complexity: {parsed_data['complexity']}")
        
        if parsed_data['functions']:
            summary_parts.append(f"Functions: {len(parsed_data['functions'])}")
        if parsed_data['classes']:
            summary_parts.append(f"Classes: {len(parsed_data['classes'])}")
        if parsed_data.get('interfaces'):
            summary_parts.append(f"Interfaces: {len(parsed_data['interfaces'])}")
        if parsed_data.get('structs'):
            summary_parts.append(f"Structs: {len(parsed_data['structs'])}")
        
        return " | ".join(summary_parts)