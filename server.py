from mcp.server.fastmcp import FastMCP
import fitz  # PyMuPDF
import os

# Inicializamos el servidor MCP
mcp = FastMCP("PDF Cleaner Wuolah")

@mcp.tool()
def limpiar_pdf(input_path: str, output_path: str) -> str:
    """
    Limpia un PDF eliminando publicidad y páginas horizontales. 
    Ideal para documentos de Wuolah.
    
    Args:
        input_path: Ruta completa al archivo PDF original.
        output_path: Ruta completa donde se guardará el PDF limpio.
    """
    
    # --- Tu lógica original comienza aquí (adaptada ligeramente para retorno) ---
    if not os.path.exists(input_path):
        return f"Error: El archivo no existe: '{input_path}'"

    try:
        doc_original = fitz.open(input_path)
        paginas_validas_indices = []
        paginas_eliminadas_count = 0
        
        # FASE 1: Filtrado
        for page_num, page in enumerate(doc_original):
            page_dims = page.rect
            area_pagina = page_dims.width * page_dims.height
            
            # 1. Filtro: Orientación Horizontal
            if page_dims.width > page_dims.height:
                paginas_eliminadas_count += 1
                continue
            
            # 2. Filtro: Saturación de Imágenes
            image_list = page.get_images(full=True)
            area_imagenes = 0
            for img in image_list:
                try:
                    bbox = page.get_image_bbox(img)
                    area_imagenes += bbox.width * bbox.height
                except ValueError:
                    pass
            
            porcentaje_imagen = area_imagenes / area_pagina if area_pagina > 0 else 0
            if porcentaje_imagen > 0.85:
                paginas_eliminadas_count += 1
                continue
            
            paginas_validas_indices.append(page_num)

        if not paginas_validas_indices:
            doc_original.close()
            return "Error: No quedaron páginas válidas tras el filtrado."

        # Configuración del tamaño maestro
        first_page = doc_original[paginas_validas_indices[0]]
        MASTER_WIDTH = first_page.rect.width
        MASTER_HEIGHT = first_page.rect.height
        
        doc_final = fitz.open()

        # FASE 2: Reconstrucción
        for idx in paginas_validas_indices:
            page = doc_original[idx]
            page_dims = page.rect
            
            y_top = 0
            y_bottom = page_dims.height
            x_left = 0
            x_right = page_dims.width

            # Detectar Banners (Lógica simplificada para brevedad, usando tu código base)
            image_list = page.get_images(full=True)
            for img_info in image_list:
                try:
                    bbox = page.get_image_bbox(img_info)
                except ValueError:
                    continue

                w_img = bbox.width
                h_img = bbox.height
                
                # Banner Horizontal
                if w_img > page_dims.width * 0.8:
                    if bbox.y1 < page_dims.height * 0.25:
                        if bbox.y1 > y_top: y_top = bbox.y1 + 5
                    elif bbox.y0 > page_dims.height * 0.75:
                        if bbox.y0 < y_bottom: y_bottom = bbox.y0 - 5
                # Banner Vertical
                elif h_img > page_dims.height * 0.6:
                    if bbox.x1 < page_dims.width * 0.25:
                         if bbox.x1 > x_left: x_left = bbox.x1
                    elif bbox.x0 > page_dims.width * 0.75:
                        if bbox.x0 < x_right: x_right = bbox.x0

            # SAFETY CHECK
            ancho_final = x_right - x_left
            alto_final = y_bottom - y_top
            
            if ancho_final < 200 or alto_final < 200:
                rect_recorte = page_dims
            else:
                rect_recorte = fitz.Rect(x_left, y_top, x_right, y_bottom)

            nueva_pagina = doc_final.new_page(width=MASTER_WIDTH, height=MASTER_HEIGHT)
            nueva_pagina.show_pdf_page(
                nueva_pagina.rect,
                doc_original,
                idx,
                clip=rect_recorte
            )

        doc_final.save(output_path, garbage=0, deflate=True)
        doc_original.close()
        doc_final.close()
        
        return f"¡Éxito! PDF limpio guardado en: {output_path}. Se eliminaron {paginas_eliminadas_count} páginas."

    except Exception as e:
        return f"Error crítico al procesar el PDF: {str(e)}"

# Esto permite ejecutar el servidor
if __name__ == "__main__":
    mcp.run()