# Progression Shadow Replay Dataset UI Adapter

## Purpose

K27 connects the validated K26 replay dataset to the existing K25 dev-only
replay surface.

The adapter remains fully offline.

## Import model

The user explicitly selects:

    progression_shadow_replay_dataset.json

from the local filesystem.

The browser reads the file with File.text() and parses it in memory.

K27 does not:

- upload the file;
- call the ProVSA API;
- call any remote endpoint;
- use fetch or XMLHttpRequest;
- store the dataset in localStorage or sessionStorage;
- persist replay state.

Synthetic K25 fixtures remain available as a fallback.

## Validation

Before any imported sequence is shown, the adapter validates:

- exact K26 audit id;
- dataset_status = shadow_replay_dataset_ready;
- all top-level safety flags are false;
- source_event_count = sequence_count;
- replay_sequences length = sequence_count;
- total_frame_count matches flattened frames;
- unique sequence ids;
- each sequence has exactly one event frame;
- event week matches the event frame;
- resolved event index matches the event frame;
- sequence semantic role/direction match the event frame;
- non-event frames contain no semantic marker data;
- every frame keeps all production safety flags false.

Invalid files fail closed and are not rendered.

## Route boundary

The existing route remains:

    /replay/progression-semantic

It remains disabled in production by default.

K27 changes the route description from synthetic-only to offline-local-artifact
review. Synthetic fixtures remain a built-in fallback for smoke testing.

## Safety

No production API, scanner, qualification, scoring, actionability, persistence,
alerts, or orders are connected to this adapter.
