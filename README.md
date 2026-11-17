# Iris

Short, Google-Meet-style meeting links backed by [VDO.Ninja](https://vdo.ninja).

Iris is an [Anvil](https://anvil.works) app. It is built to serve Empiria's
meeting links at meet.empiria.co.uk and to be deployable by anyone who wants
to run their own instance.

## Layout

- `anvil.yaml`: app config (dependencies, services, startup module)
- `client_code/`: forms and client modules, imported as `app.*`
- `server_code/`: server modules and `requirements.txt`
- `theme/`: theme assets and parameters

## Dependencies

The app depends on these Anvil apps. After you clone or import it into a new
Anvil account, add them again through the editor's "Add Dependency" dialog:

- Material 3 Theme (`m3`) v1.2.3
- routing v0.3.5
- Anvil Extras v3.1.0

## Working on the code

See [AGENTS.md](AGENTS.md) for conventions and checks.
