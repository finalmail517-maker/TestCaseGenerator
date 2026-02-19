An intelligent test case generation system that automatically creates comprehensive test suites for your code using AI/LLM technology. Supports multiple programming languages and generates Unit Tests, Regression Tests, and Functional Tests in professional formats.
Features
🎯 Core Capabilities

Multi-Language Support: Python, JavaScript, TypeScript, Java, C++, Go, Ruby, PHP, and more
Multiple Test Types:

Unit Tests (function-level testing)
Regression Tests (change detection and backward compatibility)
Functional Tests (end-to-end behavior validation)


Professional Test Formats: Industry-standard test case documentation with Test IDs, Steps, and Expected Results
Code-Based Tests: Ready-to-run test functions with assertions

🚀 Input Methods

File Upload: Upload individual code files through web interface
Git Repository: Clone and analyze entire repositories
Interactive Chat: Ask questions and get guidance on test generation

🧠 Intelligent Features

RAG System: Context-aware test generation using Retrieval Augmented Generation
Code Chunking: Intelligent code splitting for optimal LLM processing
Change Detection: Identifies code modifications for targeted regression testing
Security Validation: Input sanitization and malicious pattern detection

📊 Export Options

CSV format for spreadsheet integration
Professional test reports (TXT format)
JSON format for programmatic access
Multiple format export in one go

Installation
Prerequisites

Python 3.8 or higher
Git (for repository cloning features)
LLM API endpoint (local or remote)

Setup

Clone the repository

bashgit clone <repository-url>
cd test-case-generator

Install dependencies

bashpip install -r requirements.txt

Configure environment variables
Create a .env file in the root directory:

env# LLM Configuration
LLM_API_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL_NAME=your-model-name
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# Application Settings
DEBUG=False
LOG_LEVEL=INFO
MAX_FILE_SIZE=1000000

# Feature Flags
ENABLE_GIT_INTEGRATION=True
ENABLE_RAG_SYSTEM=True

Create necessary directories

bashpython -c "from config import config; config.create_directories()"
Usage
Web Interface (Streamlit)
Start the web application:
bashstreamlit run app.py
The application will be available at http://localhost:8501
Features:

Upload code files via drag-and-drop
Clone Git repositories by URL
Interactive chat for test generation guidance
Real-time test generation with progress tracking
Download generated tests in multiple formats

Command Line Interface
Generate tests from local files
bashpython cli.py generate file1.py file2.py --types unit regression functional --output csv
Generate tests from Git repository
bashpython cli.py generate-repo https://github.com/username/repo.git --branch main --types unit functional
Analyze code structure
bashpython cli.py analyze mycode.py
Export in multiple formats
bashpython cli.py generate file.py --output all
```

```

## Configuration

### LLM Settings
Configure your LLM endpoint and model in the `.env` file or through environment variables:
- `LLM_API_ENDPOINT`: API endpoint URL
- `LLM_MODEL_NAME`: Model identifier
- `LLM_TEMPERATURE`: Creativity level (0.0-1.0)
- `LLM_MAX_TOKENS`: Maximum response length

### Test Generation Settings
- `UNIT_TESTS_PER_FILE`: Number of unit tests per file (default: 5)
- `REGRESSION_TESTS_PER_CHANGE`: Tests per code change (default: 3)
- `FUNCTIONAL_TESTS_PER_MODULE`: Module-level tests (default: 5)

### Security Settings
- `MAX_INPUT_LENGTH`: Maximum input string length
- `RATE_LIMIT_REQUESTS`: Request rate limit
- `ENABLE_SECURITY_LOGGING`: Enable security event logging

## Test Format Examples

### Professional Format (Functional Tests)
```
Test Case ID: TC-FN-01
Description: Validate user authentication flow
Steps:
  Step 1: Navigate to login page
  Step 2: Enter valid credentials
  Step 3: Click login button
Expected Result: User successfully authenticated and redirected to dashboard
Code Format (Unit/Regression Tests)
pythondef test_calculate_total_valid_input():
    """Test calculate_total with valid numeric inputs"""
    result = calculate_total(10, 20, 30)
    assert result == 60, "Sum should equal 60"
Architecture
Code Processing Pipeline

Parsing: Extract functions, classes, imports from code
Chunking: Split code into logical, processable chunks
Context Retrieval: Use RAG to find relevant code context
Test Generation: Generate tests using LLM for each chunk
Formatting: Convert to professional or code format
Export: Save to CSV, TXT, or JSON

RAG System
The RAG (Retrieval Augmented Generation) system maintains a knowledge base of:

Code structure and patterns
Function and class definitions
Previous versions for change detection
Cross-file dependencies

Security
The application includes multiple security layers:

Input Sanitization: Removes malicious patterns and control characters
Query Validation: Ensures requests are test-related
Code Validation: Checks for suspicious patterns in uploaded code
Git URL Validation: Prevents access to private/local repositories
Rate Limiting: Prevents abuse (placeholder for production implementation)

Logging
Comprehensive logging system with multiple log files:

logs/app.log: General application events
logs/test_generation.log: Test generation metrics
logs/errors.log: Error tracking
logs/performance.log: Performance metrics
logs/security_events.log: Security-related events

Troubleshooting
LLM Connection Issues

Verify LLM_API_ENDPOINT is correct and accessible
Check if LLM service is running
Review timeout settings in configuration

Git Clone Failures

Ensure Git is installed and in PATH
Check repository URL format
Verify network connectivity
For private repos, authentication is not currently supported

Test Generation Issues

Check logs in logs/app.log for detailed errors
Verify code files are in supported languages
Ensure LLM has sufficient context window for large files

Contributing
Contributions are welcome! Please:

Fork the repository
Create a feature branch
Make your changes with tests
Submit a pull request

License
[MIT]
Support
For issues, questions, or feature requests, please:

Check the logs for detailed error information
Review the troubleshooting section
Open an issue on the repository


Streamlit for the web interface
Python AST for code parsing
Modern LLM technology for intelligent test generation
