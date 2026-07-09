import time
import threading

class TokenBucketLimiter:
    def __init__(self, capacity=10, leak_rate=2.0):
        """
        capacity: Número máximo de requisições/pacotes permitidos em rajada.
        leak_rate: Quantos tokens são regenerados por segundo.
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.tokens = float(capacity)
        self.last_check = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens_requested=1):
        """Verifica se há tokens suficientes. Retorna True se o pacote puder passar."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_check
            self.last_check = now
            
            # Regenera tokens com base no tempo decorrido
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.leak_rate))
            
            if self.tokens >= tokens_requested:
                self.tokens -= tokens_requested
                return True
            return False # Dropa ou aplica Backpressure
