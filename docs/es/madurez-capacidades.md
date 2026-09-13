# Modelo de madurez de capacidad

| Etapa | Significado | Uso permitido |
|---|---|---|
| 0 Definido | Existen instrucciones y esquema | Sólo documentación |
| 1 Validado | Pasan las pruebas estáticas y unitarias | Uso de accesorios |
| 2 ensayado | Accesorios representativos y pase de ensayo de no producción; VM/contenedor opcional cuando sea útil | Laboratorio supervisado o objetivo de rasguño aislado |
| 3 Observado | La evidencia de producción de solo lectura funciona | Observación en vivo |
| 4 Supervisado | La mutación probada en recuperación funciona | Aprobación humana exacta |
| 5 Automatizado | Pruebas repetidas y auditoría externa | Política estrecha preaprobada |

Ninguna capacidad avanza porque la marca parece confiada. La promoción requiere
evaluaciones registradas, aprobación del propietario, reversión conocida y una política versionada
cambiar. Autoactualización, seguridad, arranque, firmware, identidad, cifrado, almacenamiento y
Es posible que las capacidades de acceso remoto nunca pasen por alto la revisión independiente.

La implementación del host directo puede avanzar en un procedimiento reversible de tipo restringido
a la etapa 4 después de pruebas de accesorios representativas, verificadas específicas de la acción
recuperación, aprobación exacta y validación independiente del host en vivo. Una máquina virtual no es una
puerta de promoción universal porque no puede representar una estación de trabajo física
rutas de hardware. Aprobaciones de trámites y transacciones y la caja fuerte preautorizada
La lista permanece deshabilitada hasta que un procedimiento específico llegue a la etapa 5. Lección
la promoción está separada de la madurez de ejecución: la evidencia automatizada puede crear un
candidato, pero sólo el usuario lo activa.
