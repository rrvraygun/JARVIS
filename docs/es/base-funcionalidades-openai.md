# Base de características de OpenAI

La plataforma utiliza de forma selectiva las superficies del Codex documentadas actualmente:

- Revisión de ganchos y confianza: https://learn.chatgpt.com/docs/hooks
- Modos de configuración y aprobación de MCP: https://learn.chatgpt.com/docs/extend/mcp
- Complementos: https://learn.chatgpt.com/docs/build-plugins
- Habilidades: https://learn.chatgpt.com/docs/build-skills
- Agentes personalizados y orquestación: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Guía de repositorio persistente: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Automatización no interactiva: https://learn.chatgpt.com/docs/non-interactive-mode
- Integración de cliente enriquecido: https://learn.chatgpt.com/docs/app-server
- Integración de Python y TypeScript: https://learn.chatgpt.com/docs/codex-sdk
- Acceso al plan ChatGPT:
  https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt
- Configuración y requisitos gestionados: https://learn.chatgpt.com/docs/config-file/config-reference

Implicaciones de diseño:

- Los ganchos son útiles pero están incompletos y no pueden deshacer los efectos secundarios completos.
- Los enlaces de complementos requieren una revisión de confianza explícita a menos que se administren de forma centralizada.
- Un servidor MCP requerido hace que la automatización falle si las herramientas de gobierno no se inician.
- Las listas de permitidos de MCP y los modos de aprobación por herramienta reducen la autoridad expuesta.
- `codex exec` tiene como valor predeterminado solo lectura y admite JSONL y esquemas de salida.
- App Server expone hilos, turnos, elementos transmitidos, solicitudes de entrada de usuarios,
  aprobaciones, interrupciones y esquemas de protocolos generados por versiones para ricos
  clientes.
- El SDK de Python controla el servidor de aplicaciones local a través de JSON-RPC, pero es crítico para la seguridad.
  El cliente debe verificar que el SDK exponga todas las características de aprobación/evento requeridas.
  o utilice el esquema de protocolo generado directamente.
- La TUI planificada utiliza App Server con autenticación administrada por ChatGPT. lo hace
  no requiere ni recurre silenciosamente a una clave API facturada por separado.
- Los subagentes mejoran la evidencia y la revisión independientes, pero el primario conserva
  autorización y responsabilidad de integración.
- Las habilidades proporcionan una divulgación progresiva; Los procedimientos detallados no deben abultar
  el indicador del agente siempre cargado.
