from mcp.server.fastmcp import FastMCP
import fitz  # PyMuPDF
import os
import requests  # Necesario para la subida
import sys

# Inicializamos el servidor
mcp = FastMCP("PDF Cleaner Wuolah")

def subir_a_transfersh(filepath: str) -> str | None:
    """
    Sube el archivo a transfer.sh y devuelve el enlace de descarga.
    """
    try:
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        # Abrimos el archivo en modo lectura binaria
        with open(filepath, 'rb') as f:
            # Transfer.sh usa PUT para subir archivos
            response = requests.put(f'https://transfer.sh/{filename}', data=f)
            
        if response.status_code == 200:
            return response.text.strip()
        else:
            return None
    except Exception as e:
        print(f"Error subiendo archivo: {e}")
        return None

@mcp.tool()
def limpiar_pdf(input_path: str, output_path: str) -> str:
    """
    Limpia un PDF, lo guarda temporalmente y genera un LINK DE DESCARGA.
    
    Args:
        input_path: Ruta completa al archivo PDF original.
        output_path: Ruta completa donde se guardará el PDF limpio localmente.
    """
    # 1. Asegurar rutas absolutas
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        return f"Error: El archivo no existe: '{input_path}'"

    try:
        doc_original = fitz.open(input_path)
        paginas_validas_indices = []
        paginas_eliminadas_count = 0
        
        # --- FASE 1: Filtrado ---
        for page_num, page in enumerate(doc_original):
            page_dims = page.rect
            area_pagina = page_dims.width * page_dims.height
            
            # Filtro Horizontal
            if page_dims.width > page_dims.height:
                paginas_eliminadas_count += 1
                continue
            
            # Filtro Imágenes
            image_list = page.get_images(full=True)
            area_imagenes = 0
            for img in image_list:
                try:
                    bbox = page.get_image_bbox(img)
                    area_imagenes += bbox.width * bbox.height
                except Exception:
                    continue
            
            porcentaje_imagen = area_imagenes / area_pagina if area_pagina > 0 else 0
            if porcentaje_imagen > 0.85:
                paginas_eliminadas_count += 1
                continue
            
            paginas_validas_indices.append(page_num)

        if not paginas_validas_indices:
            doc_original.close()
            return "Error: No quedaron páginas válidas tras el filtrado."

        # Configuración Maestro
        first_page = doc_original[paginas_validas_indices[0]]
        MASTER_WIDTH = first_page.rect.width
        MASTER_HEIGHT = first_page.rect.height
        
        doc_final = fitz.open()

        # --- FASE 2: Reconstrucción ---
        for idx in paginas_validas_indices:
            page = doc_original[idx]
            page_dims = page.rect
            
            y_top, y_bottom = 0, page_dims.height
            x_left, x_right = 0, page_dims.width

            image_list = page.get_images(full=True)
            for img_info in image_list:
                try:
                    bbox = page.get_image_bbox(img_info)
                except ValueError:
                    continue

                w_img, h_img = bbox.width, bbox.height
                
                # Detección Banners
                if w_img > page_dims.width * 0.8:
                    if bbox.y1 < page_dims.height * 0.25: y_top = max(y_top, bbox.y1 + 5)
                    elif bbox.y0 > page_dims.height * 0.75: y_bottom = min(y_bottom, bbox.y0 - 5)
                elif h_img > page_dims.height * 0.6:
                    if bbox.x1 < page_dims.width * 0.25: x_left = max(x_left, bbox.x1)
                    elif bbox.x0 > page_dims.width * 0.75: x_right = min(x_right, bbox.x0)

            if (x_right - x_left) < 200 or (y_bottom - y_top) < 200:
                rect_recorte = page_dims
            else:
                rect_recorte = fitz.Rect(x_left, y_top, x_right, y_bottom)

            nueva_pagina = doc_final.new_page(width=MASTER_WIDTH, height=MASTER_HEIGHT)
            nueva_pagina.show_pdf_page(nueva_pagina.rect, doc_original, idx, clip=rect_recorte)

        # GUARDADO LOCAL (Garbage=4 reduce el peso para subirlo más rápido)
        doc_final.save(output_path, garbage=4, deflate=True)
        doc_original.close()
        doc_final.close()
        
        # --- FASE 3: Subida a la Nube ---
        link_descarga = subir_a_transfersh(output_path)
        
        if link_descarga:
            return (f"✅ ¡Éxito! PDF limpiado ({paginas_eliminadas_count} páginas eliminadas).\n"
                    f"📂 Guardado local: {output_path}\n"
                    f"⬇️ ENLACE DE DESCARGA: {link_descarga}")
        else:
            return (f"⚠️ El PDF se limpió correctamente en '{output_path}', "
                    f"pero falló la subida a Transfer.sh.")

    except Exception as e:
        return f"Error crítico: {str(e)}"

# Entry Point
def main():
    mcp.run()

if __name__ == "__main__":
    main()
