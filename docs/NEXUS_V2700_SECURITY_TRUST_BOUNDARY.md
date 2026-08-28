# Nexus V2700 Security Trust Boundary

## Purpose

This document defines the security trust boundary for the Nexus Runtime
Platform V2700 node-to-node control and distributed Compute transport.

It documents the security properties already enforced by the runtime and
does not claim transport-layer TLS confidentiality.

## Trust model

Nexus V2700 uses a shared-secret trust model for authenticated protocol
messages.

A node is trusted to participate in the authenticated Nexus protocol only
when it possesses the configured `NEXUS_SECRET_KEY`.

Possession of network connectivity alone does not establish protocol trust.

The shared secret is therefore part of the trusted deployment boundary and
must be provisioned only to authorized Nexus nodes.

## Untrusted boundary

The following inputs are treated as untrusted until validated:

- messages received from the network;
- claimed sender identities;
- message payloads;
- timestamps and nonces carried by protocol envelopes;
- Compute requests and Compute results received from remote nodes;
- rendezvous requests received from remote participants.

A remote peer must not be trusted solely because its IP address or TCP
connection is reachable.

## Message authentication and integrity

Authenticated Nexus messages are created and verified through
`NexusProtocol`.

The protocol provides message authentication and integrity using the
configured shared secret.

A message whose authenticated envelope has been modified must be rejected.

The authenticated envelope binds protocol metadata and payload to the
message signature.

## Replay resistance

Authenticated messages include freshness/replay information.

`ReplayCache` records accepted protocol messages and rejects reuse of an
already accepted authenticated message.

Protocol verification also applies the configured message TTL so that stale
messages are rejected outside the accepted freshness window.

Replay resistance therefore depends on both freshness validation and the
lifetime of the replay cache maintained by the receiving process.

## Distributed Compute boundary

Distributed Compute crosses the network trust boundary.

`TransportNodeExecutor` creates an authenticated `COMPUTE_TASK` envelope
before sending a remote task.

The receiving Compute handler validates the authenticated request before
executing it and returns an authenticated `COMPUTE_RESULT`.

The requesting node validates the returned envelope before accepting the
result.

After cryptographic/protocol validation, the Compute client additionally
validates:

- response message type;
- expected sender identity;
- task identifier;
- terminal execution status.

A network peer therefore cannot establish an authoritative Compute result
merely by returning syntactically valid JSON.

## Rendezvous boundary

Rendezvous messages also cross the network trust boundary and are subject to
the authenticated Nexus protocol and replay/freshness validation where the
secure protocol path is used.

Rendezvous discovery does not by itself grant authority to forge
authenticated Compute messages.

## Transport framing

`nexus_transport.py` provides framed message transport and explicit message
size validation.

Framing is not an authentication mechanism.

Authentication and integrity are provided by the authenticated protocol
envelope, while framing defines safe message boundaries and transport size
limits.

## Confidentiality

V2700 does not claim that the raw node-to-node Compute socket is protected
by TLS.

The demonstrated V2700 security contract is message authentication,
integrity, freshness/replay resistance, explicit protocol validation and
endpoint validation.

Deployments requiring confidentiality against passive network observation
must provide an appropriate protected network or transport confidentiality
layer.

## Persistence integrity boundary

Persistence integrity and distributed transport authentication are distinct
security boundaries.

The external-anchor persistence model protects integrity/rollback properties
of durable state.

It is not a substitute for node-to-node message authentication.

Likewise, authenticated transport does not eliminate the separately
documented coordinated log/checkpoint rollback limitation when the required
external integrity authority is unavailable or restorable with the attacked
state.

## Operational responsibilities

Operators are responsible for:

- provisioning a non-empty `NEXUS_SECRET_KEY`;
- restricting the secret to authorized nodes;
- rotating/reprovisioning secrets when trust is lost;
- configuring a positive message TTL;
- protecting external integrity anchors according to their threat model;
- providing network confidentiality when required by deployment policy.

## V2700 security boundary summary

Inside the authenticated Nexus trust boundary:

- authorized nodes share the configured protocol secret;
- authenticated messages may be accepted only after protocol validation.

Outside the trust boundary:

- network traffic and claimed identities are untrusted;
- malformed, tampered, stale or replayed authenticated messages are rejected;
- remote Compute results require both authenticated-envelope validation and
  explicit response identity/task validation.

This boundary intentionally describes the V2700 implementation as
demonstrated by the repository and does not claim PKI, mutual TLS, per-node
cryptographic identities or encrypted raw TCP transport.