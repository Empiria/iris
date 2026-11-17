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

- routing v0.7.0
- anvil-reactive v0.1.4 (repo `github.com/anvilistas/reactive`)

## Local development

`just setup`, `just deps`, `just verify` and `just unit` work anywhere you have
`just`, `uv`, `ruff`, `anvil-cli` and `git`. The stack recipes (`just up`,
`just seed`, `just e2e`) need podman.

## Working on the code

See [AGENTS.md](AGENTS.md) for conventions and checks.
