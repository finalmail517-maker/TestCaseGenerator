"""
Chat History Manager for persistent conversation storage
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from logger import get_app_logger

logger = get_app_logger("chat_manager")

class ChatManager:
    """Manage chat history with persistence"""
    
    def __init__(self, history_dir: Path = None):
        """Initialize chat manager"""
        self.history_dir = history_dir or Path("chat_history")
        self.history_dir.mkdir(exist_ok=True, parents=True)
        
        self.current_session_file = None
        self.current_session_id = None
        
        logger.info(f"✅ ChatManager initialized with directory: {self.history_dir}")
    
    def start_new_session(self, title: str = None) -> str:
        """Start a new chat session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        
        self.current_session_id = session_id
        self.current_session_file = self.history_dir / f"{session_id}.json"
        
        session_data = {
            'session_id': session_id,
            'title': title or f"Chat {timestamp}",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'messages': []
        }
        
        self._save_session(session_data)
        logger.info(f"📝 New session started: {session_id}")
        
        return session_id
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Dict = None
    ) -> None:
        """Add a message to current session"""
        if not self.current_session_id:
            self.start_new_session()
        
        session_data = self._load_session(self.current_session_file)
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        session_data['messages'].append(message)
        session_data['updated_at'] = datetime.now().isoformat()
        
        self._save_session(session_data)
        logger.debug(f"💬 Message added: {role} - {len(content)} chars")
    
    def get_current_history(self) -> List[Dict]:
        """Get current session history"""
        if not self.current_session_file or not self.current_session_file.exists():
            return []
        
        session_data = self._load_session(self.current_session_file)
        return session_data.get('messages', [])
    
    def list_sessions(self, limit: int = 50) -> List[Dict]:
        """List all chat sessions"""
        sessions = []
        
        for file in sorted(self.history_dir.glob("session_*.json"), reverse=True)[:limit]:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        'session_id': data['session_id'],
                        'title': data['title'],
                        'created_at': data['created_at'],
                        'updated_at': data['updated_at'],
                        'message_count': len(data.get('messages', []))
                    })
            except Exception as e:
                logger.error(f"❌ Error loading session {file.name}: {e}")
                continue
        
        return sessions
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load a specific session"""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            logger.warning(f"⚠️ Session not found: {session_id}")
            return None
        
        self.current_session_id = session_id
        self.current_session_file = session_file
        
        session_data = self._load_session(session_file)
        logger.info(f"📂 Session loaded: {session_id}")
        
        return session_data
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_file = self.history_dir / f"{session_id}.json"
        
        if session_file.exists():
            session_file.unlink()
            logger.info(f"🗑️ Session deleted: {session_id}")
            
            if self.current_session_id == session_id:
                self.current_session_id = None
                self.current_session_file = None
            
            return True
        
        return False
    
    def update_session_title(self, session_id: str, new_title: str) -> bool:
        """Update session title"""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return False
        
        session_data = self._load_session(session_file)
        session_data['title'] = new_title
        session_data['updated_at'] = datetime.now().isoformat()
        
        self._save_session(session_data, session_file)
        logger.info(f"✏️ Session title updated: {session_id}")
        
        return True
    
    def clear_current_session(self) -> None:
        """Clear current session"""
        self.current_session_id = None
        self.current_session_file = None
        logger.info("🧹 Current session cleared")
    
    def export_session(self, session_id: str, format: str = 'json') -> Optional[Path]:
        """Export session to file"""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        session_data = self._load_session(session_file)
        
        if format == 'json':
            return session_file
        elif format == 'txt':
            txt_file = self.history_dir / f"{session_id}.txt"
            
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"Chat Session: {session_data['title']}\n")
                f.write(f"Created: {session_data['created_at']}\n")
                f.write("=" * 80 + "\n\n")
                
                for msg in session_data['messages']:
                    f.write(f"[{msg['timestamp']}] {msg['role'].upper()}:\n")
                    f.write(f"{msg['content']}\n\n")
                    f.write("-" * 80 + "\n\n")
            
            return txt_file
        
        return None
    
    def _save_session(self, session_data: Dict, file: Path = None) -> None:
        """Save session data to file"""
        file = file or self.current_session_file
        
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    def _load_session(self, file: Path) -> Dict:
        """Load session data from file"""
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_statistics(self) -> Dict:
        """Get chat statistics"""
        sessions = self.list_sessions(limit=1000)
        
        total_messages = sum(s['message_count'] for s in sessions)
        
        return {
            'total_sessions': len(sessions),
            'total_messages': total_messages,
            'average_messages_per_session': total_messages / len(sessions) if sessions else 0,
            'oldest_session': sessions[-1]['created_at'] if sessions else None,
            'newest_session': sessions[0]['created_at'] if sessions else None
        }