# Visibilidad de los resultados del perfil de energía — 2026-08-30

## Resultado

Se implementó el segmento de resultados de la aplicación Power Expert. Ayudante de perfil verificado
las respuestas ahora producen un `PowerProfileApplicationRecord` atómico por usuario con
valores pre/solicitados/resultantes, comparaciones de control de tres vías, valores omitidos,
estado, resumen, marca de tiempo y metadatos de recuperación. Reiniciar la restauración carga el
último registro aplicado válido e ignora los registros con formato incorrecto o que no coinciden con el resumen.

La pestaña Energía etiqueta la variante de CA/batería seleccionada automáticamente, mantiene la
El resultado aplicado está separado del borrador actual y utiliza la misma capacidad de respuesta.
regiones de inventario/configuración. La activación verificada agrega un AGENTE detallado
confirmación de la conversación, que persiste a través de la existente
administrador de conversaciones y está disponible para el contexto posterior de Power Expert.

## Evidencia de validación

- `PYTHONPATH=tui/src python3 -m unittest tui.tests.test_power_profiles tui.tests.test_power_control_client tui.tests.test_presentation`: 29 aprobados.
- `PYTHONPATH=tui/src python3 -m unittest discover -s tui/tests -p 'test_*.py' -k power`: 13 aprobados, 4 saltados.
- Descubrimiento completo de TUI: 250 pruebas, 217 aprobadas, 32 omitidas, 1 error de entorno: el entorno de pruebas denegó el enlace del socket de prueba de solo lectura (`PermissionError: [Errno 1] Operation not permitted`).
- Se aprobó la verificación de Ruff y el formato para todos los archivos Python modificados.
- Se aprobó el contrato de documentación, el inventario de base de código regenerado y el manifiesto de lanzamiento de 744 entradas regenerado/verificado.

No se utilizó ningún asistente de energía del host, administrador de paquetes, servicio ni operación privilegiada.
activado. Las rutas existentes de aprobación y reversión de un solo uso permanecen sin cambios.
