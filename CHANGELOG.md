# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

## [0.0.1] - 2026-10-16

### Added

- Estructura inicial del paquete `arnes`.
- Modulo `paths` con resolucion del directorio `~/.arnes/` y override por `ARNES_HOME`.
- Modulo `config` con carga, guardado y validacion de `config.json`.
- Modulo `credentials` con carga y guardado de `credentials.json` con permisos `0600` en Unix.
- Modulo `prompts` con parser de frontmatter YAML minimalista y prompts por defecto.
- Modulo `store` con persistencia de sesiones y estado en JSON.
- Modulo `orchestrator` con maquina de estados pedagogica determinista.
- Modulo `validator` con validacion de restricciones y fallback determinista.
- Modulo `provider` con interfaz abstracta `InferenceProvider` y adaptador `OpenRouterProvider`.
- Modulo `evaluator` con panel de evaluadores, agregacion por mediana y umbral compuesto.
- Modulo `planner` con generacion de plan a partir de logro y fuentes, con citas obligatorias.
- Modulo `commands` con `/help`, `/settings`, `/connect`, `/new`, `/status`, `/quit`.
- Modulo `repl` con bucle interactivo usando `prompt_toolkit` y `rich`.
- Modulo `cli` con entry point `arnes`.
- Script `install.sh` para macOS, Linux y WSL.
- Script `install.ps1` para Windows.
- README con instrucciones de instalacion, uso y desinstalacion.

[Unreleased]: https://github.com/lflamonega/arnes/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/lflamonega/arnes/releases/tag/v0.0.1
