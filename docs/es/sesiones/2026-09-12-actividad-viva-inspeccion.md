# Inspección de paquetes y actividad en vivo.

Fallo de MCP observado: se devolvieron inspect_packages
herramienta_no_autorizada_para_especialista_seleccionado. El especialista en instalación omitió
ese alias de solo lectura existente. Lo agregó sin agregar capacidades de mutación.

El enlace de consultas de observación reciente ahora permite conjuntos de términos de paquetes normalizados iguales,
incluidos los alias node/nodejs y go/golang, en lugar de requerir bytes idénticos
lenguaje natural. Se mantienen las comprobaciones de tarea/generación, caducidad y actualización. No relacionado,
Las consultas obsoletas y parciales de paquetes múltiples no pueden satisfacer la verificación de observación.
Las cargas útiles no disponibles o de error ya no generan un recibo de observación reciente.

Una llamada MCP de alcance real inspect_packages(query=node, refresco=true) tuvo éxito con
disponible=verdadero, obsoleto=falso y frescura_observación=verdadero. Partidos instalados incluidos
nodejs22 22.23.1 y nodejs24 24.18.0. No se ejecutó ninguna instalación de paquete. este ejercido
el MCP/backend real; No fue un turno de inspección de UI basado en modelos completos.

El texto de inspección no verificado se convierte en un evento de actividad sin texto de chat. Eliminado
el repetido reemplazo enlatado "Sin observación reciente registrada". No compatible
las reclamaciones siguen retenidas; el fracaso es visible en la actividad, no reportado como éxito.

El indicador en vivo sobre el chat se actualiza cada 100 ms y muestra la fase, el tiempo transcurrido,
recuentos de fragmentos/caracteres y hasta cuatro herramientas recientes con nombres, consultas y estados
y tiempo transcurrido. Las respuestas completas conservan cada fragmento; el primero cada veinte
Se eliminó el filtro de fragmentos. Las tarjetas de herramientas muestran los nombres de las herramientas MCP y la consulta limitada
metadatos, sin copiar resultados sin procesar ni razonamientos privados. desconectado o
Las herramientas terminadas que carecen de eventos de finalización se detienen con un resultado desconocido.

Validación: 107 sesiones enfocadas/presentación/reductor/gobernado/pruebas de especialista,
Pasaron 38 pruebas gráficas (66,025 segundos) y una regresión de actividad terminal.
La prueba gráfica comprueba la retención de secuencias cortas, la visualización de herramientas/consultas y los fallos.
Estado y ausencia de chat fijo. Inspección_revisión independiente identificada
cobertura de consultas parciales y problemas con spinner inacabados; ambos fueron arreglados y probados.

Se conservan los registros de conversaciones/auditoría existentes. Reinicie el candidato para cargar
los módulos actualizados. Los asistentes raíz instalados y las políticas de Polkit no se modificaron.
