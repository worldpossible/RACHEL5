# RACHEL 5

This document covers the build process used to create the RACHEL5 install/recovery USB.

## Overview

[ECS](https://www.ecsusa.com/en) provided us with updated hardware: the CMAL 150. It is the same
basic device used for the RACHEL 4 (CMAL 100) with two hardware improvements: a better
WiFi card, and a battery heat-dissipation plate. It also includes a software improvement in the
form of a 64-bit OS. The CMAL 100 had 64-bit hardware, but used a 32-bit OS. This change requires
re-building the RACHEL software collection and configuration on the new system.

## The Plan

* Start with the default CMAL 150 software (Ubuntu 16.04.5 LTS)
* Follow the instructions below to create the RACHEL 5 system
* Clone the finished RACHEL 5 device and replace the disk image on the RACHEL 4.1.2 USB

NOTE: Do not upgrade the system software. An `apt upgrade` will disable the WiFi status
LED on the CMAL 150. We have not figured out how to upgrade the system software without
disabling the WiFi status light.

# The Build Process

Starting with a bare CMAL 150 as provided by ECS (or a cloned reinstall of same):

## Initial Setup and Conveniences

```
# get in
ssh cap@192.168.x.x

# verify the system (should be Ubuntu 16.04.5 LTS and x86_64
lsb_release -d
uname -p

# set sudo to use target home directory
echo 'Defaults always_set_home' | sudo EDITOR='tee -a' visudo

sudo bash

# make vi a bit nicer
cat >> /root/.vimrc<< EOF
set softtabstop=4 shiftwidth=4 expandtab
set vb
set encoding=utf-8
set fileencoding=utf-8
EOF

# allow remote root login
sed -i '/PermitRootLogin/ s/prohibit-password/yes/' /etc/ssh/sshd_config
service sshd restart

# change root password
passwd root

# optional ssh keys
vi /root/.ssh/authorized_keys

# log out and back in as root
```

## Network Changes

```
# 192.168.88.1 is less likely to conflict with existing networks than 192.168.1.1
# It's also all over the RACHEL documentation
# we used to also edit some nodogsplash (captive WiFi) files, but it seems unnecessary on this version
perl -pi -e 's/192\.168\.1\./192.168.88./g' \
    /etc/config/dhcp \
    /etc/config/network

# change SSID
sed -i '/option ssid .CMAL-2.4G-/ s/CMAL-2.4G-..../RACHEL-SLOW/' /etc/config/wireless
sed -i '/option ssid .CMAL-5G-/ s/CMAL-5G-..../RACHEL/' /etc/config/wireless

reboot
```

## Change the Router Admin Password

1. Connect to the device through WiFi (RACHEL) and browser (http://192.168.88.1)
2. Change the router admin password through built-in admin interface.
3. Default password is admin/admin
4. Go to "guest logins" and update it to the preferred default RACHEL password

## Get Configuration Files

```
# XXX This needs to be updated to a github pull from this repository
# XXX currently it's an rsync from my desktop
rsync -av jfield@192.168.x.x:/Volumes/Master/RACHEL/CAP3/rachel-plus-v3/files/ /root/files/
```

### Configure nginx / php-fpm

```
# install some dependencies
apt update
apt install -y php7.0-cli php7.0-fpm php7.0-sqlite3 sqlite3

# change "default" server to use :8090 (gets the default CMS out of our way)
sed -i '/80 default_server/ s/80/8090/' /etc/nginx/sites-available/default

# use our custom website config file
cp /root/files/rachel.nginx.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/rachel.nginx.conf /etc/nginx/sites-enabled/

# make sure everything runs as root so our web admin can do admin-like stuff
# examples: ubus/battery on CMAL100
sed -i '/^user / s/www-data/root/' /etc/nginx/nginx.conf
sed -i '/^user =/ s/www-data/root/' /etc/php/7.0/fpm/pool.d/www.conf
sed -i '/^group =/ s/www-data/root/' /etc/php/7.0/fpm/pool.d/www.conf

# allow slower scripts more time to complete
sed -i '/^max_execution_time =/ s/30/300/' /etc/php/7.0/fpm/php.ini

# allow uploading large files (like videos)
sed -e '/^upload_max_filesize/ s/[[:digit:]]\+M/1024M/' -i /etc/php/7.0/fpm/php.ini

# the system needs extra persmission to let php-fpm run as root
sed -i '/ExecStart/ s/--nodaemonize/--allow-to-run-as-root --nodaemonize/' /lib/systemd/system/php7.0-fpm.service
systemctl daemon-reload
service php7.0-fpm restart
service nginx restart

# XXX include other php dependencies here?

# NOTE: on this device the admin portal (port 8080) runs on uhttpd (migrate to nginx?)

```

### Install RACHEL contentshell

```
# XXX The version in github is currently not updated. It should be.
# XXX But for now we use a copy from the 4.1.2 recovery USB rsync'd from my desktop
mkdir /.data/RACHEL
ln -s /.data/RACHEL /media/RACHEL
rsync -av "jfield@192.168.x.x:~/RACHEL5/contentshell-4.1.2/" /media/RACHEL/rachel/
```

At this point, you should be able to go to http://192.168.88.1 and see an empty RACHEL front page

### Install Stats Package

```
cd
apt install libncursesw5-dev
wget https://tar.goaccess.io/goaccess-1.9.3.tar.gz
tar -xzvf goaccess-1.9.3.tar.gz
cd goaccess-1.9.3
./configure --enable-utf8
make
make install
sed -i '/^#time-format %H:%M:%S/ s/#//' /usr/local/etc/goaccess/goaccess.conf
sed -i '/^#date-format %d\/%b\/%Y/ s/#//' /usr/local/etc/goaccess/goaccess.conf
sed -i '/# NCSA Combined Log Format$/{n;s/^#//}' /usr/local/etc/goaccess/goaccess.conf
# XXX we can improve these stats by configuring it to ignore javascript, css, and such
```

### Install DataPost

Based on the [complete instructions here](https://github.com/worldpossible/wiki-datapost/wiki/Installing-eMule-on-a-Rachel-Plus)
we did the following:

```
cd /opt
# XXX for git clone to work I had to put my personal ssh keys in /root/.ssh
# XXX we should make the repo public instead
git clone git@github.com:worldpossible/internetdelivered-emule-webservice.git emulewebservice
cd emulewebservice/bin/
./install.sh
# wait several minutes
# we should revert datapost code to not change this because we have to change it back:
sed -i '/php7.1-fpm.sock/ s/php7.1/php7.0/' /etc/nginx/sites-available/rachel.nginx.conf
service nginx restart
# we should also stop datapost from inserting the webmail link because we end up with two:
sed -i '0,/WEBMAIL/{/WEBMAIL/d}' index.php

# At this point webmail should work, but we have no module to show
# to get that, we install some default modules:
rsync -av "jfield@192.168.x.x:~/RACHEL5/modules-4.1.2/" /media/RACHEL/rachel/modules

# Add bold to the DataPost "not configured" message:
sed -i '/<p>DataPost is not/s/<p>/<p><b>/' /media/RACHEL/rachel/modules/en-datapost/rachel-index.php
sed -i '/<b>DataPost is not/s/<\/p>/<\/b><\/p>/' /media/RACHEL/rachel/modules/en-datapost/rachel-index.php

# OK, how about:
apt install npm
npm install -g n
n 6.17.1
rm /usr/bin/node
ln -s /usr/local/bin/nodejs /usr/bin/node

### Cleanup?
```
    apache2 not running (ok? do we need nginx hub.conf?)
    looks like apache2 is gone from rachel 4 (good? one webserver is plenty, thank you)

    symlink: ln -s /usr/bin/nodejs /usr/bin/node

    no longer use /root/rachel-scripts/rachelStartup.sh ... is that OK?
    now use /etc/rachel/boot/ ... but it just does the firstboot.sh stuff

    are we using /var/kiwix/rachelKiwixStart.sh or /root/rachel-scripts/rachelKiwixStart.sh?
    seems the first one is in the /etc/rc*.d files? is the second a boondoggle?
```
