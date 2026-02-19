"""
Configuration settings for the Test Case Generator
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""
    
    # Application settings
    APP_NAME = "AI Test Case Generator"
    APP_VERSION = "2.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # LLM Configuration
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash-lite")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))
    
    # File handling
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "1000000"))  # 1MB
    MAX_FILES_PER_REQUEST = int(os.getenv("MAX_FILES_PER_REQUEST", "50"))
    SUPPORTED_EXTENSIONS = [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
        '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala'
    ]
    
    # Git configuration
    GIT_CLONE_DEPTH = int(os.getenv("GIT_CLONE_DEPTH", "1"))
    GIT_TIMEOUT = int(os.getenv("GIT_TIMEOUT", "300"))
    MAX_REPO_FILES = int(os.getenv("MAX_REPO_FILES", "100"))
    
    # RAG configuration
    RAG_MAX_RESULTS = int(os.getenv("RAG_MAX_RESULTS", "3"))
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.1"))

    # Test generation settings
    DEFAULT_TEST_TYPES = ["Unit Test", "Regression Test", "Functional Test"]
    UNIT_TESTS_PER_FILE = int(os.getenv("UNIT_TESTS_PER_FILE", "5"))
    REGRESSION_TESTS_PER_CHANGE = int(os.getenv("REGRESSION_TESTS_PER_CHANGE", "3"))
    FUNCTIONAL_TESTS_PER_MODULE = int(os.getenv("FUNCTIONAL_TESTS_PER_MODULE", "5"))
    
    # Security settings
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))
    ENABLE_SECURITY_LOGGING = os.getenv("ENABLE_SECURITY_LOGGING", "True").lower() == "true"
    
    # Storage paths
    BASE_DIR = Path(__file__).parent
    STORAGE_DIR = BASE_DIR / "storage"
    CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
    RAG_STORAGE_DIR = BASE_DIR / "rag_storage"
    TEST_OUTPUT_DIR = BASE_DIR / "test_outputs"
    TEMP_REPOS_DIR = BASE_DIR / "temp_repos"
    LOGS_DIR = BASE_DIR / "logs"
    
    # Create directories
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        for dir_path in [
            cls.STORAGE_DIR,
            cls.CHAT_HISTORY_DIR,
            cls.RAG_STORAGE_DIR,
            cls.TEST_OUTPUT_DIR,
            cls.TEMP_REPOS_DIR,
            cls.LOGS_DIR
        ]:
            dir_path.mkdir(exist_ok=True, parents=True)
    
    # Streamlit configuration
    STREAMLIT_PORT = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    
    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    LOG_FILE = LOGS_DIR / "app.log"
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        errors = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is not set in .env file")
        
        try:
            cls.create_directories()
        except Exception as e:
            errors.append(f"Cannot create directories: {e}")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True

# Create configuration instance
config = Config()

# Create directories on import
config.create_directories()