import fitz
import pytesseract
from PIL import Image
import io

# Caminho absoluto do Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"

def extrair_texto_pdf(path):
    texto = ""
    try:
        doc = fitz.open(path)
        for pagina in doc:
            t = pagina.get_text().strip()
            palavras_chave = ["CNPJ", "VALOR", "PESO", "NOTA", "EMISSOR", "CTE", "CHAVE"]
            tem_conteudo_util = any(p in t.upper() for p in palavras_chave)

            if len(t) < 150 or not tem_conteudo_util:
                pix = pagina.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                t = pytesseract.image_to_string(img, lang="por")
            texto += "\n" + t
        doc.close()
    except Exception as e:
        print(f"❌ Erro ao ler PDF: {e}")
    return texto