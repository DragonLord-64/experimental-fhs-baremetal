#!/bin/bash

echo "Starting 4 parallel cardtest processes..."

# Process 1
# Replace serialnumber below with the serial number of the first ia-860m card
(
    echo "Process 1 (PID: $$) started"
    bw_card_test -p ia860m_system_test_8190728_sdk2025.yaml
    sleep 2
    echo "Process 1 completed"
) &

# Process 2
# Replace serialnumber below with the serial number of the second ia-860m card
(
    echo "Process 2 (PID: $$) started"
    bw_card_test -p ia860m_system_test_8190729_sdk2025.yaml
    sleep 1
    echo "Process 2 completed"
) &

# Process 3
# Replace serialnumber below with the serial number of the third ia-860m card
# (
 #   echo "Process 3 (PID: $$) started"
 #   bw_card_test -p ia860m_card_test_8190705.yaml
 #   sleep 2
 #   echo "Process 3 completed"
# ) &

# Process 4
# Replace serialnumber below with the serial number of the fourth ia-860m card
# (
 #   echo "Process 4 (PID: $$) started"
 #   bw_card_test -p ia860m_card_test_8191054.yaml
 #   sleep 1
 #   echo "Process 4 completed"
# ) &

# Wait for all background processes to finish
wait

echo "All tests have completed!"
