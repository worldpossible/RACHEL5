#!/usr/bin/env python
#
# Copyright World Possible 2023

import argparse
import fileinput
import http.client
import json
import logging
import os
import requests
import subprocess
import sys
import time
import zipfile
from enum import IntEnum

class APICode(IntEnum):
    NONE       = 0
    REGISTER   = 1
    UPDATE     = 2
    INFO       = 3
    FINISHED   = 4

def path_exists(path):
    return os.path.isfile(path) or os.path.isdir(path)

def ubus_cmd(command):
    result = subprocess.run(
        command, 
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    result = result.stdout.decode('utf-8')
    result = result.replace("\t", "").replace("\n", "").replace("\r", "")
    return result  

def cmd(c):
    result = subprocess.Popen(c,
                              shell=True,
                              stdin=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              close_fds=True)
    try:
        result.communicate()
    except KeyboardInterrupt:
        pass
    return (result.returncode == 0)

def sudo_script(s):
    if not cmd("sudo DEBIAN_FRONTEND=noninteractive %s" % s):
        log("SCRIPT_CMD_FAIL: {0}".format(s))
        sys.exit(1)

def sudo(s):
    if not cmd("sudo DEBIAN_FRONTEND=noninteractive %s" % s):
       fail(s + " command failed")

def basedir():
    path = os.path.dirname(os.path.abspath(sys.argv[0]))

    if not path:
        path = "."

    return path

def copy_file(src, dst):
    path = os.path.join(basedir(), src)

    if not os.path.isfile(path):
        fail("Copy failed. Source " + path + "doesn't exist.")

    if not os.path.isdir(os.path.dirname(dst)):
        fail("Copy failed destination folder " +
            os.path.dirname(dst) + " doesn't exist.")

    sudo("cp {0} {1}".format(path,dst))
    log("Copied {0} to {1}.".format(path, dst))

def fail(err):
    api_log("FAIL: {0}".format(err))
    sys.exit(1)

def log(msg):
    logger = logging.getLogger()
    logger.info(msg)

def api_log(msg):
    logger = logging.getLogger()
    logger.info(msg)
    api_update(APICode.UPDATE, msg)

def get_api_address():
    log("GET_API_ADDRESS: Start")

    api_file = "/etc/rachel/install/api.txt"

    if not os.path.exists(api_file):
        log("GET_API: No API file. Using default")

    api_address = ""

    try:
        with open(api_file, "r") as apir:
            api_address = apir.readline().strip()
    except:
        log("GET_API_ADDRESS: Failed reading API address from {0}".format(api_file))
        return ""

    if api_address == "":
        log("GET_API_ADDRESS: No address in {0}. Using default".format(api_file))

    log("GET_API_ADDRESS: Switching API address to {0}".format(api_address))
    args.api_address = api_address

    log("GET_API_ADDRESS: Done")

def get_mac():
    log("GET_MAC: Start")
    address_file = "/sys/class/net/enp2s0/address"
    mac          = ""

    if not os.path.exists(address_file):
        fail("GET_MAC: {0} does not exist".format(address_file))

    try:
        with open(address_file, "r") as address_read:
            mac = address_read.readline().strip()
    except:
        fail("GET_MAC: Failed reading MAC from {0}".format(address_file))
        return ""

    if mac == "":
        fail("GET_MAC: No mac in {0}".format(address_file))

    mac            = mac.replace(":", "")
    args.device_id = mac
    log("GET_MAC: Done")
    return mac


def get_serial():
    log("GET_SERIAL: Start")
    serial = ubus_cmd("dmidecode | grep 95XD1")

    if serial == "":
        fail("GET_SERIAL: No serial in output")

    if not "95XD1" in serial:
        fail("GET_SERIAL: Invalid serial number in output")
        
    words  = serial.split()
    serial = words[-1]
    
    if not "95XD1" in serial:
        fail("GET_SERIAL: Failed to extract serial from output")

    log("GET_SERIAL: Done")
    return serial

def configure_datapost():
    log("Configuring DataPost")
    site_id = get_siteid()
    domain  = "datapost.site"
    site    = site_id + "." + domain

    log("DataPost: Copying config.js")
    conf_dist = "/opt/emulewebservice/node/server-nodejs/config.js.dist"
    conf      = "/opt/emulewebservice/node/server-nodejs/config.js"
    copy_file(conf_dist, conf)

    log("DataPost: Setting config.js servicename")
    servicename = "config.servicename='" + site_id +"';"

    for line in fileinput.input(conf, inplace = 1):
        if "config.servicename=" in line:
            line = servicename;
        print(line.rstrip()) 

    log("DataPost: Setting exim4 mail server domain")
    exim_conf      = "/etc/exim4/update-exim4.conf.conf"
    exim_hostnames = "dc_other_hostnames='" + site +";" + site_id + "';"

    for line in fileinput.input(exim_conf, inplace = 1):
        if "dc_other_hostnames=" in line:
            line = exim_hostnames;
        print(line.rstrip())  

    log("DataPost: Setting roundcube domain in main.inc.php")
    roundcube_conf     = "/etc/roundcube/main.inc.php"
    roundcube_host     = "$rcmail_config['default_host'] = '" + site + "';"

    for line in fileinput.input(roundcube_conf, inplace = 1):
        if "$rcmail_config['default_host']" in line:
            line = roundcube_host;
        print(line.rstrip())  

    log("DataPost: Setting roundcube domain in config.inc.php")
    roundcube_conf     = "/etc/roundcube/config.inc.php"
    roundcube_host     = "$config['default_host'] = '" + site + "';"

    for line in fileinput.input(roundcube_conf, inplace = 1):
        if "$config['default_host']" in line:
            line = roundcube_host;
        print(line.rstrip())  

    offset = -4

    if len(site_id) > offset:
       cmal_siteid = site_id[0 : offset : ] + site_id[offset + 1 : :]

    log("DataPost: Generating new hosts file")

    cmal_address  = "CMAL-" + site_id
    hosts_content = """
127.0.0.1       localhost
127.0.0.1       """ + site + " " + site_id + """
127.0.1.1       """ + cmal_address + """

# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
"""
    log("DataPost: Removing old hosts file")
    sudo("rm /etc/hosts")
    log("DataPost: Creating new hosts file")

    with open("/etc/hosts", "w") as hosts_file:
        hosts_file.write(hosts_content)

    log("DataPost: Updating hostname")
    
    if path_exists("/etc/hostname"):
        sudo("rm /etc/hostname")
        
    with open("/etc/hostname", "w") as hostname_file:
        hostname_file.write(site_id)

    sudo("hostnamectl set-hostname " + site_id)

    log("DataPost: Updating mailname")
    
    sudo("rm /etc/mailname")
    
    with open('/etc/mailname', 'w') as f:
        f.write(site)
        
    log("Restarting exim4")
    sudo("systemctl restart exim4")

    log("Restarting dovecot")
    sudo("/etc/init.d/dovecot restart")

    log("Restarting logind service" )
    sudo("systemctl restart systemd-logind.service")
    
    log("Restarting emule service")
    sudo("systemctl restart emule.service")
    
    log("Restarting datapost-admin service")
    sudo("systemctl restart datapost-admin")

    log("Finished configuring DataPost")







def get_siteid():
    log("Getting MAC address")
    address_file = "/sys/class/net/enp2s0/address"
    mac          = ""

    if not os.path.exists(address_file):
        fail("Failed to get site id from address. File does not exist")

    try:
        with open(address_file, "r") as address_read:
            mac = address_read.readline().strip()
    except:
        fail("Failed reading from MAC address file")

    if mac == "":
        fail("Failed retrieving MAC address")

    mac = mac.replace(":", "")

    if "1c697a" in mac:
        return mac.replace("1c697a", "")
        log("Finished getting site ID")
    if "f44d30" in mac:
        return mac.replace("f44d30", "")
        log("Finished getting site ID")
    
    log("Unsupported device MAC")
    sys.exit(1)

def api_status():
    log("GET_STATUS: Checking connectivity to {0}".format(args.api_address))
    attempts  = 0
    server_up = False
    url       = "http://{0}".format(args.api_address)
    
    while not server_up:
        try:
            response = requests.get(url, verify=False, timeout=5)

            if response.status_code == 200:
                server_up = True
                log("SERVER_MESSAGE: Up")
            else:
                log("API_STATUS: Connection failed with code {0}".format(str(response.status_code)))
                time.sleep(3)
        except requests.ConnectionError:
            attempts += 1
            log("API_STATUS: Connection timed out ({0})".format(str(attempts)))
            
            if attempts > 50:
                log("GET_STATUS: Production server at {0} is not available. Exiting".format(url))
                sys.exit(1)

def api_run():
    api_status()
    get_mac()
    serial    = get_serial()
    response  = api_update(APICode.REGISTER, serial)
    config    = response['path']
    name      = response['name']
    zip_name  = "{0}.zip".format(name)
    zip_path  = "http://{0}{1}".format(args.api_address, config)
    save_path = "/etc/rachel/install/{0}".format(zip_name)
    ext_path  = "/etc/rachel/install/config/"
    api_log("GET_CONFIG: Getting config from {0}".format(zip_path))

    response = requests.get(zip_path, allow_redirects=True)  
    
    if response.status_code != 200:
        fail("GET_CONFIG: Failed getting config from {0}".format(zip_path))
    
    try:
        log("GET_CONFIG: Writing config to {0}".format(save_path))
        open(save_path, 'wb').write(response.content)
    except Exception as e:
        fail("GET_CONFIG: Failed savinh zip to {0}. {1}".format(save_path, str(e)))
        
    try:
        log("GET_CONFIG: Extracting config")

        with zipfile.ZipFile(save_path, 'r') as zip_file:
            zip_file.extractall(ext_path)
    except:
        fail("GET_CONFIG: Failed extracting {0} to {0}".format(save_path, ext_path))
    
    config_script = "{0}config.py".format(ext_path)

    api_log("RUN_CONFIG: Running {0}".format(config_script))    

    if not os.path.exists(config_script):
        fail("RUN_CONFIG: {0} does not exist".format(config_script))
 
    config_cmd = "python3 {0} --device-id={1} --api-address={2}".format(config_script, args.device_id, args.api_address)

    sudo_script(config_cmd)
    api_log("RUN_CONFIG: Done")
    api_update(APICode.FINISHED, "none")
    api_log("Configuration Complete")

def api_update(code, data):
    log("API_UPDATE: Code {0}".format(str(code)))
    info_code = int(code)
    api       = "http://{0}/api.php".format(args.api_address)
    info      = { 
        'device_id': args.device_id, 
        'code': info_code, 
        'data': data 
    }
    attempts  = 0
    available = False
    
    while not available:
        try:
            response = requests.post( api, data = info, timeout=5)

            if response.status_code == 200:
                available = True
            else:
                log("API_UPDATE: Connection attempt failed with code {0}".format(str(response.status_code)))
                
                if response.json != None:
                    log("API_UPDATE: Server Response {0}".format(response.json()))
                time.sleep(3)
        except requests.ConnectionError:
            attempts += 1
            log("API_UPDATE: Connection attempt timed out ({0})".format(str(attempts)))
            time.sleep(3)

            if attempts > 7:
                log("API_UPDATE: Production server at {0} is not available. Exiting".format(api))
                sys.exit(1)

    responseJSON = json.loads(response.text)
    message      = responseJSON['responseText']
    log("API_UPDATE: Server Message - {0}".format(message))
    return responseJSON

def setup_logging():
    print("Setting up logging")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter      = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)
    file_handler = logging.FileHandler('/etc/rachel/logs/firstboot.txt')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)
    print("Finished setting up logging")

def parse_args():
    print("PARSE_ARGS: Start")
    global args
    parser  = argparse.ArgumentParser()
    in_args = parser.add_argument_group(description='Options')
    in_args.add_argument('--version',
                          action='store',
                          help='The API version this script targets',
                          default='2023.10',
                          dest='version')
    in_args.add_argument('--device-id',
                          action='store',
                          dest='device_id')                    
    in_args.add_argument('--api-address',
                          action='store',
                          help='The default address of the API server',
                          default='192.168.1.11',
                          dest='api_address')
    in_args.add_argument('--log-path',
                          action='store',
                          help='The path to store API logs to',
                          default='/etc/rachel/logs/firstboot.txt',
                          dest='log_path')                                               
    args = parser.parse_args()
    print("PARSE_ARGS: Done")

def main():
    parse_args()
    setup_logging()
    configure_datapost()
    get_api_address()
    api_run()

if __name__== "__main__":
  main()
