# Disponibilidad de paquetes y plan de compatibilidad

> **Nota de estado (2026-08-09):** este documento comenzó como una función de solo lectura
>planificar. El límite del paquete actual implementado, incluido el límite
> instalación de la herramienta de desarrollo, está documentada en
> [`current-product-state.md`](estado-actual-producto.md). Declaraciones debajo de eso
> todas las transacciones de paquetes están deshabilitadas describe el estado de planificación anterior.

## Objetivo

Amplíe el inventario de paquetes TUI desde los RPM instalados a una vista navegable de
paquetes disponibles en los repositorios configurados de Fedora, incluidas versiones,
origen del repositorio, relaciones de dependencia, conflictos, alternativas y
orientación respaldada por evidencia para elegir entre paquetes.

La característica nunca debe instalar, eliminar, actualizar, habilitar o deshabilitar un paquete.
Se trata únicamente de una capacidad de información y planificación.

## 1. Modos de inventario

La vista del paquete existente se convierte en un modo de alternancia:

- **Instalado**: paquetes actualmente en la base de datos RPM local.
- **Disponible**: paquetes anunciados por repositorios habilitados.
- **Combinado**: registros instalados y disponibles unidos por nombre de paquete y
  arquitectura.
- **Actualizaciones**: versiones disponibles más recientes que la versión instalada.

Cada modo conserva las vistas existentes:

- lista completa,
- alfabético,
- categoría/clasificado,
- orientado a un propósito.

Las listas grandes deben paginarse o filtrarse incrementalmente. La TUI nunca debe
renderice un resultado de repositorio ilimitado en un widget de registro.

## 2. Modelo de datos del paquete

Cada registro debe llevar:

- nombre, época/versión/lanzamiento, arquitectura;
- ID del repositorio y prioridad del repositorio;
- proveedor, licencia, URL, resumen, descripción;
- estado instalado y versión instalada;
- tamaño del paquete y tamaño de descarga cuando estén disponibles;
- proporciona, exige, recomienda, complementa, sugiere;
- conflictos, obsolescencias y reemplazos;
- paquete fuente y metadatos de compilación cuando estén disponibles;
- clasificación de categorías y finalidades;
- fuente de evidencia, tiempo de recuperación, antigüedad del caché y estado de actualización.

La clave de identidad del paquete es `(name, epoch, version, release, arch, repository)`.

## 3. Análisis de compatibilidad y “mismo propósito”

El análisis debe distinguir tres relaciones:

### Relaciones autorizadas entre el administrador de paquetes

Leer directamente de los metadatos de RPM/DNF:

- conflictos difíciles;
- obsoletos;
- requisitos insatisfechos;
- arquitecturas incompatibles;
- proveedores mutuamente excluyentes;
- fallos de dependencia a nivel de transacción.

Estos se informan como **metadatos autorizados**, con el paquete exacto
campo del gerente que causó la relación.

### Alternativas funcionales

Los paquetes que proporcionan la misma capacidad se agrupan mediante:

- nombres virtuales `Provides` idénticos;
- Grupos/entornos de paquetes de Fedora;
- metadatos de funciones de escritorio o hardware;
- reemplazo explícito/metadatos alternativos.

Estos se informan como **candidatos alternativos**, no como conflictos. dos
Los paquetes pueden tener el mismo propósito y aún así poder instalarse juntos.

### Similitud inferida

El nombre, el resumen, la categoría, el ejecutable, la biblioteca y la similitud de la documentación pueden
identificar paquetes con propósitos superpuestos. Esto es sólo una **inferencia** y
Nunca debe presentarse como una regla de compatibilidad.

La interfaz de usuario debe mostrar una explicación de la relación, como por ejemplo:

> `package-a` y `package-b` entran en conflicto porque los metadatos RPM declaran `Conflicts:`.

o:

> `package-a` y `package-b` son alternativas porque ambos proporcionan
> `video-driver`.

## 4. Repositorio y fuentes de versión

### Fuentes locales, fuera de la red

- Base de datos RPM para metadatos instalados;
- metadatos del repositorio DNF en caché, si están presentes;
- historial de transacciones DNF local;
- archivos de paquetes locales y datos de propiedad.

### Fuentes explícitamente conectadas a la red

- metadatos del repositorio Fedora actualmente habilitados;
- avisos de seguridad y actualización;
- Documentación del paquete Fedora y metadatos del ciclo de vida.

La actualización de la red debe ser una acción separada y claramente etiquetada que requiera
confirmación del usuario. Un resultado almacenado en caché debe mostrar su marca de tiempo y su repositorio.
Estado de caducidad de los metadatos.El sistema nunca debe pretender recomendaciones “100% confiables”. En lugar de eso debería
Utilice etiquetas de evidencia:

- **Observado**: lectura directa desde el estado RPM/DNF local;
- **Obtenido**: compatible con documentación o metadatos de Fedora/RPM/DNF;
- **Inferido**: derivado de nombres, capacidades o similitudes;
- **Desconocido**: pruebas insuficientes o obsoletas.

## 5. Orientación sobre la base de conocimientos

JARVIS puede responder preguntas sobre selección de paquetes utilizando un conocimiento estructurado.
registro que contiene:

- objetivo del usuario y carga de trabajo;
- paquetes de candidatos;
- capacidades requeridas;
- restricciones de compatibilidad;
- relevancia del hardware;
- referencias de evidencia y marcas de tiempo de recuperación;
- fundamento de la recomendación;
- alternativas consideradas;
- incertidumbre y pruebas faltantes.

Las recomendaciones deben ser comparativas y reversibles. JARVIS puede explicar qué
El paquete se adapta mejor a una carga de trabajo, pero no puede instalar la recomendación a través de
esta característica.

## 6. Diseño TUI

Agregue un selector de modo de paquete con:

- Instalado / Disponible / Combinado / Actualizaciones;
- Vistas completas/alfabéticas/clasificadas/propósito;
- filtros de categorías como NVIDIA/GPU, Intel, GNOME, iluminación, kernel,
  desarrollo, audio, redes, virtualización, seguridad y otros;
- filtros de arquitectura y repositorio;
- filtros “mostrar conflictos”, “mostrar alternativas” y “mostrar actualizaciones”;
- panel de detalles del paquete con dependencias, conflictos, archivos, repositorio y
  etiquetas de evidencia;
- indicadores de caché obsoleta y de red requerida;
- búsqueda y paginación acotadas.

La opción de lista completa expande la lista instalada actual a la lista seleccionada
alcance disponible/combinado sin eliminar las vistas ordenadas existentes.

## 7. Límites de seguridad y autoridad

- No se permite instalar, eliminar, actualizar, degradar, borrar ni ejecutar transacciones.
- Sin shell ni entrada de comando arbitrario.
- Se corrigieron los formularios de consulta `rpm`/`dnf` únicamente, con tiempo de espera y límites de salida.
- Actualización de red deshabilitada a menos que se apruebe por separado.
- Ninguna recomendación de paquete puede convertirse silenciosamente en una aprobación o transacción.
- Los metadatos del repositorio y las descripciones de los paquetes son entradas que no son de confianza.
- Los volcados del repositorio sin procesar no deben persistir; almacenar registros normalizados y acotados.

## 8. Fases de entrega

1. Agregue analizadores de versiones y paquetes disponibles utilizando metadatos almacenados en caché.
2. Agregue conflicto RPM autorizado/proporciona/obsoleta la extracción de gráficos.
3. Agregue la actualización del repositorio como una operación independiente y consciente de la red.
4. Agregue modos combinados/actualizados, paginación, filtros y vistas detalladas.
5. Agregue registros de recomendación y compatibilidad vinculados a evidencia.
6. Agregue revisión independiente de solo lectura y pruebas de analizador contradictorio.
7. Mantenga todas las transacciones de paquetes deshabilitadas hasta que se inicie un proyecto de mutación separado.
   aprobado.

## Criterios de finalización

- Se distinguen claramente los modos instalados y disponibles.
- Funcionan vistas completas, alfabéticas, clasificadas, de propósito, combinadas y de actualizaciones.
- Datos de versión, repositorio, dependencia, conflicto, alternativa y propiedad
  son explicables y acotados.
- Los conflictos de autoridad nunca se combinan con similitudes inferidas.
- El estado obsoleto/caché/red es visible.
- Las recomendaciones del paquete incluyen etiquetas de evidencia e incertidumbre.
- No existe ninguna transacción de paquete ni ruta de mutación.
- Pruebas VM/TUI, verificación de manifiesto y pase de revisión independiente.
