from mcp.server.fastmcp import FastMCP
import fitz  # PyMuPDF
import os
import requests
import tempfile
import uuid

# Inicializamos el servidor
mcp = FastMCP("PDF Cleaner Wuolah")

def subir_a_internet(filepath: str) -> tuple[str | None, str]:
    """
    Intenta subir a Catbox (más estable), luego File.io, luego Transfer.sh.
    Devuelve (enlace, mensaje_error).
    """
    filename = os.path.basename(filepath)
    errors = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # --- INTENTO 1: Catbox.moe (Suele evitar firewalls) ---
    try:
        with open(filepath, 'rb') as f:
            # Catbox usa una API simple de form-data
            data = {'reqtype': 'fileupload'}
            response = requests.post('https://catbox.moe/user/api.php', data=data, files={'fileToUpload': f}, headers=headers, timeout=15)
        
        if response.status_code == 200 and "catbox.moe" in response.text:
            return response.text.strip(), ""
        else:
            errors.append(f"Catbox falló ({response.status_code})")
    except Exception as e:
        errors.append(f"Catbox error: {str(e)}")

    return None, "; ".join(errors)

@mcp.tool()
def limpiar_pdf(input_path: str, output_path: str | None = None) -> str:
    """
    Limpia un PDF de Wuolah. Intenta subirlo para dar un enlace.
    Si la subida falla, devuelve la ruta local.
    """
    
    # --- FIX RUTAS WINDOWS ---
    if input_path: input_path = input_path.strip().strip('"').strip("'")
    if output_path: output_path = output_path.strip().strip('"').strip("'")

    # Validar entrada
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        return f"Error: No encuentro el archivo: '{input_path}'"

    # Ruta temporal si no se define salida
    if not output_path:
        nombre_base = os.path.splitext(os.path.basename(input_path))[0]
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"{nombre_base}_CLEAN_{uuid.uuid4().hex[:6]}.pdf")
    
    try:
        # --- PROCESAMIENTO PDF ---
        doc_original = fitz.open(input_path)
        paginas_validas_indices = []
        paginas_eliminadas_count = 0
        
        # 1. Analizar páginas
        for page_num, page in enumerate(doc_original):
            page_dims = page.rect
            area_pagina = page_dims.width * page_dims.height
            
            # Filtros (Horizontal y % Imágenes)
            if page_dims.width > page_dims.height:
                paginas_eliminadas_count += 1
                continue
            
            image_list = page.get_images(full=True)
            area_imagenes = 0
            for img in image_list:
                try:
                    bbox = page.get_image_bbox(img)
                    area_imagenes += bbox.width * bbox.height
                except: continue
            
            if area_pagina > 0 and (area_imagenes / area_pagina) > 0.85:
                paginas_eliminadas_count += 1
                continue
            
            paginas_validas_indices.append(page_num)

        if not paginas_validas_indices:
            doc_original.close()
            return "Error: El documento se quedó sin páginas válidas (todo era publicidad o apaisado)."

        # 2. Reconstruir
        first_page = doc_original[paginas_validas_indices[0]]
        MASTER_W, MASTER_H = first_page.rect.width, first_page.rect.height
        doc_final = fitz.open()

        for idx in paginas_validas_indices:
            page = doc_original[idx]
            rect = page.rect
            # Detección básica de banners en bordes
            y_top, y_bot, x_left, x_right = 0, rect.height, 0, rect.width

            for img_info in page.get_images(full=True):
                try: bb = page.get_image_bbox(img_info)
                except: continue
                if bb.width > rect.width * 0.8: # Banner horiz
                    if bb.y1 < rect.height * 0.25: y_top = max(y_top, bb.y1 + 5)
                    elif bb.y0 > rect.height * 0.75: y_bot = min(y_bot, bb.y0 - 5)
                elif bb.height > rect.height * 0.6: # Banner vert
                    if bb.x1 < rect.width * 0.25: x_left = max(x_left, bb.x1)
                    elif bb.x0 > rect.width * 0.75: x_right = min(x_right, bb.x0)

            clip_rect = rect
            if (x_right - x_left) > 200 and (y_bot - y_top) > 200:
                clip_rect = fitz.Rect(x_left, y_top, x_right, y_bot)

            new_p = doc_final.new_page(width=MASTER_W, height=MASTER_H)
            new_p.show_pdf_page(new_p.rect, doc_original, idx, clip=clip_rect)

        doc_final.save(output_path, garbage=4, deflate=True)
        doc_original.close()
        doc_final.close()
        
        # --- SUBIDA A INTERNET ---
        link, error_msg = subir_a_internet(output_path)
        
        mensaje_base = (f" Limpieza completada (Eliminadas {paginas_eliminadas_count} pags).\n")

        if link:
            return mensaje_base + f" DESCARGA AQUÍ: {link}"
        else:
            # Si falla la subida, mostramos la ruta local de forma muy clara
            return (f"{mensaje_base}"
                    f" NO se pudo subir a internet (Tu red bloquea conexiones de Python).\n"
                    f" TU ARCHIVO ESTÁ AQUÍ ,contacta con el creador (Copia y pega en explorador):\n"
                    f"{output_path}")

    except Exception as e:
        return f"Error crítico: {str(e)}"

if __name__ == "__main__":
    mcp.run()
