# Nexus V2700 — Axis 7 Physical Multi-Machine Certification

## Purpose

This validation area is reserved exclusively for physical
multi-machine certification of Nexus Runtime Platform V2700.

Local multi-process experiments are not sufficient evidence.

## Required topology

Final certification requires three distinct physical hosts
participating in the distributed experiment.

## Required final evidence

The certification must demonstrate:

1. three distinct hosts;
2. exactly one MASTER during stable observation;
3. failover after loss of the active MASTER;
4. continued state progress after failover;
5. rejoin of the old node;
6. equal persistence height after convergence;
7. equal persistence tip_hash after convergence;
8. a stability observation window after convergence.

## Evidence policy

Each physical run must receive its own timestamped directory
under:

    validation/axis7-physical/evidence/

The evidence directory must preserve raw observations before
a certification verdict is produced.

No physical certification claim may be made solely from local
process execution.
