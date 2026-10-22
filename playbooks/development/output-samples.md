```bash
$ source /opt/venvs/fhs/bin/activate
$ bw_card_list -i USB -v
IA-860M 819xxxx
  Interface(s)
   USB
     Index               : 0
     Vendor ID           : 9512
     Device ID           : 7
     Location            : 3-2.2.1
  Manufacturing Info
    Manufacture Date    : 2024-12-12 2:20:10
    Part Number         : IA-860m-S-F391E2C-0-S0-X-30-2U-0-E-9
    Version             : 3.2.0.0.0
    Asset Tag           : 861093192
  Firmware Version Info
    CPLD Version        : Not implemented
    BMC Version Full    : 1.1.2-3
    BMC Version         : 1.1.2-3
  Card Status
    Power               : On
    Last Error          : <BMC3: Use the get bw_bmc_get_logs utility>
    Reset Cause         : Power on reset
    FPGA State          : Configured Normal
IA-860M 819xxxx
  Interface(s)
   USB
     Index               : 1
     Vendor ID           : 9512
     Device ID           : 7
     Location            : 3-2.1.1
  Manufacturing Info
    Manufacture Date    : 2024-12-11 19:18:52
    Part Number         : IA-860m-S-F391E2C-0-S0-X-30-2U-0-E-9
    Version             : 3.2.0.0.0
    Asset Tag           : 861093192
  Firmware Version Info
    CPLD Version        : Not implemented
    BMC Version Full    : 1.1.2-3
    BMC Version         : 1.1.2-3
  Card Status
    Power               : On
    Last Error          : <BMC3: Use the get bw_bmc_get_logs utility>
    Reset Cause         : Power on reset
    FPGA State          : Configured Normal 

$ bw_qsfp_info -c 0 -i USB display

QSFP Information

  QSFP0:
     qsfp_type : QSFP-DD
     connecter : Reserved
     cable_length : 1
     vendor_name : FS
     vendor_oui : [100, 157, 153]
     vendor_partnumber : QDD-400G-PC01
     vendor_rev : 00
     vendor_serial_number : C2504136693-1
     vendor_date : 250407
     supply_voltage : 0.0
     temperature : 0.0
     sep : 83
     technology : 0
     techstr : 850nm VCSEL
     power_class : 1
     max_power : 0.25 Watts
     length : 130
     Present : Present
     Interrupt : Unasserted
     Low Power : Unasserted
     Reset : Unasserted

  QSFP1:
     qsfp_type : QSFP-DD
     connecter : Reserved
     cable_length : 1
     vendor_name : FS
     vendor_oui : [100, 157, 153]
     vendor_partnumber : QDD-400G-PC01
     vendor_rev : 00
     vendor_serial_number : C2504136693-2
     vendor_date : 250407
     supply_voltage : 0.0
     temperature : 0.0
     sep : 83
     technology : 0
     techstr : 850nm VCSEL
     power_class : 1
     max_power : 0.25 Watts
     length : 130
     Present : Present
     Interrupt : Unasserted
     Low Power : Unasserted
     Reset : Unasserted

  QSFP2:
     Present : Removed
     Interrupt : Unasserted
     Low Power : Unasserted
     Reset : Asserted
```


```bash
$ ethtool -i enp1s0np0 
driver: mlx5_core
version: 6.8.0-139-generic
firmware-version: 20.31.1014 (MT_0000000223)
expansion-rom-version: 
bus-info: 0000:01:00.0
supports-statistics: yes
supports-test: yes
supports-eeprom-access: no
supports-register-dump: no
supports-priv-flags: yes
ma097380_p@sys1389:~$ ethtool -i enp1s0np0 -v
ethtool: bad command line argument(s)
For more information run ethtool -h
$ sudo ethtool -m enp1s0np0
        Identifier                                : 0x11 (QSFP28)
        Extended identifier                       : 0x00
        Extended identifier description           : 1.5W max. Power consumption
        Extended identifier description           : No CDR in TX, No CDR in RX
        Extended identifier description           : High Power Class (> 3.5 W) not enabled
        Power set                                 : Off
        Power override                            : Off
        Connector                                 : 0x23 (No separable connector)
        Transceiver codes                         : 0x80 0x00 0x00 0x00 0x00 0x00 0x00 0x00
        Transceiver type                          : 50GBASE-CR, 100GBASE-CR2, or 200GBASE-CR4
        Encoding                                  : 0x08 (PAM4)
        BR, Nominal                               : 25500Mbps
        Rate identifier                           : 0x00
        Length (SMF,km)                           : 0km
        Length (OM3 50um)                         : 0m
        Length (OM2 50um)                         : 0m
        Length (OM1 62.5um)                       : 29m
        Length (Copper or Active cable)           : 1m
        Transmitter technology                    : 0xa0 (Copper cable unequalized)
        Attenuation at 2.5GHz                     : 4db
        Attenuation at 5.0GHz                     : 7db
        Attenuation at 7.0GHz                     : 8db
        Attenuation at 12.9GHz                    : 13db
        Vendor name                               : FS
        Vendor OUI                                : 64:9d:99
        Vendor PN                                 : QDD-400G-2QPC01
        Vendor rev                                : A0
        Vendor SN                                 : C2507508472-1
        Date code                                 : 250722
        Revision Compliance                       : Unallocated
        Module temperature                        : 0.00 degrees C / 32.00 degrees F
        Module voltage                            : 0.0000 V

$ sudo ethtool  enp1s0np0
Settings for enp1s0np0:
        Supported ports: [ Backplane ]
        Supported link modes:   1000baseT/Full
                                10000baseT/Full
                                1000baseKX/Full
                                10000baseKR/Full
                                10000baseR_FEC
                                40000baseKR4/Full
                                40000baseCR4/Full
                                40000baseSR4/Full
                                40000baseLR4/Full
                                25000baseCR/Full
                                25000baseKR/Full
                                25000baseSR/Full
                                50000baseCR2/Full
                                50000baseKR2/Full
                                100000baseKR4/Full
                                100000baseSR4/Full
                                100000baseCR4/Full
                                100000baseLR4_ER4/Full
                                50000baseSR2/Full
                                1000baseX/Full
                                10000baseCR/Full
                                10000baseSR/Full
                                10000baseLR/Full
                                10000baseER/Full
                                50000baseKR/Full
                                50000baseSR/Full
                                50000baseCR/Full
                                50000baseLR_ER_FR/Full
                                50000baseDR/Full
                                100000baseKR2/Full
                                100000baseSR2/Full
                                100000baseCR2/Full
                                100000baseLR2_ER2_FR2/Full
                                100000baseDR2/Full
                                200000baseKR4/Full
                                200000baseSR4/Full
                                200000baseLR4_ER4_FR4/Full
                                200000baseDR4/Full
                                200000baseCR4/Full
        Supported pause frame use: Symmetric
        Supports auto-negotiation: Yes
        Supported FEC modes: None        RS      BASER
        Advertised link modes:  1000baseT/Full
                                10000baseT/Full
                                1000baseKX/Full
                                10000baseKR/Full
                                10000baseR_FEC
                                40000baseKR4/Full
                                40000baseCR4/Full
                                40000baseSR4/Full
                                40000baseLR4/Full
                                25000baseCR/Full
                                25000baseKR/Full
                                25000baseSR/Full
                                50000baseCR2/Full
                                50000baseKR2/Full
                                100000baseKR4/Full
                                100000baseSR4/Full
                                100000baseCR4/Full
                                100000baseLR4_ER4/Full
                                50000baseSR2/Full
                                1000baseX/Full
                                10000baseCR/Full
                                10000baseSR/Full
                                10000baseLR/Full
                                10000baseER/Full
                                50000baseKR/Full
                                50000baseSR/Full
                                50000baseCR/Full
                                50000baseLR_ER_FR/Full
                                50000baseDR/Full
                                100000baseKR2/Full
                                100000baseSR2/Full
                                100000baseCR2/Full
                                100000baseLR2_ER2_FR2/Full
                                100000baseDR2/Full
                                200000baseKR4/Full
                                200000baseSR4/Full
                                200000baseLR4_ER4_FR4/Full
                                200000baseDR4/Full
                                200000baseCR4/Full
        Advertised pause frame use: Symmetric
        Advertised auto-negotiation: Yes
        Advertised FEC modes: RS
        Speed: 200000Mb/s
        Duplex: Full
        Auto-negotiation: on
        Port: Direct Attach Copper
        PHYAD: 0
        Transceiver: internal
        Supports Wake-on: d
        Wake-on: d
        Link detected: yes
$