# Browser-wallet E2E contracts

Choose explicitly between an injected EIP-1193 mock and a real extension/local
chain. A mock validates application handling, not extension UI or provider
compatibility.

Install an injected provider with `page.addInitScript` before application code.
Implement only the methods/events the case needs, but fail on unexpected RPC
methods instead of returning `null`; silent fallbacks hide missing coverage.

Cover account and chain changes, rejection, disconnected state, malformed RPC
responses, and transaction failure as well as connection success. Assert the
exact request parameters and resulting application state. Use deterministic
addresses and transaction hashes that are unmistakably fixtures.

Real-extension tests must track popup/page handles explicitly and run only with
disposable seed material on an isolated local chain. Never use a funded wallet,
production RPC, or a seed shared outside the test job. Reset wallet permissions,
selected account, chain, and local-chain snapshot between cases.
