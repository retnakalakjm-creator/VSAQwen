# API completed weekly bar policy

The API analysis path uses the same completed-weekly-bar boundary as the CLI and live scanner.

Daily bars are first resampled into weekly bars. The current weekly bar is then excluded until the configured market weekly close boundary has passed.

This keeps API output aligned with production scanner behavior:

- no analysis uses an incomplete current week as the latest signal bar;
- API `latest_bar_index`, `latest_week`, and returned bars refer to completed weekly bars only;
- swing, evidence, qualification, and professional scoring outputs are computed from the completed weekly dataset.

The policy reduces accidental same-week lookahead and prevents API consumers from seeing different results than CLI/live scans for the same symbol.
