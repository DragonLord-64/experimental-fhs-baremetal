### PDU Power Monitoring

**pdu_power_monitory.py**

Monitor the power, voltage, current, and power factor of 2 outlets of a single PDU. Records Max power

#### Requirements:
- Servertech Pro2x PDU configured for HTTP access.

#### Usage:
Run with
```bash
./pdu_power_monitor.py
```
output will be logged in the same directory as the file

### CPU and Memory Performance Test

**run_cpu_perf_test.sh**

This script executes a linux performance benchmark test on the target machine. It tests both CPU and memory.



#### Requirements:
the following application to be installed and available on the test machine:
https://www.passmark.com/products/pt_linux/download.php?srsltid=AfmBOooi93VlY6P_uNpNMO80yPnA-jbavKl9Y45eTZA6SewieJE52g3z 
v11.0 Build 1004

#### Usage:
To be run on the Equipment Under Test.
Installing the passmark Performance Test
- Unzip the PerformanceTest_Linux_x86-64.zip on the target machine.
- Copy the PerformanceTest_Linux_x86-64 to the same directory of the 
- run the script

```bash
./run_cpu_perf_test.sh
```

### Bittware Power Burner Tests

**system_test.sh**

Executes a power burner test on both FPGA cards within the Terabox1501b.

#### Requirements:

- 860_burner_profile.csv # defines power burner test
- ia860m_system_test_***_sdk2025.yaml # for both FPGA card targets
- ia860m_cardtest01_bbrev4_pwr_v1.0.rbf # power burner bitstream.

The bitstream (.rbf file) must be loaded and programmed on to the target FPGA cards.
See bitware SDK documentation for instructions on loaded and programming a bitstream.

#### Usage:

Run the following script in the same directory as the other requirement files (see above).

```bash
./system_test.sh
```


