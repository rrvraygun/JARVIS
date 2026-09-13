# Punto de control estructural Fase 4 L1: controlador y matrícula

## Resultado

El futuro límite del protocolo del controlador VM y la estación de trabajo exacta de Fedora.
Se preparan y validan las propuestas de inscripción.

Esto no significa que se produjo la inscripción L1. La propuesta no es aprobada, cada
El grupo está deshabilitado, la identidad del host no está resuelta y no hay adaptador de observación ni
existe el servicio de controlador.

Sin escaneo de host, recopilación de especificaciones del sistema, verificación de preparación para la virtualización,
acceso a la red, instalación, adquisición de imágenes, operación del ciclo de vida de la VM,
diagnóstico de iluminación, lectura protegida, sonda de activación del dispositivo, privilegio, mutación,
o se produjo persistencia.

## Contratos entregados

- Una política de controlador sin autoridad de transporte, servicio, operación,
  persistencia, observación, virtualización, red, privilegio o dispositivo
  acceso.
- Dieciocho definiciones de operaciones versionadas con parámetros exactos, identidades,
  estados, requisitos de consentimiento, efectos y futuros nombres de adaptadores.
- Una máquina de estado de ciclo de vida cerrada con un intento, sin reintento y explícita
  estados de parada/no válido/reinicio.
- Treinta y dos definiciones de fuentes fuera de línea y no mutantes.
- Noventa definiciones de hechos normalizados en doce grupos separados por consentimiento.
- Semántica de lectura automática de nivel 0 solo después de la activación exacta de la propuesta, nivel 1
  confirmación de grupo y confirmación por sonda de Nivel 2.
- Un grupo de preparación para la virtualización L2 diferido por separado.
- Recuento exacto de salida, bytes, actualización, transformación, privacidad y retención
  límites.
- Exclusión explícita de secretos, contenidos, identificadores únicos, rutas personales,
  redes/VPN e información sobre juegos.
- Un dispositivo de solicitud/respuesta sin efecto, de un solo uso, con vencimiento y vinculado al resumen.
- Un resumen del catálogo fuente vinculado a la propuesta y un registro de revisión pendiente
  sin decisión, niveles, grupos, hechos, vinculación del anfitrión o autoridad.

## Evidencia de validación

Dieciséis pruebas de controladores cubren:

- ausencia de importaciones operativas y autoridad;
- operaciones, fuentes, grupos y enlace de host deshabilitados;
- clasificación de fuentes seguras de nivel 0;
- aislamiento de nivel 2 protegido/activación del dispositivo;
- separación exacta L2;
- transición sin efecto y rechazo de repetición;
- rechazo de operaciones no implementadas;
- rechazo de parámetros adicionales y campos ejecutables;
- discrepancia en el resumen de políticas/propuestas;
- afirmaciones falsas de aprobación y escaneo de host;
- escalada de la fuente de activación del dispositivo al Nivel 0;
- ampliación de caducidad.

La matriz VM-lab anterior y la suite adversarial siguen aplicándose de forma independiente.

## Trabajo restante de L1

La finalización operativa de L1 aún requiere:

1. revisión del usuario y activación de una revisión exacta de la propuesta;
2. adaptadores registrados revisados ​​para cada fuente seleccionada;
3. almacenamiento local cifrado y desbloqueo explícito de datos restringidos;
4. el intermediario de observación sin privilegios y la integración de auditoría inmutable;
5. ensayo de accesorios hostiles de cada adaptador; El ensayo de VM desechable es
   Opcional para la pista de host directo y requerido solo cuando un procedimiento necesita
   evidencia representativa de invitados;
6. una nueva decisión explícita de ejecutar la observación de inscripción limitada;
7. revisión del perfil del candidato antes de la activación.

## Progreso de implementación segura (2026-08-06)

El paquete contiene ahora una fachada mecanografiada en
`vm-lab/scripts/observation_broker.py` para la plataforma/cómputo mínimo
Alcance de nivel 0. Vincula el registro, la política, el catálogo de fuentes y la propuesta.
digiere; aplica ID de solicitud de caducidad y de un solo uso; emite candidato sintético
sólo hechos; y rechaza el modo de anfitrión en vivo hasta que se completen las puertas restantes.`vm-lab/scripts/restricted_fact_store.py` proporciona el límite de almacenamiento: hechos
permanecen efímeros a menos que un backend certifique de forma independiente el cifrado en reposo,
escrituras atómicas y verificación de recuperación. No proporciona intencionalmente
respaldo de texto plano o criptografía local. La revisión v2 incluye
`LuksStorageAttestor` y `LuksSqliteFactBackend`: el primero vuelve a comprobar el
ruta canónica contra la identidad actual de montaje/mapeador de dispositivos, y esta última
utiliza aperturas `O_NOFOLLOW` controladas por el propietario, escrituras SQLite transaccionales, un
Libro de activación duradero de un solo uso, metadatos vinculantes e integridad de registros.
verificación. La membresía del adaptador/versión/fuente/hecho aprobado está sujeta a
`vm-lab/enrollment/tier0-approved-fact-scope.json` y aplicado nuevamente en el
límite de almacenamiento. Permanece inactivo hasta que se realiza un desbloqueo/recuperación concreto del usuario.
la atestación está vinculada a una ruta en vivo.

Estos son requisitos previos de implementación, no activación de inscripción. Sin anfitrión
autoridad de observación, persistencia restringida o servicio de controlador ha sido
habilitado. La implementación v2 y las pruebas de fijación se registran en
`runtime/reports/2026-08-07-restricted-storage-backend-v2.json`.

Se registran las pruebas recientes de desbloqueo de usuario/ruta y la prueba de límites de recuperación de R2.
en `runtime/reports/2026-08-07-live-luks-storage-attestation.json` y
`runtime/reports/2026-08-07-r2-live-recovery-boundary.json`. Estos artefactos son
evidencia preparada únicamente; no crean un registro de activación en vivo.

La próxima revisión de construcción agrega `vm-lab/scripts/activation_authority.py`,
un libro de decisiones de usuario duradero y de alcance exacto, y
`vm-lab/scripts/live_tier0_observation.py`, un coleccionista acotado y sin privilegios
para las cuatro plataformas/fuentes de computación aprobadas. Ambos están cerrados detrás
la política de discapacitados existente; el cobrador no puede consumir una autorización o
lea el estado del host mientras `host_observation_enabled` es falso. Un nuevo independiente
Se requiere revisión antes de cualquier promoción de póliza o registro.

Se registran la evaluación de la puerta actual y el alcance inicial exacto recomendado.
en `runtime/reports/2026-08-06-phase4-activation-readiness.json`.

Esa tarea estructural ahora está completa para cuatro analizadores de dispositivos Tier-0 y el
contrato de corredor sin efecto. El diseño completo de preparación de Workstation VM y L2 es
documentado en `phase-4-l2-full-vm-blueprint.md`. No existe ningún coleccionista vivo; el
El límite sin escaneo permanece sin cambios.
