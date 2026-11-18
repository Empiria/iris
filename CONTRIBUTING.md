<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2026 Empiria -->

# Contributing

Thanks for helping with Iris.

## Run the checks

Install [`just`](https://github.com/casey/just), [`uv`](https://docs.astral.sh/uv/),
`git` and `anvil-cli`, then:

```sh
just setup    # once per clone: git hooks, tools, Playwright chromium
just verify   # lint, format check, type-check, anvil validate, leftovers, SPDX, unit tests
```

`just verify` is the gate before you send a change, and CI runs it. Outside
contributions arrive as pull requests, and the maintainer merges them to `main`. The browser
tests (`just e2e`) need the local podman stack; see the README's
[Local development](README.md#local-development).

## Code rules

The conventions are in [AGENTS.md](AGENTS.md): the server and the Skulpt client
run different Python, forms hold UI only, data goes through model classes, and
callables check permissions on the server. Please read it before changing code.

## Licence headers

Iris is MIT-licensed. Every new file needs an
`SPDX-License-Identifier: MIT` and `Copyright (c) 2026 Empiria` header (`#` in
Python and the justfile, `/* */` in CSS, `<!-- -->` in Markdown). Files that
can't hold a comment, or that the Anvil editor rewrites, are covered by
[`REUSE.toml`](REUSE.toml) instead. Run `just spdx` to check.

## Reporting security problems

Please don't use a public issue. See [SECURITY.md](SECURITY.md).
