from mcp.server.fastmcp import FastMCP
import fitz  # PyMuPDF
import os
import requests
import tempfile
import uuid

# Inicializamos el servidor
mcp = FastMCP("PDF Cleaner Wuolah")

def subir_a_transfersh(filepath: str) -> str | None:
    """Sube el archivo a transfer.sh y devuelve el enlace."""
    try:
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            # Transfer.sh permite PUT directo
            response = requests.put(f'https://transfer.sh/{filename}', data=f)
            
        if response.status_code == 200:
            return response.text.strip()
        return None
    except Exception as e:
        print(f"Error subiendo: {e}")
        return None

@mcp.tool()
def limpiar_pdf(input_path: str, output_path: str = None) -> str:
    """
    Limpia un PDF de Wuolah y devuelve un ENLACE DE DESCARGA.
    
    Args:
        input_path: Ruta al archivo PDF original.
        output_path: (Opcional) Ruta para guardar el archivo. Si no se indica, usa un temporal.
    """
    # Validar entrada
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        return f"Error: No encuentro el archivo: '{input_path}'"

    # Si no nos dan ruta de salida, creamos un temporal seguro
    if not output_path:
        nombre_base = os.path.splitext(os.path.basename(input_path))[0]
        temp_dir = tempfile.gettempdir()
        # Añadimos un ID único para evitar colisiones si se limpia el mismo archivo 2 veces
        output_path = os.path.join(temp_dir, f"{nombre_base}_CLEAN_{uuid.uuid4().hex[:6]}.pdf")
    
    try:
        doc_original = fitz.open(input_path)
        paginas_validas_indices = []
        paginas_eliminadas_count = 0
        
        # --- FASE 1: Filtrado ---
        for page_num, page in enumerate(doc_original):
            page_dims = page.rect
            area_pagina = page_dims.width * page_dims.height
            
            # Filtro 1: Horizontal
            if page_dims.width > page_dims.height:
                paginas_eliminadas_count += 1
                continue
            
            # Filtro 2: Imágenes (Publicidad)
            image_list = page.get_images(full=True)
            area_imagenes = 0
            for img in image_list:
                try:
                    bbox = page.get_image_bbox(img)
                    area_imagenes += bbox.width * bbox.height
                except Exception: continue
            
            porcentaje = area_imagenes / area_pagina if area_pagina > 0 else 0
            if porcentaje > 0.85:
                paginas_eliminadas_count += 1
                continue
            
            paginas_validas_indices.append(page_num)

        if not paginas_validas_indices:
            doc_original.close()
            return "Error: El documento se quedó sin páginas válidas (quizás era todo publicidad)."

        # --- FASE 2: Reconstrucción ---
        first_page = doc_original[paginas_validas_indices[0]]
        MASTER_W, MASTER_H = first_page.rect.width, first_page.rect.height
        doc_final = fitz.open()

        for idx in paginas_validas_indices:
            page = doc_original[idx]
            rect = page.rect
            y_top, y_bot = 0, rect.height
            x_left, x_right = 0, rect.width

            # Detectar banners (lógica simplificada)
            for img_info in page.get_images(full=True):
                try: bb = page.get_image_bbox(img_info)
                except ValueError: continue
                
                if bb.width > rect.width * 0.8: # Banner horiz
                    if bb.y1 < rect.height * 0.25: y_top = max(y_top, bb.y1 + 5)
                    elif bb.y0 > rect.height * 0.75: y_bot = min(y_bot, bb.y0 - 5)
                elif bb.height > rect.height * 0.6: # Banner vert
                    if bb.x1 < rect.width * 0.25: x_left = max(x_left, bb.x1)
                    elif bb.x0 > rect.width * 0.75: x_right = min(x_right, bb.x0)

            # Validar recorte
            clip_rect = rect
            if (x_right - x_left) > 200 and (y_bot - y_top) > 200:
                clip_rect = fitz.Rect(x_left, y_top, x_right, y_bot)

            new_p = doc_final.new_page(width=MASTER_W, height=MASTER_H)
            new_p.show_pdf_page(new_p.rect, doc_original, idx, clip=clip_rect)

        # Guardar y Optimizar
        doc_final.save(output_path, garbage=4, deflate=True)
        doc_original.close()
        doc_final.close()
        
        # --- FASE 3: Subida ---
        link = subir_a_transfersh(output_path)
        
        # Opcional: Borrar el archivo local después de subir para no llenar el disco
        # os.remove(output_path) 
        
        if link:
            return (f"✅ ¡Limpieza completada!\n"
                    f"🗑️ Páginas eliminadas: {paginas_eliminadas_count}\n"
                    f"🔗 **ENLACE DE DESCARGA:** {link}")
        else:
            return f"⚠️ PDF limpiado en local ({output_path}), pero falló la subida a Transfer.sh."

    except Exception as e:
        return f"Error crítico: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
