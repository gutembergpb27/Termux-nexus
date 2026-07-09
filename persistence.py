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

    def _validate_file_chain(self, filepath, initial_previous_hash=None):
        """Valida um arquivo de blocos e retorna o ultimo hash armazenado."""
        if not os.path.exists(filepath):
            return initial_previous_hash

        previous_stored_hash = initial_previous_hash

        with open(filepath, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                if not line.strip():
                    continue

                try:
                    block = json.loads(line)
                    timestamp = block["timestamp"]
                    payload = block["payload"]
                    prev_hash = block["prev_hash"]
                    stored_hash = block["hash"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise ValueError(
                        f"Bloco invalido na linha {line_number}: {exc}"
                    ) from exc

                expected_hash = self._compute_hash(
                    timestamp,
                    payload,
                    prev_hash
                )

                if stored_hash != expected_hash:
                    raise ValueError(
                        f"Hash invalido na linha {line_number}"
                    )

                if previous_stored_hash is None:
                    if payload != "ROTATION_ANCHOR" and prev_hash != "0" * 64:
                        raise ValueError(
                            f"Hash genesis invalido na linha {line_number}"
                        )
                elif prev_hash != previous_stored_hash:
                    raise ValueError(
                        f"Quebra de cadeia na linha {line_number}"
                    )

                previous_stored_hash = stored_hash

        return previous_stored_hash

    def validate_chain(self):
        """Valida cadeia ativa e, se existir, o arquivo rotacionado anterior."""
        backup_filepath = f"{self.filepath}.1"

        previous_hash = None
        if os.path.exists(backup_filepath):
            previous_hash = self._validate_file_chain(backup_filepath)

        self._validate_file_chain(
            self.filepath,
            initial_previous_hash=previous_hash
        )

        return True

    def recover_state(self):
        """Lê os blocos criptográficos e reconstrói o estado lógico do Nexus v700."""
        self.validate_chain()
        state = {"active_workers": {}, "completed_jobs": [], "pending_jobs": []}
        if not os.path.exists(self.filepath):
            return state

        print("🔄 Validando cadeia e reconstruindo árvore de estado...")
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    block = json.loads(line.strip())
                    payload = block.get("payload")
                    
                    # Ignora âncoras de rotação interna
                    if payload == "ROTATION_ANCHOR":
                        continue
                        
                    event = payload.get("event") if isinstance(payload, dict) else None
                    data = payload.get("data") if isinstance(payload, dict) else None

                    if event == "WORKER_SPAWN":
                        state["active_workers"][data["worker_id"]] = data["pid"]
                    elif event == "WORKER_CRASH":
                        if data["worker_id"] in state["active_workers"]:
                            del state["active_workers"][data["worker_id"]]
                    elif event == "JOB_SUBMIT":
                        state["pending_jobs"].append(data["job_id"])
                    elif event == "JOB_COMMIT":
                        if data["job_id"] in state["pending_jobs"]:
                            state["pending_jobs"].remove(data["job_id"])
                        state["completed_jobs"].append(data["job_id"])
                except Exception as e:
                    print(f"⚠️ Bloco ignorado na varredura: {e}")
        return state
