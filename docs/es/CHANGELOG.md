# Registro de cambios

Aquí se registran los cambios relevantes de JARVIS. Las fechas usan la hora local
de Europe/Madrid cuando el registro original aporta una hora local.

## [Sin publicar] — 2026-09-13

### Añadido

- Documentación principal en inglés y un espejo español bajo `docs/es/`, con
  `README.es.md` como entrada del repositorio.
- Vistas Clean y Raw para Health, Development, Network, Security y Recovery.
- Explicaciones `[i]` por campo, selectores globales de modelo, razonamiento y
  ventana de contexto, y marcador de tokens usado/disponible.
- Actividad en tiempo real dentro de Conversation y recuperación de contexto a
  cero tras restaurar un checkpoint o iniciar una conversación nueva.
- Ejecución en terminal normal, helpers revisados para arranque/actualizaciones,
  pruebas autenticadas y smoke test visible.

### Cambiado

- La conversación mantiene fija la geometría del contenedor al abrir selectores
  y menús de checkpoint.
- El inventario y el manifiesto resuelven las exclusiones desde la raíz de la
  entrega y rechazan manifiestos vacíos.

### Límites conocidos

- Las mutaciones privilegiadas reales y un turno autenticado completo siguen
  requiriendo pruebas separadas de despliegue.
- El uso de contexto queda sin datos hasta que App Server envía un evento de uso;
  la interfaz no lo estima a partir de caracteres.

## Registros históricos

Los registros de fases, auditorías y sesiones están bajo `docs/` y `docs/es/`.
Describen decisiones y evidencias en sus fechas originales. Para el comportamiento
actual consulta `current-product-state.md`.
