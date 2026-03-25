import pandas as pd

def extrair_texto_excel(path):
    texto_final = ""
    try:
        xls = pd.read_excel(path, sheet_name=None, engine='openpyxl')
        for nome_aba, df in xls.items():
            csv_string = df.to_csv(index=False)
            texto_final += f"--- ABA: {nome_aba} ---\n{csv_string}\n\n"
    except Exception as e:
        print(f"❌ Erro ao ler Excel: {e}")
    return texto_final