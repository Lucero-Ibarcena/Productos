# Ronda

Comparador de precios en español para Carrefour, Jumbo, Disco, Vea, ChangoMás y Día. Busca en los catálogos online al momento, muestra fotos publicadas por las tiendas, permite filtrar supermercados y guardar una lista de compras con totales estimados.

## Cómo abrirla

1. Instalá Python 3.9 o posterior si todavía no está instalado.
2. Abrí PowerShell en esta carpeta y ejecutá `py server.py`.
3. Abrí <http://127.0.0.1:8765> en el navegador.
4. Para apagar el servidor, volvé a PowerShell y presioná `Ctrl+C`.

El servidor usa solo bibliotecas incluidas con Python. Tiene que quedar abierto mientras usás la aplicación.

## Datos y alcance

- Cada búsqueda consulta los seis catálogos públicos en paralelo. La respuesta se conserva en memoria durante 35 segundos para reducir consultas repetidas.
- La pantalla enumera cada supermercado y su estado: con precios encontrados, catálogo disponible sin coincidencias o sin respuesta.
- Se muestran precios publicados por las tiendas y se descartan artículos marcados sin stock. Cada precio enlaza a la ficha de origen, y la foto proviene del catálogo de producto.
- La lista de compras se guarda en el navegador. Sus totales por cadena muestran cuántos productos tienen precio; un total incompleto se identifica como parcial.
- Los catálogos no están fijados a una sucursal o código postal. Precio, disponibilidad y promociones pueden variar por zona.
- Los resultados se agrupan por marca, tamaño y tipo detectados en el nombre. Revisá el envase y la variante en la tienda antes de comprar.
- La cobertura depende de que cada supermercado mantenga disponible su catálogo público. No se incluyen tiendas para las que no se pudo verificar una búsqueda de productos con precios.
