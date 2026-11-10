# docs/

How this project works, for maintainers and for agents working in the repo. These pages explain internals and the reasoning behind them. For installing and using the client, see the README.

- **[how-it-works.md](./how-it-works.md)** — what a `Device` does on the wire, the connection lifecycle, who drives the network loop, and where connection errors surface.
- **[state-and-time.md](./state-and-time.md)** — how `send_state` builds its payload and how each kind of `time_like` is interpreted.
- **[testing.md](./testing.md)** — how `Device` is tested without a network, and how to add a test.
- **[packaging-and-ci.md](./packaging-and-ci.md)** — what ends up in the wheel, what each CI job checks, and how a release is cut.
- **[development.md](./development.md)** — set up the environment and run the everyday commands.
