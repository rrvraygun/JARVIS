# Atrasos en la estabilización

Aquí sólo podrán permanecer trabajos medios/bajos. Los hallazgos críticos y elevados bloquean la
registro de finalización de la estabilización.

| Prioridad | Artículo | Criterio de salida |
| --- | --- | --- |
| M1 | Extraiga los controladores de flujo de trabajo de paquete, energía/iluminación, conversación y envío de `app.py`. | `app.py` posee únicamente el cableado de composición/evento; Las pruebas de regresión del flujo de trabajo permanecen en verde. |
| M1 | Ingestión de transporte de sesión dividida desde contexto/orquestación de turnos. | Las pruebas de ingreso limitado y de estado de giro se dirigen a módulos separados. |
| M1 | Fortalezca la propiedad de la raíz del almacén de MCP, los archivos temporales y el esquema/tamaño de la carga útil de eventos. | Las pruebas de carga útil de enlace simbólico, raíz sin propietario, con formato incorrecto y de gran tamaño fallan al cerrarse. |
| M1 | Reemplace las rutas de enlace/proyecto codificadas con la configuración de implementación revisada. | La configuración de inicio y enlace funciona desde una raíz de paquete configurada y validada. |
| M2 | Reemplace las capturas de interfaz de usuario amplias restantes con diagnósticos seguros escritos. | Ninguna excepción/rastreo sin procesar llega a la conversación o a la línea de tiempo. |
| M2 | Establezca una base de cobertura documentada y aplique una cobertura de sucursales del 90 % para los módulos de autoridad. | Quality Gate analiza la cobertura JSON y falla por debajo del umbral acordado. |
| M2 | Archivar los documentos de fase claramente reemplazados en `docs/history/`. | Cada documento movido tiene un banner y todos los enlaces locales se validan. |
| L1 | Normalice el estilo residual y las advertencias de escritura. | Cada regla es fija o tiene una supresión limitada y justificada. |
