import os
import hmac
import hashlib
from dotenv import load_dotenv

# Define o caminho absoluto para o ficheiro de configuração, 
# garantindo que seja encontrado independentemente de onde o script é chamado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, 'nexus_config.env')

# Carrega as variáveis de ambiente
load_dotenv(ENV_PATH)
SECRET_KEY = os.getenv('NEXUS_SECRET_KEY')

class NexusSecurityProvider:
    @staticmethod
    def get_key():
        if not SECRET_KEY:
            raise ValueError("Erro: A chave secreta (NEXUS_SECRET_KEY) não foi encontrada no nexus_config.env")
        return SECRET_KEY.encode('utf-8')

    @staticmethod
    def sign_payload(payload: str) -> str:
        """Assina o payload usando HMAC-SHA256."""
        key = NexusSecurityProvider.get_key()
        return hmac.new(key, payload.encode('utf-8'), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_payload(payload: str, signature: str) -> bool:
        """Verifica a integridade do payload comparando a assinatura."""
        expected = NexusSecurityProvider.sign_payload(payload)
        return hmac.compare_digest(expected, signature)
