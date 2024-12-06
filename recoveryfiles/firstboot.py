import argparse
import fileinput
import logging
import os
import subprocess
import sys
import time

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

def sudo(s):
    if not cmd("sudo DEBIAN_FRONTEND=noninteractive %s" % s):
       error(s + " command failed")

def basedir():
    path = os.path.dirname(os.path.abspath(sys.argv[0]))

    if not path:
        path = "."

    return path

def copy_file(src, dst):
    path = os.path.join(basedir(), src)

    if not os.path.isfile(path):
        die("Copy failed. Source " + path + "doesn't exist.")

    if not os.path.isdir(os.path.dirname(dst)):
        die("Copy failed destination folder " +
            os.path.dirname(dst) + " doesn't exist.")

    sudo("cp {0} {1}".format(path,dst))
    log("Copied {0} to {1}.".format(path, dst))

def error(err):
    log("ERROR: " + err)
    sys.exit(1)

def log(msg):
    logger = logging.getLogger()
    logger.info(msg)
        
def path_exists(path):
    return os.path.isfile(path) or os.path.isdir(path)

def run():
    configure_datapost()
    log("Finished running firstboot functions")

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

    if not path_exists(address_file):
        error("Failed to get site id from address. File does not exist")

    try:
        with open(address_file, "r") as address_read:
            mac = address_read.readline().strip()
    except:
        error("Failed reading from MAC address file")

    if mac == "":
        error("Failed retrieving MAC address")

    mac = mac.replace(":", "")

    if "1c697a" in mac:
        return mac.replace("1c697a", "")
        log("Finished getting site ID")
    if "f44d30" in mac:
        return mac.replace("f44d30", "")
        log("Finished getting site ID")
    
    log("Unsupported device MAC")
    sys.exit(1)

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
 
def main():
    setup_logging()
    run()
    sys.exit(0)

if __name__== "__main__":
  main()
