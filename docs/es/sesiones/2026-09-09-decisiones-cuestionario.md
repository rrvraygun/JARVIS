# Decisiones del usuario: cuestionario de cierre

Las 15 preguntas fueron respondidas a través del selector de esta conversación. Estos
las decisiones definen el alcance del producto; no son aprobaciones para comandos,
instalaciones, eliminaciones o cambios en el sistema.

| No. | Decisión aceptada |
| --- | --- |
| 1 | Elija un kernel instalado para el próximo arranque y repare initramfs para un kernel específico. |
| 2 | Prepare cualquier actualización necesaria: paquetes, kernel, gráficos y otros componentes. Cada operación lleva una revisión de efectos, recuperación aplicable y aprobación exacta. |
| 3 | Cubre todo el directorio de inicio y el sistema, con caché revisable y exclusiones temporales. |
| 4 | Cuando el disco externo esté conectado, prepare la copia de seguridad y solicite aprobación antes de ejecutarla. La conexión no autoriza escrituras. |
| 5 | Guarde las últimas 10 copias. La limpieza se presenta y aprueba por separado. El alcance de cada set debe ser visible para que las copias de seguridad del sistema no se mezclen con ensayos o proyectos. |
| 6 | No se realizó la verificación completa de Restic o se desconoce su resultado; queda pendiente. |
| 7 | Pruebe la restauración en un destino aislado en el disco interno, sujeto a suficiente espacio y compatibilidad. No sobrescriba la instalación actual. |
| 8 | Elija objetivos concretos de servicio, red y seguridad para cada solicitud, con revisión y aprobación exactas. |
| 9 | Prepare los cambios de dependencia en una copia y ofrezca la solicitud al original después de revisar el cambio exacto. |
| 10 | Prepare descargas de dependencias y solicite la aprobación de la red antes de una compilación aislada. |
| 11 | Permitir cualquier comando necesario para el objetivo cuando sea explicado y aprobado por el usuario. No limite la función a un catálogo fijo. No mantenga requisitos de autoridad persistente o global, reintento automático o pérdida de recuperación y verificación. |
| 12 | Mantener transcripciones operativas desinfectadas durante siete días con límites de espacio y limpieza revisable; mantenga el historial de conversaciones separado. |
| 13 | Restauración completa sólo para una operación recuperable. Si existen varios, ofrezca solo restauración del chat y no reclame la recuperación del sistema. |
| 14 | Ejecute una prueba autenticada final en una sesión separada utilizando el acceso habitual sin copiar credenciales. |
| 15 | Prepare la instalación en esta estación de trabajo y presente las aprobaciones exactas requeridas después de las pruebas y la revisión independiente. |

## Los cambios de alcance aún requieren implementación

- Un límite de comando general revisado con autoridad mínima y por operación
  aprobación. Esto reemplaza el catálogo funcional fijo sin cambiar la seguridad.
  invariantes.
- Aplicación exacta al proyecto original a partir de la copia revisada, con cambio
  detección y recuperación.
- Descarga de dependencia aprobada seguida de una compilación aislada.
- Retención de expedientes académicos durante siete días.
- Actualizaciones para cualquier componente y las dos funciones de arranque concretas.
- Copia de seguridad del sistema y del directorio principal, detección de disco, propuesta de retención de diez copias,
  y ensayo de restauración aislado.
- Instalación revisada y prueba final autenticada.

La evidencia anterior de 309 pruebas pertenece al candidato antes de estas
Se implementaron extensiones. La respuesta de Restic no prueba que un cheque
pasado. Ninguna selección por sí sola autoriza una operación privilegiada.
