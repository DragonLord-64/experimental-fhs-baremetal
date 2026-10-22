#!/usr/bin/env python3
import requests
import logging
import time
import urllib3




log_dur = 200 #Duration to log in seconds
user = ""  #PDU username
password = "" #PDU password
pdu_addr = ""
outlet1 = "" #Outlet connected to PSU1
outlet2 = "" #Outlet connected to PSU2


max_power=0 #records max power from test

urllib3.disable_warnings()



logging.basicConfig(
    filename=f'pdu_power_monitor_{time.time()}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a' # 'a' for append (default), 'w' for overwrite each run
)


def log_pdu_outlet_status():
    global max_power
    if not all([user, password, pdu_addr, outlet1]):
        print("Error: Missing one or more required configuration variables (USER, PASS, PDU_ADDR, OUTLET)")
        return

    # Construct the URL
    url1 = f"https://{pdu_addr}/jaws/monitor/outlets/{outlet1}"
    url2 = f"https://{pdu_addr}/jaws/monitor/outlets/{outlet2}"
    print(url1 + url2)
    command1 = ["curl", "-s", "-k", "-u", f"{user}:{password}", "-X", "GET", f"{url1}"]
    command2 = ["curl", "-s", "-k", "-u", f"{user}:{password}", "-X", "GET", f"{url2}"]
    try:
        # Perform the GET request with basic authentication and verify=False to ignore SSL errors
        # The verify=False corresponds to the shell's -k (insecure) flag
        
        response1 = requests.get(url1, auth=(user, password), verify=False, timeout=10)
        response2 = requests.get(url2, auth=(user, password), verify=False, timeout=10)

        data1 = response1.json()
        current1 = data1.get("current")
        voltage1 = data1.get("voltage")
        pf1= data1.get("power_factor")

        data2 = response2.json()
        current2 = data2.get("current")
        voltage2= data2.get("voltage")
        pf2= data2.get("power_factor")


        try:
            power1 = float(voltage1) * float(current1)
            power2= float(voltage2) * float(current2)
            total_power= power1+power2
        except ValueError:
            print(f"Error: Non-numeric values found for voltage ({voltage1}) or current ({current1}).")
            return

        # log the results       
        logging.info(f"psu1: current = {current1}")
        logging.info(f"psu1: voltage = {voltage1}")
        logging.info(f"psu1: pf = {pf1}")
        logging.info(f"psu1: power (VA) {power1}")
        logging.info(f"psu2: current = {current2}")
        logging.info(f"psu2: voltage = {voltage2}")
        logging.info(f"psu2: pf = {pf2}")
        logging.info(f"psu2: power (VA) = {power2}")
        logging.info(f"total power (VA) = {total_power} \n\n")

        if(total_power>max_power):
            max_power = total_power

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the request: {e}")
    except ValueError as e:
        print(f"Failed to parse JSON response: {e}")

if __name__ == "__main__":

    start_time = time.time()
    end_time = start_time + log_dur  # Set the end time to 30 seconds from now
    logging.info(f"\n\n\n--------CONFIGURATION------")
    logging.info(f"PDU username: {user}")
    logging.info(f"PDU pass: *****")
    logging.info(f"PDU IP: {pdu_addr}")
    logging.info(f"PSU 1 Outlet: {outlet1}")
    logging.info(f"PSU 2 Outlet: {outlet1}")
    logging.info(f"\n\n\n--------START TEST------")
    # Loop until the current time exceeds the end time
    while time.time() < end_time:
        print(f"duration {time.time()- start_time}")
        log_pdu_outlet_status()
        #log rate maximum 10Hz. Slower due to http request delay.
        time.sleep(0.1)
    logging.info(f"MAX POWER RECORDED {max_power}")
    logging.info(f"\n\n\n--------END TEST------")
