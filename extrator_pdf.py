import fitz
import pytesseract
from PIL import Image
import io

# --- SEU CAMINHO ESPECÍFICO ---
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"

def extrair_texto_pdf(path):
    texto = ""
    try:
        doc = fitz.open(path)
        for pagina in doc:
            t = pagina.get_text().strip()
            # Lista de palavras que OBRIGATORIAMENTE deveriam estar em um documento fiscal
            palavras_chave = ["CNPJ", "VALOR", "PESO", "NOTA", "EMISSOR", "CTE", "CHAVE"]
            tem_conteudo_util = any(p in t.upper() for p in palavras_chave)

            # Se tiver pouco texto OU não encontrar palavras essenciais, chama o OCR
            if len(t) < 150 or not tem_conteudo_util:
                # CORREÇÃO BUG 3: Linha duplicada removida (get_pixmap era chamado 2x)
                pix = pagina.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                t = pytesseract.image_to_string(img, lang="por")
            texto += "\n" + t
        doc.close()
    except Exception as e:
        print(f"❌ Erro ao ler PDF: {e}")
    return texto.upper()
