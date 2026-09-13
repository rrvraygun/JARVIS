# Lanzamiento y actualización automática

1. Construir en una rama o árbol de trabajo aislado, nunca directamente en el perfil activo.
2. Validar habilidades, complementos, configuración, esquemas, pruebas de políticas, enlaces, protocolo MCP,
   redacción, integridad del libro mayor y accesorios de fallas representativas.
3. Genere `release-manifest.json` y revise las diferencias de permiso/capacidad.
4. Obtener una revisión de seguridad independiente para políticas, ganchos, MCP, aprobación, auditoría,
   o cambios de privilegios.
5. Cree una versión inmutable versionada y conserve la versión anterior.
6. Solicitar aprobación vinculada al resumen del manifiesto de publicación.
7. Activar atómicamente mediante un puntero o cambio de nombre de directorio.
8. Validar desde un proceso separado. En caso de error en el inicio, la política, el MCP o el libro mayor,
   bloquear la activación y preparar una recuperación exacta aprobada por separado; nunca vuelva a intentarlo ni retroceda automáticamente.
9. Registre externamente el lanzamiento, el revisor, la aprobación, la activación y el resultado.

El agente puede proponer y preparar una actualización, pero no puede aprobar ni dar fe únicamente
a su propia actualización. Nunca actualice automáticamente desde una rama no fijada o una URL mutable.
