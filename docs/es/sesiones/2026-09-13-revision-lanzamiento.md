# Revisión de lanzamiento - 2026-09-13

## Alcance

Revisó el árbol de origen raíz sincronizado, los contratos actuales, generados
inventario, registros de validación por etapas y metadatos de publicación. El árbol raíz
ahora incluye la fuente candidata más reciente, mientras que los datos de tiempo de ejecución, credenciales,
Los entornos virtuales y las cachés de Python permanecen excluidos de la publicación.

## Implementación actual

- Flujo de sesión de TUI y App Server, incluidas correcciones de compatibilidad de protocolos.
- Las configuraciones del modelo global, el esfuerzo de razonamiento y la ventana de contexto persistieron para los nuevos
  vueltas.
- Aislamiento de contexto por conversación, marcador de uso de token y restablecimiento de punto de control.
- Vistas de evidencia de dominio limpias/sin formato con explicaciones de campo acotadas.
- Terminal normal, aislamiento de carga, inspección de bultos y revisión privilegiada
  contratos de ayuda.
- Actividad en vivo y proyección de streaming con metadatos de herramientas desinfectadas.

## Política de documentación

`current-product-state.md` y `tui-contract.md` son autoridades actuales.
`CHANGELOG.md` es el índice de cambio público. Archivos fechados de fase, auditoría y sesión.
permanecer como procedencia histórica; las instantáneas contradictorias están etiquetadas explícitamente
histórico en lugar de eliminado silenciosamente.

## Validación

- Puerta de entrada de calidad rápida: superada, 26 pruebas.
- Puerta de raíz completa: se alcanzaron 372 pruebas; 371 pasaron y una prueba de socket fue bloqueada
  por la restricción de socket local del sandbox administrado. Esto es ambiental y
  se verificó previamente por separado fuera del sandbox.
- Ruff, inventario generado, verificaciones de documentación y manifiesto de liberación aprobados.
- Inventario raíz final: 832 archivos; el inventario de candidatos en tiempo de ejecución/por etapas permanece
  Se realiza un seguimiento por separado y no forma parte del árbol de publicaciones de GitHub.

## Requisitos previos de publicación

El espacio de trabajo contiene un directorio `.git` vacío, por lo que no hay diferencias o confirmaciones confiables.
El control remoto se puede generar aquí. Antes de ingresar a GitHub, inicialice un Git nuevo
repositorio, revisar `CHANGELOG.md`, inspeccionar la diferencia completa y garantizar el tiempo de ejecución
y las rutas de credenciales permanecen ignoradas. Instalación privilegiada y paquete real o
las mutaciones de arranque permanecen controladas por separado; esta revisión no los certifica.
