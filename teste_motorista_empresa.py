"""
Busca IDs dos motoristas por nome nos registros antigos.
python teste_motorista_empresa.py
"""
from api_bsoft import BsoftAPI
api = BsoftAPI()

BUSCAR = ["DAYVSON", "JERONIMO", "BRUNO", "DJOHN"]

print("=== Buscando nos 100 mais recentes ===")
r = api.get("pessoas/v1/pessoas/fisicas", params={"ini": 0, "fim": 100}, paginar=False)
lista = r if isinstance(r, list) else (r or {}).get("data", [])
ids_recentes = {str(p.get("id")) for p in lista}
for p in lista:
    nome = (p.get("nome") or "").upper()
    for busca in BUSCAR:
        if busca in nome:
            print(f"  ✅ id={p.get('id')} | {nome}")

print("\n=== Buscando IDs antigos (1..200) ===")
for id_test in range(1, 201):
    if str(id_test) in ids_recentes:
        continue
    try:
        r2 = api.get(f"pessoas/v1/pessoas/fisicas/{id_test}", paginar=False)
        lista2 = r2 if isinstance(r2, list) else ([r2] if r2 and isinstance(r2, dict) else [])
        for p in lista2:
            nome = (p.get("nome") or "").upper()
            for busca in BUSCAR:
                if busca in nome:
                    print(f"  ✅ id={p.get('id')} | {nome}")
    except Exception:
        pass

print("\nFim.")