# Solución de envío de saludo especializado

La corrección anterior solo para clasificadores omitió broker.prepare_turn_request, que aún
enviado readOnly.access. También se eliminó ese campo del despacho de especialistas,
conservando readOnly/networkAccess=false y las aprobaciones granulares existentes.
El alcance de lectura nativo del usuario actual está documentado en tui-contract.md.

Luego, una sonda en vivo expuso otro rechazo de protocolo:
AskForApproval.granular requiere capacidad experimentalApi. Inicialización ahora
declara experimentalApi=true; no se otorga autoridad de ejecución ni aprobación por
esa negociación. Las pruebas cubren el protocolo de enlace y las cargas útiles de permisos exactos.

Después de la segunda corrección, una sesión de App Server autenticada por separado usando
El propio perfil del candidato aceptó un saludo fijo, respondió "¡Oye!" y
Estado de giro informado completado con error = nulo. Esta sonda ejerció la vida.
transporte y modelo utilizando la carga útil del permiso de envío, no un clic completo de TUI
flujo o una operación privilegiada. No se copiaron ni imprimieron ninguna credencial.

Validación final enfocada: 46 pruebas aprobadas entre App Server, broker y sesión.
Dispatch_review independiente revisó la corrección del permiso. existente
se conservaron conversaciones y registros de auditoría fallidos; no se repitió ninguna tarea fallida.
Reinicie JARVIS para cargar los módulos corregidos y enviar un nuevo saludo.
