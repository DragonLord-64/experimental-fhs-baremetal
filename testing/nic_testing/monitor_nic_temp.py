import os
import logging
import time
import subprocess
import re

log_dur = 10
max_temp=0

logging.basicConfig(
    filename=f'nic_temp_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a' # 'a' for append (default), 'w' for overwrite each run
)


def log_nic_temp():
    global max_temp

    try:
        result = subprocess.run(['sudo mget_temp -d 81:00.0'], shell=True, env=os.environ, capture_output=True, text=True, check=True)
        output = result.stdout
        match = re.search(r"(\d+\.?\d*)", output)
        if match:
            temperature = float(match.group(1))
            logging.info(f"nic temperature: {temperature}")
            print(f"nic temperature: {temperature}")
            if(temperature>max_temp):
                max_temp = temperature
                logging.info(f"new max temp: {max_temp}")
        else:
            print("Could not parse temperature from output.")
    except Exception as e:
        print(f"You got an error: {e}")




if __name__ == "__main__":

    start_time = time.time()
    end_time = start_time + log_dur

    while time.time() < end_time:

        print(f"duration {time.time()- start_time}")
        log_nic_temp()
        time.sleep(1)
        
    logging.info(f"MAX TEMP RECORDED {max_temp}")
    print(f"MAX TEMP RECORDED {max_temp}")
