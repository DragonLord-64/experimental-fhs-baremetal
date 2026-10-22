# VCC and FSP units

Unit topology confirmed by the user, 2026-10-21.

| Unit | FHS servers | Network switches |
|---|---:|---:|
| VCC unit | 1 | 1 |
| FSP unit | 4 | 1 |

Each VCC unit connects to every FSP unit. The mesh dashboard represents those unit-to-unit connections; it must retain the switch interfaces at both ends of each link.

Keep `unit_type`, `unit_id`, FHS identity, switch identity and interface identity separate. Unit health aggregates its member devices; a unit is not a single generic server. Rack views drill into the appropriate FHS or switch.

## Design references

- [SKA Mid.CBF MCS design notes](https://developer.skao.int/projects/ska-mid-cbf-mcs/en/latest/guide/developer/design_notes.html): FHS/LRU composition, VCC units, FSP units and their monitoring/control hierarchy. The published model has two signal-processing FPGAs per FHS, six VCC resources per VCC unit, and eight FPGAs across the four FHSs in an FSP unit.
- [MCS-to-FHS interface](https://developer.skao.int/projects/ska-mid-cbf-mcs/en/latest/guide/interfaces/mcs_fhs_interface.html): control interactions between MCS, FHS controllers and network switches.

Use the user's inventory for deployed identities and placement. The design references explain the architecture; they do not prove the current lab hardware or deployment state.
