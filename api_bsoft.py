"""
api_bsoft.py
============
Classe base para integração com a API REST do Bsoft TMS.
Importar sempre via config.py — nunca usar os.getenv() diretamente.
"""

import time
import requests
from requests.auth import HTTPBasicAuth
from colorama import init, Fore, Style

from config import BSOFT_USUARIO, BSOFT_SENHA, BSOFT_BASE_URL

init(autoreset=True)

LIMIT_POR_PAGINA = 100


class BsoftAPI:
    def __init__(self):
        self.base_url = BSOFT_BASE_URL
        self.session  = requests.Session()
        self.session.auth = HTTPBasicAuth(BSOFT_USUARIO, BSOFT_SENHA)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept":       "application/json",
        })

    # ------------------------------------------------------------------
    # GET com paginação automática
    # ------------------------------------------------------------------
    def get(self, endpoint: str, params: dict = None, paginar: bool = True):
        """
        GET com loop de paginação automático.
        - paginar=True  → retorna lista unificada de todos os registos.
        - paginar=False → retorna o JSON bruto da primeira página
          (útil para endpoints que retornam dict, ex: planoDeContasGerencial).
        """
        url    = f"{self.base_url}/{endpoint}"
        params = params or {}

        if not paginar:
            return self._request("GET", url, params=params)

        todos  = []
        offset = 0

        while True:
            params_pag = {**params, "limit": f"{offset},{LIMIT_POR_PAGINA}"}
            resultado  = self._request("GET", url, params=params_pag)

            if isinstance(resultado, dict):
                return resultado

            if not resultado:
                break

            todos.extend(resultado)
            print(Fore.CYAN + f"   📄 Paginação: {offset}–{offset + len(resultado)} registos obtidos")

            if len(resultado) < LIMIT_POR_PAGINA:
                break

            offset += LIMIT_POR_PAGINA
            time.sleep(0.2)

        return todos

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------
    def post(self, endpoint: str, body):
        url = f"{self.base_url}/{endpoint}"
        return self._request("POST", url, json=body)

    # ------------------------------------------------------------------
    # PUT
    # ------------------------------------------------------------------
    def put(self, endpoint: str, body):
        url = f"{self.base_url}/{endpoint}"
        return self._request("PUT", url, json=body)

    # ------------------------------------------------------------------
    # PATCH
    # ------------------------------------------------------------------
    def patch(self, endpoint: str, body):
        url = f"{self.base_url}/{endpoint}"
        return self._request("PATCH", url, json=body)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete(self, endpoint: str, params: dict = None):
        url = f"{self.base_url}/{endpoint}"
        return self._request("DELETE", url, params=params)

    # ------------------------------------------------------------------
    # Executor interno com tratamento de erros
    # ------------------------------------------------------------------
    def _request(self, method: str, url: str, **kwargs):
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)

            if resp.ok:
                try:
                    return resp.json()
                except Exception:
                    return {"raw": resp.text}

            cor = Fore.RED if resp.status_code >= 500 else Fore.YELLOW
            print(cor + f"   ⚠️  [{method}] {url}")
            print(cor + f"   Status: {resp.status_code} | Resposta: {resp.text[:300]}")
            return None

        except requests.exceptions.ConnectionError:
            print(Fore.RED + f"   ❌ Sem conexão: {url}")
        except requests.exceptions.Timeout:
            print(Fore.RED + f"   ❌ Timeout: {url}")
        except Exception as e:
            print(Fore.RED + f"   ❌ Erro inesperado [{method}] {url}: {e}")

        return None