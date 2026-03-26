import fitz
import pytesseract
from PIL import Image
import io

# Caminho absoluto do Tesseract no Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"

def extrair_texto_pdf(path):
    texto = ""
    try:
        doc = fitz.open(path)
        for pagina in doc:
            # 1. Extração Nativa: Tenta extrair o texto digital puro do PDF
            t_nativo = pagina.get_text("text").strip()
            
            # 2. Motor de Decisão: Se a página tiver menos de 150 caracteres, é uma "FOTO" ou Escaneado
            if len(t_nativo) < 150:
                print(f"    👁️ Modo Visão Computacional: Lendo imagem da página {pagina.number + 1}...")
                try:
                    # Extrai a imagem com alta resolução (300 DPI) para máxima clareza
                    pix = pagina.get_pixmap(dpi=300)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Tenta ler com idioma português. O '--psm 6' é a magia que mantém as colunas da tabela separadas!
                    try:
                        t_ocr = pytesseract.image_to_string(img, lang="por", config="--psm 6")
                    except:
                        # Fallback seguro caso o pacote português não esteja instalado no Windows
                        t_ocr = pytesseract.image_to_string(img, config="--psm 6")
                        
                    texto += "\n" + t_ocr.strip()
                except Exception as e_ocr:
                    print(f"    ⚠️ Falha na visão computacional da página {pagina.number + 1}: {e_ocr}")
                    texto += "\n" + t_nativo # Usa o pouco que conseguiu nativamente como último recurso
            else:
                # Se o PDF for digital (PDF original), usa o texto nativo que é 100% perfeito
                texto += "\n" + t_nativo
                
        doc.close()
    except Exception as e:
        print(f"❌ Erro crítico ao ler PDF {path}: {e}")
        
    return texto.strip()