"""
Code chunking utility to intelligently split code into processable pieces
"""
from typing import List, Dict
import ast
from logger import get_app_logger

logger = get_app_logger("code_chunker")

class CodeChunker:
    """Split code into logical chunks for processing"""
    
    def __init__(self, max_chunk_size: int = 1500):
        """
        Initialize code chunker
        
        Args:
            max_chunk_size: Maximum size of each chunk in characters
        """
        self.max_chunk_size = max_chunk_size
        logger.info(f" CodeChunker initialized (max_chunk_size={max_chunk_size})")
    
    def chunk_code(self, code: str, parsed_data: Dict) -> List[Dict]:
        """
        Split code into logical chunks
        
        Args:
            code: Full code content
            parsed_data: Parsed code structure from CodeParser
            
        Returns:
            List of code chunks with metadata
        """
        language = parsed_data.get('language', 'unknown')
        logger.debug(f"Chunking {language} code ({len(code)} chars)")
        
        if language == 'python':
            return self._chunk_python(code, parsed_data)
        elif language in ['javascript', 'typescript']:
            return self._chunk_javascript(code, parsed_data)
        else:
            return self._chunk_generic(code, parsed_data)
    
    def _chunk_python(self, code: str, parsed_data: Dict) -> List[Dict]:
        """Chunk Python code by functions and classes"""
        chunks = []
        
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            
            # Get imports
            imports = self._extract_imports(code)
            
            # Process each class
            for cls in parsed_data.get('classes', []):
                cls_name = cls['name']
                line = cls.get('line', 1)
                
                end_line = self._find_class_end(tree, cls_name, line)
                class_code = '\n'.join(lines[line-1:end_line])
                
                chunks.append({
                    'type': 'class',
                    'name': cls_name,
                    'code': f"{imports}\n\n{class_code}",
                    'line_start': line,
                    'line_end': end_line,
                    'size': len(class_code),
                    'methods': cls.get('methods', [])
                })
            
            # Process standalone functions
            class_lines = set()
            for cls in parsed_data.get('classes', []):
                line = cls.get('line', 1)
                end_line = self._find_class_end(tree, cls['name'], line)
                class_lines.update(range(line, end_line + 1))
            
            for func in parsed_data.get('functions', []):
                func_name = func['name']
                line = func.get('line', 1)
                
                if line in class_lines:
                    continue
                
                end_line = self._find_function_end(tree, func_name, line)
                func_code = '\n'.join(lines[line-1:end_line])
                
                if len(func_code) <= self.max_chunk_size:
                    chunks.append({
                        'type': 'function',
                        'name': func_name,
                        'code': f"{imports}\n\n{func_code}",
                        'line_start': line,
                        'line_end': end_line,
                        'size': len(func_code),
                        'args': func.get('args', [])
                    })
                else:
                    chunks.append({
                        'type': 'function',
                        'name': func_name,
                        'code': f"{imports}\n\n{func_code[:self.max_chunk_size]}",
                        'line_start': line,
                        'line_end': end_line,
                        'size': len(func_code),
                        'truncated': True,
                        'args': func.get('args', [])
                    })
            
            if not chunks:
                chunks.append({
                    'type': 'module',
                    'name': 'full_module',
                    'code': code[:self.max_chunk_size],
                    'line_start': 1,
                    'line_end': len(lines),
                    'size': len(code)
                })
            
        except Exception as e:
            logger.error(f" Error chunking Python code: {e}")
            return self._chunk_generic(code, parsed_data)
        
        logger.debug(f" Created {len(chunks)} chunks from Python code")
        return chunks
    
    def _chunk_javascript(self, code: str, parsed_data: Dict) -> List[Dict]:
        """Chunk JavaScript/TypeScript code"""
        chunks = []
        lines = code.split('\n')
        
        for func in parsed_data.get('functions', []):
            func_name = func['name']
            line = func.get('line', 1)
            
            end_line = self._find_js_function_end(lines, line)
            func_code = '\n'.join(lines[line-1:end_line])
            
            if len(func_code) <= self.max_chunk_size:
                chunks.append({
                    'type': 'function',
                    'name': func_name,
                    'code': func_code,
                    'line_start': line,
                    'line_end': end_line,
                    'size': len(func_code)
                })
        
        for cls in parsed_data.get('classes', []):
            cls_name = cls['name']
            line = cls.get('line', 1)
            
            end_line = self._find_js_class_end(lines, line)
            class_code = '\n'.join(lines[line-1:end_line])
            
            chunks.append({
                'type': 'class',
                'name': cls_name,
                'code': class_code,
                'line_start': line,
                'line_end': end_line,
                'size': len(class_code)
            })
        
        if not chunks:
            return self._chunk_generic(code, parsed_data)
        
        logger.debug(f"Created {len(chunks)} chunks from JavaScript code")
        return chunks
    
    def _chunk_generic(self, code: str, parsed_data: Dict) -> List[Dict]:
        """Generic chunking by size"""
        chunks = []
        lines = code.split('\n')
        
        current_chunk = []
        current_size = 0
        chunk_num = 1
        
        for i, line in enumerate(lines, 1):
            line_size = len(line)
            
            if current_size + line_size > self.max_chunk_size and current_chunk:
                chunks.append({
                    'type': 'segment',
                    'name': f'segment_{chunk_num}',
                    'code': '\n'.join(current_chunk),
                    'line_start': i - len(current_chunk),
                    'line_end': i - 1,
                    'size': current_size
                })
                
                current_chunk = []
                current_size = 0
                chunk_num += 1
            
            current_chunk.append(line)
            current_size += line_size
        
        if current_chunk:
            chunks.append({
                'type': 'segment',
                'name': f'segment_{chunk_num}',
                'code': '\n'.join(current_chunk),
                'line_start': len(lines) - len(current_chunk) + 1,
                'line_end': len(lines),
                'size': current_size
            })
        
        logger.debug(f" Created {len(chunks)} generic chunks")
        return chunks
    
    def _extract_imports(self, code: str) -> str:
        """Extract import statements from Python code"""
        try:
            tree = ast.parse(code)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    names = ', '.join([alias.name for alias in node.names])
                    imports.append(f"from {module} import {names}")
            
            return '\n'.join(imports[:10])
        except:
            return ""
    
    def _find_class_end(self, tree, class_name: str, start_line: int) -> int:
        """Find the end line of a class"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                if hasattr(node, 'end_lineno'):
                    return node.end_lineno
                if node.body:
                    last_node = node.body[-1]
                    if hasattr(last_node, 'end_lineno'):
                        return last_node.end_lineno
        return start_line + 20
    
    def _find_function_end(self, tree, func_name: str, start_line: int) -> int:
        """Find the end line of a function"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                if hasattr(node, 'end_lineno'):
                    return node.end_lineno
                if node.body:
                    last_node = node.body[-1]
                    if hasattr(last_node, 'end_lineno'):
                        return last_node.end_lineno
        return start_line + 15
    
    def _find_js_function_end(self, lines: List[str], start_line: int) -> int:
        """Find end of JavaScript function"""
        brace_count = 0
        in_function = False
        
        for i in range(start_line - 1, len(lines)):
            line = lines[i]
            
            if '{' in line:
                brace_count += line.count('{')
                in_function = True
            if '}' in line:
                brace_count -= line.count('}')
            
            if in_function and brace_count == 0:
                return i + 1
        
        return min(start_line + 30, len(lines))
    
    def _find_js_class_end(self, lines: List[str], start_line: int) -> int:
        """Find end of JavaScript class"""
        return self._find_js_function_end(lines, start_line)
    
    def get_chunk_summary(self, chunks: List[Dict]) -> Dict:
        """Get summary statistics for chunks"""
        return {
            'total_chunks': len(chunks),
            'by_type': {
                chunk_type: len([c for c in chunks if c['type'] == chunk_type])
                for chunk_type in set(c['type'] for c in chunks)
            },
            'total_size': sum(c['size'] for c in chunks),
            'avg_size': sum(c['size'] for c in chunks) / len(chunks) if chunks else 0
        }