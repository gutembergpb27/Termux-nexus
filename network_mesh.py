import socket
import json
import threading
import time

class NexusMeshNode:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.is_running = False
        self.on_message_callback = None

    def start_server(self, callback):
        """Inicia o servidor de escuta da rede Mesh em uma thread separada."""
        self.on_message_callback = callback
        self.is_running = True
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()
        print(f"📡 [Mesh Server] Escutando na porta {self.port} para orquestração distribuída...")

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            while self.is_running:
                try:
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(1024)
                        if data:
                            message = json.loads(data.decode('utf-8'))
                            if self.on_message_callback:
                                self.on_message_callback(message, addr)
                except Exception as e:
                    if self.is_running:
                        print(f"⚠️ [Mesh Server] Erro ao processar pacote de rede: {e}")

    @staticmethod
    def send_transaction(target_host, target_port, payload):
        """Envia de forma assíncrona um bloco ou evento para outro nó da malha."""
        def _send():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0) # Não trava o Core se o outro dispositivo sumir da rede
                    s.connect((target_host, target_port))
                    s.sendall(json.dumps(payload).encode('utf-8'))
            except Exception as e:
                print(f"📡 [Mesh Outbound] Falha ao sincronizar com nó {target_host}:{target_port} -> {e}")

        threading.Thread(target=_send, daemon=True).start()
