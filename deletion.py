# deletion.py
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

class RepoDeletionTracker:
    """
    Snapshot-based deletion tracker.
    - Stores snapshot per repo in .cache/snapshots/<repo_id>.json
    - Detects deleted files, functions, classes between snapshots.
    """

    def __init__(self, repo_id: str, snapshot_dir: str = ".cache/snapshots"):
        self.repo_id = repo_id.replace("/", "_").replace(":", "_")
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.snapshot_dir / f"{self.repo_id}.json"

    def _normalize_parsed(self, parsed: Dict[str, Dict]) -> Dict[str, Dict[str, List[str]]]:
        """
        Normalize parsed_data shape to:
        { "file.py": {"functions": ["a","b"], "classes": ["X","Y"]}, ...}
        Accepts function/class entries as dicts or strings.
        """
        out: Dict[str, Dict[str, List[str]]] = {}
        for fname, meta in (parsed or {}).items():
            funcs = []
            classes = []
            f_list = meta.get("functions", []) or []
            c_list = meta.get("classes", []) or []

            for f in f_list:
                if isinstance(f, dict):
                    name = f.get("name") or f.get("id")
                else:
                    name = f
                if name:
                    funcs.append(str(name))

            for c in c_list:
                if isinstance(c, dict):
                    name = c.get("name") or c.get("id")
                else:
                    name = c
                if name:
                    classes.append(str(name))

            out[str(fname)] = {
                "functions": sorted(set(funcs)),
                "classes": sorted(set(classes))
            }
        return out

    def load_snapshot(self) -> Dict[str, Dict[str, List[str]]]:
        """Load previous snapshot (returns normalized structure)."""
        if not self.snapshot_path.exists():
            return {}
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            return self._normalize_parsed(raw)
        except Exception:
            return {}

    def save_snapshot(self, parsed: Dict[str, Dict[str, Any]]) -> None:
        """Save normalized snapshot to disk."""
        norm = self._normalize_parsed(parsed)
        with open(self.snapshot_path, "w", encoding="utf-8") as f:
            json.dump(norm, f, indent=2)

    def detect(self, current_parsed: Dict[str, Dict[str, Any]]) -> Dict:
        """
        Compare stored snapshot -> current_parsed and return deletions.

        Returns:
        {
          "deleted_files": ["a.py"],
          "deleted_details": {
              "b.py": {"functions": ["old_fn"], "classes": ["OldClass"]},
              ...
           }
        }
        """
        previous = self.load_snapshot()
        current = self._normalize_parsed(current_parsed)

        deleted_files = [f for f in previous.keys() if f not in current]

        deleted_details: Dict[str, Dict[str, List[str]]] = {}
        # for files that still exist, check functions/classes removed
        for fname, prev_meta in previous.items():
            if fname not in current:
                # whole file deleted (we already include file list)
                continue
            cur_meta = current.get(fname, {"functions": [], "classes": []})
            lost_funcs = [fn for fn in prev_meta.get("functions", []) if fn not in cur_meta.get("functions", [])]
            lost_classes = [cl for cl in prev_meta.get("classes", []) if cl not in cur_meta.get("classes", [])]
            if lost_funcs or lost_classes:
                deleted_details[fname] = {}
                if lost_funcs:
                    deleted_details[fname]["functions"] = lost_funcs
                if lost_classes:
                    deleted_details[fname]["classes"] = lost_classes

        return {"deleted_files": deleted_files, "deleted_details": deleted_details}
