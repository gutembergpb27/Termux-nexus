import os
import hashlib
import time
import json

class NexusPersistence:
    def __init__(self, filepath="outputs/nexus_store.db", max_bytes=10240):
        self.filepath = filepath
        self.max_bytes = max_bytes
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.last_hash = self._recover_last_hash()

    def _compute_hash(self, timestamp, payload, previous_hash):
        block_string = f"{timestamp}{payload}{previous_hash}".encode('utf-8')
        return hashlib.sha256(block_string).hexdigest()

    def _recover_last_hash(self):
        if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) == 0:
            return "0" * 64
        try:
            with open(self.filepath, "rb") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].decode('utf-8').strip()
                    return json.loads(last_line).get("hash", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    def _rotate_logs(self):
        """Rotaciona o log e cria o novo arquivo imediatamente com o bloco de ancoragem."""
        backup_filepath = f"{self.filepath}.1"
        if os.path.exists(backup_filepath):
            os.remove(backup_filepath)
        if os.path.exists(self.filepath):
            os.rename(self.filepath, backup_filepath)
            
        # 🔥 ANCORAGEM ATÔMICA: Cria o novo arquivo vinculando o último hash imediatamente
        timestamp = time.time_ns()
        current_hash = self._compute_hash(timestamp, "ROTATION_ANCHOR", self.last_hash)
        
        anchor_block = {
            "timestamp": timestamp,
            "payload": "ROTATION_ANCHOR",
            "prev_hash": self.last_hash,
            "hash": current_hash
        }
        
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(anchor_block) + "\n")
            f.flush()
            os.fsync(f.fileno())
            
        self.last_hash = current_hash

    def append_transaction(self, payload):
        if os.path.exists(self.filepath) and os.path.getsize(self.filepath) >= self.max_bytes:
            self._rotate_logs()
            
        timestamp = time.time_ns()
        prev_hash = self.last_hash
        current_hash = self._compute_hash(timestamp, payload, prev_hash)
        
        transaction_block = {
            "timestamp": timestamp,
            "payload": payload,
            "prev_hash": prev_hash,
            "hash": current_hash
        }
        
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(transaction_block) + "\n")
            f.flush()
            os.fsync(f.fileno())

        self.last_hash = current_hash
        return current_hash

