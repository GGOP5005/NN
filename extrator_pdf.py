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
                print(f"    👁️ Modo Visão Computacional (OCR): Lendo imagem da página {pagina.number + 1}...")
                
                t_ocr = ""
                try:
                    # Método A: Tentar extrair imagens nativamente embutidas no PDF (muito comum em passes/Danfes)
                    lista_imagens = pagina.get_images(full=True)
                    if lista_imagens:
                        for img_info in lista_imagens:
                            xref = img_info[0]
                            base_imagem = doc.extract_image(xref)
                            bytes_imagem = base_imagem["image"]
                            
                            img = Image.open(io.BytesIO(bytes_imagem))
                            img = img.convert('L') # Converte para escala de cinzentos (melhora o OCR)
                            
                            try:
                                t_ocr += pytesseract.image_to_string(img, lang="por", config="--psm 6") + "\n"
                            except:
                                t_ocr += pytesseract.image_to_string(img, config="--psm 6") + "\n"
                    
                    # Método B: Se não havia imagem embutida, força a renderização da página inteira (Fallback)
                    if not t_ocr.strip():
                        pix = pagina.get_pixmap(dpi=300)
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        img = img.convert('L')
                        
                        try:
                            t_ocr = pytesseract.image_to_string(img, lang="por", config="--psm 6")
                        except:
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
        
    # Garante que sempre devolve uma string, mesmo que vazia, para não quebrar outras funções
    return texto.strip() if texto else ""