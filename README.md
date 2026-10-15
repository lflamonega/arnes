# arnes

Arnes pedagogico minimalista para aprendizaje autodidacta.

## Instalacion

macOS/Linux/WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/TU_USUARIO/arnes/main/install.sh | bash
```

Windows:

```powershell
irm https://raw.githubusercontent.com/TU_USUARIO/arnes/main/install.ps1 | iex
```

## Uso

- `arnes` abre el REPL.
- `arnes --version`
- `arnes --help`

## Desinstalacion

```bash
pipx uninstall arnes
```

Borra tambien `~/.arnes/`.

## Estructura del directorio

```
~/.arnes/
├── config.json
├── credentials.json
├── prompts/
├── sessions/
├── logs/
└── history
```

## Comandos

| Comando | Descripcion |
|---|---|
| /help | Ayuda |
| /settings | Configuracion |
| /connect | Credenciales |
| /new | Nueva sesion |
| /status | Estado |
| /quit | Salir |

## Version

0.0.1
