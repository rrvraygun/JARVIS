# Decisiones del usuario — cuestionario de cierre

Las 15 preguntas fueron respondidas mediante el selector de esta conversación. Estas decisiones concretan el producto; no son aprobaciones de comandos, instalaciones, borrados o cambios del sistema.

| Nº | Decisión aceptada |
| --- | --- |
| 1 | Elegir un kernel instalado para el próximo arranque y reparar initramfs de un kernel concreto. |
| 2 | Preparar cualquier actualización necesaria: paquetes, kernel, gráficos y demás componentes. Cada operación conserva revisión de efectos, recuperación aplicable y aprobación exacta. |
| 3 | Cubrir todo el directorio personal además del sistema, con exclusiones revisables de cachés y temporales. |
| 4 | Al conectar el disco externo, preparar el backup y solicitar aprobación antes de ejecutarlo. La conexión no autoriza escrituras. |
| 5 | Conservar las últimas 10 copias. La limpieza se presenta y aprueba por separado. El alcance de cada conjunto de copias debe ser visible para no mezclar backups de sistema con ensayos o proyectos. |
| 6 | La comprobación completa de Restic no se ha ejecutado o su resultado se desconoce; permanece pendiente. |
| 7 | Probar restauración en un destino aislado del disco interno, condicionado a espacio suficiente y compatibilidad. No sobrescribir la instalación actual. |
| 8 | Elegir objetivos concretos para servicios, red y seguridad en cada solicitud, con revisión y aprobación exactas. |
| 9 | Preparar cambios de dependencias en una copia y ofrecer su aplicación al original tras revisar el cambio exacto. |
| 10 | Preparar descargas de dependencias y solicitar aprobación de red antes de compilar aislado. |
| 11 | Poder preparar cualquier comando necesario para el objetivo, explicado y aprobado por el usuario. No se limita a un catálogo fijo. Sin autoridad persistente, aprobación global, reintento automático ni pérdida de los requisitos de recuperación y verificación. |
| 12 | Conservar transcriptos operativos saneados durante 7 días, con límite de espacio y limpieza revisable; historial de conversación separado. |
| 13 | Restauración completa solo para una operación recuperable. Cuando existan varias, ofrecer únicamente restauración de chat, sin afirmar recuperación del sistema. |
| 14 | Prueba final autenticada en una sesión separada, usando el acceso habitual sin copiar credenciales. |
| 15 | Preparar instalación en este equipo y presentar las aprobaciones exactas necesarias tras pruebas y revisión independiente. |

## Cambios de alcance que aún requieren implementación

- Frontera de comandos generales revisados, con autoridad mínima y aprobación de cada operación; reemplaza la restricción funcional a un catálogo fijo, no las invariantes de seguridad.
- Aplicación exacta al proyecto original desde la copia revisada, con detección de cambios desde la revisión y recuperación.
- Descarga aprobada de dependencias y posterior compilación aislada.
- Retención de transcriptos de siete días.
- Actualizaciones de cualquier componente y las dos funciones concretas de arranque.
- Backup de sistema y directorio personal, detección del disco, propuesta de conservación de diez copias y restauración de ensayo aislada.
- Instalación revisada y prueba autenticada final.

La evidencia anterior de 309 pruebas corresponde al candidato previo a implementar estas ampliaciones. La respuesta de Restic no acredita una comprobación pasada. Ninguna selección autoriza por sí misma una operación privilegiada.
