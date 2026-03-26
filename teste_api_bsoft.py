"""
Descobre empresas_id lendo abastecimentos já existentes na Bsoft.
python teste_api_bsoft.py
"""
import json
from api_bsoft import BsoftAPI

api = BsoftAPI()

print("\n=== ABASTECIMENTOS EXISTENTES (últimos 5) ===")
result = api.get("manutencao/v1/abastecimentos", params={"fim": 5}, paginar=False)
if result:
    lista = result if isinstance(result, list) else result.get("data", [result])
    for ab in lista[:3]:
        print(json.dumps(ab, ensure_ascii=False, indent=2))
        print("---")
else:
    print("  (sem retorno)")

print("\n=== AGÊNCIAS (com paginação) ===")
result2 = api.get("transporte/v1/agencias", params={"ini": 0, "fim": 5}, paginar=False)
if result2:
    lista2 = result2 if isinstance(result2, list) else result2.get("data", [])
    for ag in lista2[:3]:
        print(json.dumps(ag, ensure_ascii=False, indent=2))
else:
    print("  (sem retorno)")