# Protocol and format verification

Checked 2026-10-12. Primary source repository: `spice2x/spice2x.github.io`; source snapshot `fdc7adff7f0560923633c5438a4be7d2f55a0f38`. Links below identify the upstream implementation rather than similarly named SPICE remote-desktop or Spice.ai products.

| Claim used in this project | Primary evidence |
|---|---|
| API TCP enablement, NUL-delimited UTF-8 JSON, optional password/RC4 | [Spice README, API section](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/README.md#api) |
| Request keys `id`, `module`, `function`, `params` | [Python request implementation](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/api/resources/python/spiceapi/request.py) |
| Response keys `id`, `errors`, `data` | [Python response implementation](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/api/resources/python/spiceapi/response.py) |
| One continuous RC4 stream across alternating send/receive on a connection; password UTF-8 | [Python connection implementation](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/api/resources/python/spiceapi/connection.py) |
| `buttons.read`, `write`, `write_reset` and nested-array arguments | [Button module implementation](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/api/modules/buttons.cpp) |
| `analogs.read`, `write`, `write_reset`; normalized values | [Analog module implementation](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/api/modules/analogs.cpp) |
| Default SDVX button and knob names | [SDVX I/O definitions](https://github.com/spice2x/spice2x.github.io/blob/fdc7adff7f0560923633c5438a4be7d2f55a0f38/src/spice2x/games/sdvx/io.cpp) |
| KSH syntax and timing conventions | [K-Shoot MANIA chart format repository](https://github.com/kshootmania/ksm-chart-format), [maintainer documentation](https://kson.dev/docs/format-spec/ksh_format/) |

Example plaintext requests, each followed by the actual byte `0x00` (not the literal characters `\\0`):

```json
{"id":1,"module":"buttons","function":"read","params":[]}
{"id":2,"module":"buttons","function":"write","params":[["BT-A",1.0],["FX-L",0.0]]}
{"id":3,"module":"analogs","function":"write","params":[["VOL-L",0.5]]}
{"id":4,"module":"buttons","function":"write_reset","params":[["BT-A"],["FX-L"]]}
```

`read` returns rows in `data`; writes generally return empty `data`. An override of zero is still an override; `write_reset` removes it. Empty reset parameters reset all controls, so this project instead sends explicitly owned/configured names.

The client uses the initial password stream and does not call `control.session_refresh`. Session refresh/password rotation, serial and WebSocket transports are not implemented. RC4 is retained only for protocol interoperability, not presented as modern transport security.

Unverified: compatibility with a particular kspice fork/build; real-game timing/polling; effective analog laser response; capture under your graphics mode; real skin segmentation; panic hooks on your desktop; VOX semantic/version decoding. The automated mock validates the implemented wire contract and error behavior, not a running Spice server.
