Prompts

**\#1 PLAN INICIAL**  
Quiero crear una herramienta web para agentes inmobiliarios llamada "ListaPro".   
La idea es que un agente pueda llenar un formulario con los datos de una   
propiedad y automáticamente se genere contenido profesional para publicar.

El negocio es una agencia inmobiliaria en México que vende y renta propiedades   
residenciales (casas, departamentos, terrenos). Los agentes publican entre   
3-5 propiedades por semana y actualmente hacen todo manual en Canva y Word.

Lo que necesito en esta primera versión:

FORMULARIO WEB con estos campos:  
\- Tipo de propiedad (Casa, Departamento, Terreno, Penthouse)  
\- Operación (Venta o Renta)  
\- Dirección / ubicación  
\- Ciudad y estado  
\- Precio (en MXN)  
\- Recámaras, baños, metros construidos, metros de terreno  
\- Estacionamientos    
\- Amenidades (checkboxes: alberca, jardín, seguridad 24h, gimnasio, etc.)  
\- Descripción breve del agente (2-3 líneas de lo que destaca)  
\- Subir fotos de la propiedad (mínimo 1 portada \+ extras)  
\- Datos del agente: nombre, teléfono, email

GENERACIÓN CON IA (OpenAI):  
\- Que genere una descripción profesional y atractiva de la propiedad   
  usando los datos del formulario  
\- Un copy optimizado para Instagram con hashtags relevantes del sector   
  inmobiliario en México

PÁGINA DE RESULTADOS:  
\- Mostrar la descripción generada  
\- Mostrar el copy de Instagram listo para copiar  
\- Botón de copiar al portapapeles

Stack técnico: Python con FastAPI para el backend, HTML/CSS simple para   
el frontend, API de OpenAI para los textos. Todo debe correr en localhost.

**\#2 GENERAR PDF**

Agrega generación de PDF al proyecto. Cuando el agente genere un listado,   
que automáticamente se cree un PDF descargable con:

\- Las fotos de la propiedad (la portada grande arriba, las extras más pequeñas)  
\- La descripción profesional generada por IA  
\- Los datos clave en un formato visual: precio, recámaras, baños, m2,   
  estacionamientos  
\- Las amenidades del inmueble  
\- Los datos de contacto del agente (nombre, teléfono, email)

Que el diseño sea limpio y organizado, con un encabezado de color.   
Agrega un botón de "Descargar PDF" en la página de resultados.

**\#3 IMAGENES**

Agrega generación de una imagen cuadrada (1080x1080) para publicar en   
Instagram. Que use la foto de portada de la propiedad como fondo, con   
un gradiente oscuro encima para que el texto se lea bien.

La imagen debe mostrar:  
\- Un badge con "En Venta" o "En Renta" según la operación  
\- El precio destacado  
\- La ubicación  
\- Iconos con los datos principales (recámaras, baños, m2)

Usa Pillow para generarla. Agrega un botón de descarga en la página   
de resultados junto al PDF.

**\#4 PUBLICAR A INSTA**

Agrega un botón de "Publicar en Instagram" en la página de resultados   
que suba la imagen generada directamente a Instagram como post.

Usa la API de Upload Post (POST https://api.upload-post.com/api/upload)   
con estos parámetros en multipart form-data:  
\- user: el identificador del usuario  
\- platform\[\]: "instagram"  
\- video o imagen: el archivo generado  
\- title: el copy de Instagram que ya generamos

El header de autenticación es: Authorization: Apikey {tu-api-key}

Agrega la variable UPLOADPOST\_API\_KEY al archivo .env. Muestra un   
mensaje de éxito o error después de publicar.

**\#5 VIDEO**

Agrega generación de un video reel vertical (1080x1920) para Instagram   
y TikTok usando Remotion (React).

El video debe:  
\- Mostrar las fotos de la propiedad con transiciones suaves (fade, zoom)  
\- Cada foto se muestra 3-4 segundos con efecto Ken Burns (zoom lento)  
\- Texto animado sobre las fotos: precio, ubicación, datos principales  
\- Una pantalla final con los datos de contacto del agente  
\- Duración total: 20-30 segundos  
\- Música de fondo (un archivo mp3 que yo ponga)

Instala Remotion en una carpeta "video/" dentro del proyecto. El backend   
debe pasar las fotos y los datos al componente de React, renderizar el   
video con Remotion, y guardar el .mp4 para descargarlo desde la página   
de resultados.

Agrega un botón de "Generar Video" en los resultados con un indicador   
de progreso mientras se renderiza.

