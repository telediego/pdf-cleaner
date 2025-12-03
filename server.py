from mcp.server.fastmcp import FastMCP
import fitz  # PyMuPDF
import os
import requests # Necesitamos esta librería para subir el archivo

# Inicializamos el servidor
mcp = FastMCP("PDF Cleaner Wuolah con Enlace")

def subir_a_transfersh(filepath):
    """Sube el archivo a transfer.sh y devuelve el enlace de descarga."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'rb') as f:
            # Transfer.sh permite subir archivos con una simple petición PUT
            response = requests.put(f'https://transfer.sh/{filename}', data=f)
            
        if response.status_code == 200:
            # La respuesta es el enlace directo de descarga
            return response.text.strip()
        else:
            return None
    except Exception as e:
        print(f"Error subiendo archivo: {e}")
        return None

@mcp.tool()
def limpiar_pdf(input_path: str, output_path: str) -> str:
    """
    Limpia un PDF y devuelve un ENLACE DE DESCARGA.
    
    Args:
        input_path: Ruta al archivo PDF original.
        output_path: Ruta donde guardar el temporal (ej: "limpio.pdf").
    """
    
    if not os.path.exists(input_path):
        return f"Error: El archivo no existe: '{input_path}'"

    try:
        doc_original = fitz.open(input_path)
        paginas_validas_indices = []
        paginas_eliminadas_count = 0
        
        # --- FASE 1: Filtrado (Tu lógica original) ---
        for page_num, page in enumerate(doc_original):
            page_dims = page.rect
            area_pagina = page_dims.width * page_dims.height
            
            if page_dims.width > page_dims.height: # Horizontal
                paginas_eliminadas_count += 1
                continue
            
            image_list = page.get_images(full=True)
            area_imagenes = 0
            for img in image_list:
                try:
                    bbox = page.get_image_bbox(img)
                    area_imagenes += bbox.width * bbox.height
                except ValueError: pass
            
            if (area_imagenes / area_pagina if area_pagina > 0 else 0) > 0.85: # Publicidad
                paginas_eliminadas_count += 1
                continue
            
            paginas_validas_indices.append(page_num)

        if not paginas_validas_indices:
            doc_original.close()
            return "Error: No quedaron páginas válidas."

        first_page = doc_original[paginas_validas_indices[0]]
        MASTER_WIDTH = first_page.rect.width
        MASTER_HEIGHT = first_page.rect.height
        doc_final = fitz.open()

        # --- FASE 2: Reconstrucción (Tu lógica original) ---
        for idx in paginas_validas_indices:
            page = doc_original[idx]
            page_dims = page.rect
            y_top, y_bottom = 0, page_dims.height
            x_left, x_right = 0, page_dims.width

            image_list = page.get_images(full=True)
            for img_info in image_list:
                try: bbox = page.get_image_bbox(img_info)
                except ValueError: continue
                
                # Detección de banners (Simplificada para el ejemplo)
                if bbox.width > page_dims.width * 0.8:
                    if bbox.y1 < page_dims.height * 0.25 and bbox.y1 > y_top: y_top = bbox.y1 + 5
                    elif bbox.y0 > page_dims.height * 0.75 and bbox.y0 < y_bottom: y_bottom = bbox.y0 - 5

            ancho_final = x_right - x_left
            alto_final = y_bottom - y_top
            rect_recorte = page_dims if (ancho_final < 200 or alto_final < 200) else fitz.Rect(x_left, y_top, x_right, y_bottom)

            nueva_pagina = doc_final.new_page(width=MASTER_WIDTH, height=MASTER_HEIGHT)
            nueva_pagina.show_pdf_page(nueva_pagina.rect, doc_original, idx, clip=rect_recorte)

        # Guardado local temporal
        doc_final.save(output_path, garbage=0, deflate=True)
        doc_original.close()
        doc_final.close()
        
        # --- NUEVA FASE: SUBIDA A LA NUBE ---
        link_descarga = subir_a_transfersh(output_path)
        
        if link_descarga:
            return f" ¡Éxito! PDF limpiado ({paginas_eliminadas_count} páginas eliminadas).\n\n⬇️ DESCÁRGALO AQUÍ: {link_descarga}"
        else:
            return f" El PDF se limpió y está en '{output_path}' (en el disco del servidor), pero falló la subida para generar el link."

    except Exception as e:
        return f"Error crítico: {str(e)}"

if __name__ == "__main__":
    mcp.run()
