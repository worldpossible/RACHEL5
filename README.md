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
LED on the CMAL 150. The WiFi LED is operated through ath10k drivers that are implemented
as proprietary kernel modules. Any upgrades will include some kernal upgrades that seem
to disable this driver.

## The Build Process

Start with a bare CMAL 150 as provided by ECS or a cloned reinstall of same.

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
# we used to also edit some nodogsplash (captive WiFi) files,
# but it seems unnecessary on this version
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
cd /root
git clone https://github.com/worldpossible/RACHEL5.git
mv RACHEL5/buildfiles .
rsync -av rsync://dev.worldpossible.org/rachel5/buildfiles/ ./buildfiles/

```

## Configure nginx / php-fpm

```
# install some dependencies
apt update
apt install -y php7.0-cli php7.0-fpm php7.0-sqlite3 sqlite3

# change "default" server to use :8090 (gets the default CMS out of our way)
sed -i '/80 default_server/ s/80/8090/' /etc/nginx/sites-available/default

# use our custom website config file
cp /root/buildfiles/rachel.nginx.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/rachel.nginx.conf /etc/nginx/sites-enabled/

# make sure everything runs as root so our web admin can do admin-like stuff
# examples: ubus/battery on CMAL100
sed -i '/^user / s/www-data/root/' /etc/nginx/nginx.conf
sed -i '/^user =/ s/www-data/root/' /etc/php/7.0/fpm/pool.d/www.conf
sed -i '/^group =/ s/www-data/root/' /etc/php/7.0/fpm/pool.d/www.conf

# We used to see this in the logs:
#   "WARNING: [pool www] server reached pm.max_children setting (5), consider raising it"
# So:
sed -i '/^pm.max_children = 5/ s/5/10/' /etc/php/7.0/fpm/pool.d/www.conf

# allow slower scripts more time to complete
sed -i '/^max_execution_time =/ s/30/300/' /etc/php/7.0/fpm/php.ini

# allow uploading large files (like videos)
sed -e '/^upload_max_filesize/ s/[[:digit:]]\+M/1024M/' -i /etc/php/7.0/fpm/php.ini

# the system needs extra persmission to let php-fpm run as root
sed -i '/ExecStart/ s/--nodaemonize/--allow-to-run-as-root --nodaemonize/' /lib/systemd/system/php7.0-fpm.service
systemctl daemon-reload
service php7.0-fpm restart
service nginx restart

```

## Install RACHEL contentshell

```
mkdir /.data/RACHEL
ln -s /.data/RACHEL /media/RACHEL
git clone --branch v5.0.0 --depth 1 https://github.com/worldpossible/contentshell.git
rm -rf contentshell/.git
mv contentshell /media/RACHEL/rachel
```

At this point, you should be able to go to http://192.168.88.1 and see an empty RACHEL front page

## Install Stats Package

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

# clean up
rm -rf goaccess-*

```

## Install DataPost

Based on the [complete instructions here](https://github.com/worldpossible/wiki-datapost/wiki/Installing-eMule-on-a-Rachel-Plus)
we did the following:

```
cd /opt
# XXX for git clone to work on a private repository you have to put your
# github ssh keys in /root/.ssh (or do ssh-kegen and add your /root/.ssh key to github)
git clone git@github.com:worldpossible/internetdelivered-emule-webservice.git emulewebservice
cd emulewebservice/bin/
./install.sh
# wait several minutes

# XXX we should revert datapost code to not change this because we have to change it back:
sed -i '/php7.1-fpm.sock/ s/php7.1/php7.0/' /etc/nginx/sites-available/rachel.nginx.conf
service nginx restart
# the above happens when install_emulewebserver.sh copies over config/nginx/sites-available/rachel.nginx.conf

# XXX we should also stop datapost from inserting the webmail link
# because we end up with two:
sed -i '0,/WEBMAIL/{/WEBMAIL/d}' /media/RACHEL/rachel/index.php
# the above takes place in /opt/emulewebservice/bin/install_emulewebserver.sh

# At this point webmail should work, but we have no module to show
# to get that, we install some default modules:
rsync -av rsync://dev.worldpossible.org/rachel5/recoveryfiles/modules-5.0.0.tar.gz /media/RACHEL/rachel
tar -xzvf /media/RACHEL/rachel/modules-5.0.0.tar.gz -C /media/RACHEL/rachel/
rm /media/RACHEL/rachel/modules-5.0.0.tar.gz

# Add bold to the DataPost "not configured" message:
sed -i '/<p>DataPost is not/s/<p>/<p><b>/' /media/RACHEL/rachel/modules/en-datapost/rachel-index.php
sed -i '/<b>DataPost is not/s/<\/p>/<\/b><\/p>/' /media/RACHEL/rachel/modules/en-datapost/rachel-index.php

# XXX at this point, the stats page no longer works -- something in php changed?
# XXX nope! emule copies over it's own version of background.php from
# XXX /opt/emulewebservice/config/media/RACHEL/rachel/admin/background.php
# XXX this takes place in the install_emulewebservice.sh script
# XXX revert to the version we installed above from contentshell-4.1.2

# At this point, dovecot and exim4 are running, apache is not needed,
# but the emule service itself needs a new vesrion of nodejs
apt install npm
npm install -g n
n 6.17.1
rm /usr/bin/nodejs
ln -s /usr/local/bin/node /usr/bin/nodejs
service emule start

# XXX emule stays up, but we still don't see a working datapost... researching...
# ok, that was just because I was accessing the device through my own /etc/hosts
# setup where the url was http://rachel5/ -- but if you access through the IP it
# works. Should we change /medid/RACHEL/rachel/modules/en-datapost/rachel-index.php
# to use $_SERVER[SERVER_ADDR] instead of $_SERVER[HTTP_HOST]?

# XXX going through the verification steps on the above emule installation page,
# after I successfully sent an internal message I ran into a problem trying to delete
# the message: "Server Error: UID MOVE: Mailbox doesn't exist: Trash (0.000 + 0.000 secs)."
# this was solved by going to "manage folders" and manually adding a folder called "Trash"
# ... this should be the default, no? Note I found online:
#  "there is a setting in the Roundcube config file - create_default_folders -
#  which makes it auto create defailt folders on first login."

# sending a message internally worked
# sending a message remotely worked
# sending a message remote-to-rachel worked

# XXX: on the register link on RACHEL there is a missing icon
# XXX: no indication which fields are required (oh, it's all ... link to a gps tool?
# XXX: link to a default or choosable icon?)
# XXX: all data lost if you submit with missing info
# XXX: when done, you get a back button that takes you to the same blank form
# Note: admin password: grep admin /opt/emulewebservice/node/datapost-admin/app.js
# XXX: no way to see registration data? can you change by overwriting?

# android app (i got it from datapost.site, not RACHEL device):
# XXX: initial page doesn't inclue sync buttons (shows profile) - you have to go
# XXX: to menu > home
```

## Install Kolibri

```
add-apt-repository ppa:learningequality/kolibri
apt update
apt install kolibri
# yes on startup, default user "root"

sed -i '/^# KOLIBRI_LISTEN_PORT/s/# //;s/8080/9090/' /etc/kolibri/daemon.conf
sed -i '/^# KOLIBRI_USER/s/# //;s/kolibri/root/' /etc/kolibri/daemon.conf

# it may not be running because of a port clash anyway
service kolibri stop

# kolibri installs its files in /root/.kolibri which we symlink:
mv /root/.kolibri /media/RACHEL/.kolibri
ln -s /media/RACHEL/.kolibri /root/.kolibri
service kolibri start

```

## Install KA-Lite

```
# needed for dpkg installation
apt install -y unzip

dpkg -i /root/buildfiles/ka-lite_0.17.4-0ubuntu2_all.deb
    # run at startup? yes
    # which user? root
    # confirm? ok

# install contentpacks (everything but videos, I believe) 
kalite manage retrievecontentpack local en /root/buildfiles/contentpacks/en-0.17-fixed.zip
kalite manage retrievecontentpack local es /root/buildfiles/contentpacks/es.zip
kalite manage retrievecontentpack local fr /root/buildfiles/contentpacks/fr.zip
kalite manage retrievecontentpack local hi /root/buildfiles/contentpacks/hi.zip
kalite manage retrievecontentpack local pt-BR /root/buildfiles/contentpacks/pt-BR.zip
kalite manage retrievecontentpack local pt-PT /root/buildfiles/contentpacks/pt-PT.zip
kalite manage retrievecontentpack local sw /root/buildfiles/contentpacks/sw.zip

# move kalite to big partition
kalite stop
mv /root/.kalite /media/RACHEL/.kalite
ln -s /media/RACHEL/.kalite /root/.kalite
kalite start

# at this point ka-lite should be working on port 8008, but there is no
# entry on the RACHEL index. We don't install that because it would require
# installing the 40GB of videos at this point, but we'd rather do that
# during the rest of the content install in production
 
```


## Install Kiwix

```
# install from web
cd /root
wget https://download.kiwix.org/release/kiwix-tools/kiwix-tools_linux-x86_64.tar.gz
tar -xzvf kiwix-tools_linux-x86_64.tar.gz
mkdir /var/kiwix /var/kiwix/bin
mv /root/kiwix-tools_linux-x86_64-3.7.0-2/* /var/kiwix/bin
rm -rf kiwix-tools*

# updated admin/version.php to use kiwix-serve -V
# XXX also needed to do this becasue some modules check the old kiwix version
/var/kiwix/bin/kiwix-serve -V | grep kiwix-tools | cut -d ' ' -f2 > /etc/kiwix-version

# XXX I guess there's been a change where kiwix doesn't need a separate index file?
# so we use a newer version of rachelKiwixStart.sh from kn-wikipedia
# (I'm sure it's elsewhere as well :)
cp /root/buildfiles/rachelKiwixStart.sh /var/kiwix/

# this allows kiwix to run and show an informative page even if there
# are no modules installed
cp /root/buildfiles/empty.zim /var/kiwix/

# this is also changed (and available in kn-wikipedia) to point to a
# better location for the startup script
cp /root/buildfiles/init-kiwix-service /etc/init.d/kiwix
systemctl daemon-reload
chmod +x /etc/init.d/kiwix 
update-rc.d kiwix defaults
service kiwix start

# XXX given how much kiwix has changed, there may be some modules
# that need to be updated? 

```

## Install Moodle

Newer versions of Moodle require newer versions of PHP. It may take some surgery to install another PHP
and all required libaries and such without causing any conflicts with the system PHP (stuck at 7.0), so
we opt for Moodle 3.6.10, the latest release to support PHP 7.0. You can find this and other will
documented download options on their [legacy page](https://download.moodle.org/releases/legacy/).

```
# php dependencies
apt install -y php7.0-mysql php7.0-xmlrpc php7.0-curl php7.0-zip

# used to be this:
# apt install -y php7.0-mysql php7.0-gd php7.0-xmlrpc \
#    php7.0-intl php7.0-xml php7.0-curl php7.0-zip \
#    php7.0-soap php7.0-mbstring
# but several of those modules are already installed on the CMAL150

# we opt for mariadb -- it's a drop-in replacement for mysql but
# has better performance (it's a fork of Oracle's MySQL)
# root password: Rachel+1
apt install mariadb-server

# Following instructions at https://docs.moodle.org/32/en/Installation_quick_guide
# we do the following:
mysql -u root -pRachel+1
CREATE DATABASE moodle DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,DROP,INDEX,ALTER ON moodle.* TO 'moodleuser'@'localhost' IDENTIFIED BY 'Rachel+1';

# some tweaks to the config
cat /root/buildfiles/mysql-additions.txt >> /etc/mysql/my.cnf

# move the data directory
service mysql stop
mv /var/lib/mysql /media/RACHEL/mysql
# so people can find it where they expect it
ln -s /media/RACHEL/mysql /var/lib/mysql

# also: must give permission via apparmor:
echo "  /media/RACHEL/mysql/ r," >> /etc/apparmor.d/local/usr.sbin.mysqld
echo "  /media/RACHEL/mysql/** rwk," >> /etc/apparmor.d/local/usr.sbin.mysqld
echo "  /proc/*/status r," >> /etc/apparmor.d/local/usr.sbin.mysqld
service apparmor restart
service mysql start

# make a data directory for moodle
mkdir /media/RACHEL/moodle-data
chmod 777 /media/RACHEL/moodle-data

# ok, now install moodle itself (just a directory full of PHP):
cd /root
wget https://download.moodle.org/download.php/direct/stable36/moodle-3.6.10.tgz
tar -xzvf moodle-3.6.10.tgz
rm -rf /root/moodle-3.6.10.tgz
mv moodle /media/RACHEL/moodle
ln -s /media/RACHEL/moodle /media/RACHEL/rachel/moodle
cd /media/RACHEL/moodle

# configure moodle
cp config-dist.php config.php
sed -i '/CFG->dbtype/ s/pgsql/mariadb/' config.php
sed -i '/CFG->dbuser/ s/username/moodleuser/' config.php
sed -i '/CFG->dbpass/ s/password/Rachel+1/' config.php
sed -i '/CFG->dataroot/ s/\/home\/example\/moodledata/\/media\/RACHEL\/moodle-data/' config.php
# relative URL
sed -i "/CFG->wwwroot/ s/example.com/\'.\$_SERVER['SERVER_ADDR'].'/" config.php
# performance enhancement
sed -i "/\$CFG->xsendfile = 'X-Accel-Redirect';/ s/\/\///" config.php
sed -i "/\$CFG->xsendfilealiases/ s/\/\///" config.php
sed -i "/'\/dataroot\/' => \$CFG->dataroot,/ s/\/\///" config.php
sed -i "/'\/dataroot\/' => \$CFG->dataroot,/ a );" config.php

vi /etc/crontab
    # they recommend every minute, but given how little use this
    # is really likely to get, I'm going to push to every 15
    */15 * * * *    root /usr/bin/php /media/RACHEL/moodle/admin/cli/cron.php > /dev/null

# you can move on now to web-based configuration through Moodle itself

# Go to:
 http://192.168.88.1/moodle/
# there will be a minute or so delay the first time
# 1. terms and conditions: continue
# 2. server checks: continue
# 3. wait several minutes for tables to be made, then: continue
    -> mysql -u root -pRachel+1
    -> show processlist
    -> when empty (for at least several seconds) reload browser
# 4. finish configuration in browser:
Password: Rachel+1
Email: admin@localhost.com
# click update profile
# (may timeout and require the "show processlist" dance to figure out when to reload)
# (may need to go to Administration > Site administration > Notifications)
Full site name: "Moodle on RACHEL"
Short name: "moodle"
# save changes

```

## Misc Configuration

```
# this is used by the recovery USB in the recover.sh script
# -- use whatever version you're on, obviously
echo "v5.0.0" > /etc/rachelinstaller-version

# I can't find versioning in the actual emule code, but
# [this page](https://github.com/worldpossible/datapost-field-util)
# claims it is 0.2.1 so we'll go with that until there's better information
echo "0.2.1" > /etc/datapost-version

# these are slow, so we just save them
kolibri --version | cut -d " " -f 3 > /etc/kolibri-version
kalite --version > /etc/kalite-version

# lots of tweaks were done to contentshell to fix minor differences with between
# the CMAL100/CMAL150 but those will be checked in to github as v5.0.0

# install php stemming (what uses this now?
# the modules i checked included their own stemmer?)
apt -y install php7.0-dev
yes yes | pecl install -O /root/buildfiles/stem-2.0.0.tgz
echo extension=stem.so > /etc/php/7.0/mods-available/stem.ini
ln -s /etc/php/7.0/mods-available/stem.ini /etc/php/7.0/cli/conf.d/30-stem.ini
ln -s /etc/php/7.0/mods-available/stem.ini /etc/php/7.0/fpm/conf.d/30-stem.ini

# not sure it matters in practice, but we should be running in server mode, not GUI mode
systemctl set-default multi-user.target
# `runlevel` doesn't work so check with
systemctl get-default

# we had sporadic issues on the CMAL100 with /.data (and thus /media/RACHEL) not
# being mounted quickly enough during startup so that some services would fail to
# start -- we patched the init scripts to wait for the mount. I don't know if the
# CMAL150 has the same issue (I haven't seen it), but to be safe we include the
# same patches here. Patches created with: diff -Naur file.orig file.edit
patch /etc/init.d/ka-lite -i /root/buildfiles/ka-lite.init.patch
patch /etc/init.d/kolibri -i /root/buildfiles/kolibri.init.patch
patch /etc/init.d/mysql -i /root/buildfiles/mysql.init.patch
# kiwix already has the wait code in kiwix-init-service

# we want a nicer MOTD
cat >> /etc/update-motd.d/00-header << EOF
printf "Welcome to RACHEL from World Possible \n\n"
printf "RACHEL: $(cat /etc/rachelinstaller-version) \n"
printf "MAC: $(cat /sys/class/net/enp2s0/address) \n"
EOF

# this is where RACHEL keeps it's own install & startup scripts
mkdir /etc/rachel
mkdir /etc/rachel/boot
mkdir /etc/rachel/install
mkdir /etc/rachel/logs
cp /root/buildfiles/startup.sh /etc/rachel/boot/

# the firstboot.py installer script will be put in place
# later by recovery.sh on the USB -- this is because the
# version of firstboot.py varies depending on the installation
# type (recovery vs. production)

# add the rachel startup script to the
# machine startup and make sure it's executble
sed -i '/^touch/i bash /etc/rachel/boot/startup.sh &' /etc/rc.local
chmod +x /etc/rc.local

```

## Make tar files

You must tar up the following since they are on the big HD -- they will not be part of
the clonezilla copy and are instead put in place by recovery.sh during USB recovery. These
tar files are too big to keep in github, so we keep them on the ftp server. But here's what
you need to tar up:

```
cd /media/RACHEL
tar -czvf mysql.tar.gz mysql
tar -czvf moodle.tar.gz moodle
tar -czvf moodle-data.tar.gz moodle-data
tar -czvf kalite.tar.gz .kalite
tar -czvf kolibri.tar.gz .kolibri
tar --exclude='modules' -czvf contentshell.tar.tz rachel
cd rachel
tar -czvf ../modules.tar.tz modules
```

After these are made you can transfer them to http://ftp.worldpossible.org/rachel6/recoveryfiles and
delete them locally.


## Cleanup

```
# clear out any hardcoded mac addresses (firstboot.py updates these anyway, though)
sed -i '/default_host/ s/......\.datapost\.site//' /etc/roundcube/main.inc.php
sed -i '/default_host/ s/......\.datapost\.site//' /etc/roundcube/config.inc.php
# even in the DB
sqlite3 /var/lib/dbconfig-common/sqlite3/roundcube/roundcube 'delete from identities'
sqlite3 /var/lib/dbconfig-common/sqlite3/roundcube/roundcube 'delete from users'

# Get rid of leftover install files
apt clean

# get rid of unused packages
apt autoremove

rm -rf /root/RACHEL5
rm -rf /root/buildfiles
rm -rf /.Trash-0
rm -rf /tmp/firstboot.log
rm -rf /tmp/sortmods*
rm -rf /tmp/do_tasks.log
rm /srv/.git* # this was a one-time thing

# shut down servers
service nginx stop
service php7.4-fpm stop
service exim4 stop
service dovecot stop
service ka-lite stop
service kolibri stop
service mysql stop

# sanitize logs
find /var/log -name '*.gz' -delete
find /var/log -name '*.1' -delete
for i in $(find /var/log -type f); do cat /dev/null > $i; done

# remove install logs and firstboot stuff (it's installed by recovery.sh on the USB)
rm /etc/rachel/logs/*
rm -rf /etc/rachel/install/*

# sanitize history
:> /home/cap/.bash_history
:> /home/cap/.viminfo
:> /var/mail/cap
:> /root/.viminfo
rm /root/.mysql_history
rm /root/.wget-hsts
rm /root/.ssh/known_hosts

# if you want to clear out freespace (makes zipped filesystem smaller)
cat /dev/zero > /zerofile; rm /zerofile

:> /root/.bash_history
shutdown -h now

```

## Making a Clonezilla Image

After you have a version of RACHEL working to your satisfaction, you need to shut it down cleanly
and take an image using Clonezilla. The details are a bit too involved to include here, but basically
you make a Clonezilla USB, something like this on the mac:

```
diskutil partitionDisk /dev/disk## MBR FAT32 CLONEZILLA
cd /Volumes/Master/RACHEL/RACHEL5
unzip clonezilla-live-3.1.3-16-i686.zip -d /Volumes/CLONEZILLA
diskutil unmountDisk CLONEZILLA
```

Then you want to boot with that USB. Not sure how to integrate (grub.config?), but this is the command line if you don't want to do it all interatively:

```
/usr/sbin/ocs-sr -q2 -c -j2 -z9p -i 4096 -sfsck -scs -senc -p poweroff savedisk 2025-01-08-23-img mmcblk0
```

But assuming interactive: choose "To RAM", then have it clone the whole eMMC (clonedisk).
You'll end up with a Clonzilla  image directory used in the next step, which will restore the device to a
known state.

Note that isn't all that needs to be done -- the production and recvoery USBs described in the next
sections have a number of scripts that have to run to set stuff up that isn't part of cloning. Such as
the giant media drive and moving some directories there, configuration that is different from machine
to machine, etc. Those things happen in the USB's recovery.sh, firstboot.py, and whatever config script
is pulled from the production server.

Perhaps most notably is the fact that everything on the /.data/RACHEL directory has to be installed
during recovery from tar files because that is a separate (large) drive, not the cloned eMMc. The items
are large and so they are on our [ftp server](https://ftp.worldpossible.org/rachel5/recoveryfiles/)
rather than github. The items are:

* .kalite -- kalite-0.17.4.tar.gz
* .kolibri -- kolibri-0.15.12.tar.gz
* moodle -- moodle-3.6.10.tar.gz
* moodle-data -- moodle-data-3.6.10.tar.gz
* mysql -- mysql-10.0.38-MariaDB.tar.gz
* rachel -- contentshell-5.0.0.tar.gz
* rachel/modules -- modules-5.0.0.tar.gz

If you change these you need to make a new tar file, and then put that on the recovery USB so it
can be put back in place at recovery (USB install) time.

## Making the Production USB

Requirements:

* 4GB USB drive
* Downloaded Clonezilla 3.1.3
* Clonzilla image of a working RACHEL5 (as built above)

Here are the steps (on a Mac):

```
# partition and format the USB
# (replace ## with the drive number as shown in df or Disk Utility)
diskutil partitionDisk /dev/disk## MBR FAT32 RACHEL_500P R

# install the Clonzilla system
cd /Volumes/RACHEL_500P
unzip ~/RACHEL5/clonezilla-live-3.1.3-16-i686.zip -d .

# create some directories
touch .metadata_never_index # stops Mac's spotlight indexing
mkdir LOG INSTRUCTIONS
mkdir -p OPTIONS/ENABLED
touch OPTIONS/ENABLED/00_PRODUCTION.txt
mkdir -p recovery/fs/IMAGE

# get some necessary files
git clone https://github.com/worldpossible/RACHEL5.git ~/RACHEL5 
rsync -av rsync://dev.worldpossible.org/rachel5/recoveryfiles/ ~/RACHEL5/recoveryfiles/
rm ~/RACHEL5/recoveryfiles/README.md

# put our stuff in place
mv ~/RACHEL5/recoveryfiles/grub-5.0.0.cfg boot/grub/grub.cfg
mv ~/RACHEL5/recoveryfiles/recovery-5.0.0.sh recovery/recovery.sh
mv ~/RACHEL5/recoveryfiles/recoveryfiles-5.0.0/* recovery/fs/

# this is copying the Clonzilla image directory mentioned above
# -- but making the Clonezilla image is up to you
cp -r ~/Clonezilla_Image_of_RACHEL/* recovery/fs/IMAGE

# tidy up
cd /Volumes
dot_clean -mv RACHEL_500P
rm -rf RACHEL_500P/.Trashes RACHEL_500P/.fseventsd RACHEL_500P/.Spotlight-V100
diskutil unmountDisk RACHEL_500P
```

The USB needs to be set as bootable, which is most easily done on the Linux side,
so put it in the CMAL150 and do the following:

XXX this may not be needed? Creating the disk with an MBR may automatically bootable?

```
# i needed to add this (should add on the RACHEL img)
apt install mtools
# check mount point
cd /media/root/RACHEL_500P/utils/linux
bash makeboot.sh /dev/sdb1
# hit "y" a bunch of times
umount /dev/sdb1
```

Lastly, you bring the USB back to the Mac and do this:

```
diskutil unmountDisk /dev/disk##
sudo bash
dd bs=1m if=/dev/rdisk# of=RACHEL_500P.img conv=sync
gzip ~/RACHEL5/RACHEL_500P.img
```

And that should be it.

NOTE: I was unable to create a bootable USB when trying to use a partition size
smaller than the USB size -- that is, the following did not work:

```diskutil partitionDisk /dev/disk## MBR FAT32 RACHEL_500P 4G . UNUSED R```

Instead I just used a physical 4GB USB drive.

## Making the Recovery USB

Note that if you want to do a "recovery" version instead of the "production"
version described above, you would not create the "00_PRODUCTION.txt" file in OPTIONS/ENABLED
but instead:

```touch OPTIONS/01_CHECK_DRIVE.txt OPTIONS/02_RESET_DRIVE.txt```

We also take the extra effort to hide all
the directories under Windows except INSTRUCTIONS, LOGS, and OPTIONS. You can do
this on a Mac using `chflags hidden FILENAME` and `chflags nohidden FILENAME`. You
can also check the hidden status from the command line with `ls -lO` (that's a capital O).

## Disk Imaging on Mac

### Make a disk image from the USB
```
diskutil unmountDisk /Volumes/YOUR_USB_NAME
# the above command will tell you the disk# wich you must insert below
sudo time dd bs=1m if=/dev/rdisk# of=RACHEL_500P.img conv=sync
```

### Make a USB from the disk image
```
diskutil unmountDisk /Volumes/YOUR_USB_NAME
# the above command will tell you the disk# wich you must insert below
sudo time dd bs=1m if=RACHEL_500P.img of=/dev/rdisk# conv=sync
```

### Version Changes

* v5.0.0 - initial working/shipping CMAL150 version
* v5.1.0 - update PHP 7.0 -> 7.4, include IMathAS tables in MySQL
* v5.1.1 - fix contenthub upload permissions, fix duplicate startup.sh in rc.local
* v5.1.2 - fix broken roundcube from v5.1.0 PHP upgrade

## Afterhoughts / TODOs

Here are some things I considered while making the USB

After delivering a RC (release candidate) there were a few items that needed to be changed.
First, I discovered that /etc/rachel/install/firstboot.py differs between recovery and production USB.
Namely, the production USB version of firstboot.py includes the code to connect to the production server.
Both versions are now included in my recoveryfiles-5.0.0 which needs to get checked in here eventually.

Do we need a better way to manage versioning numbers in recovery.sh, /etc/... contentshell, etc.

Some modules need to be updated to understand latest kiwix: kn-wikipedia

Some modules should be indexed and made into a searchable zim module: en-w3schools

Some possible tweaks:

Turn it in :
* make teacher login submit when you hit enter on password
* no confirm on delete?

File Share :
* no way to delete files? 
* no security for uploading?
* combine with Turn it in? Or not (but improve?)
* or just lose this module?

Datapost :
* "Register" uses admin/common.php for auth screen, but logo is broken because the path is relative and the dir is different (this is hardcoded in common.php authorized()

emule service doesn't show up with service --status-all but it is running fine if you do service emule status
-- ok, this is because emule.service is in /etc/systemd/system (systemd) and is not an /etc/init.d (sysvinit) script

we should add the rc.local changes in recovery.sh to the image

we should add the MOTD stuff in recovery.sh to the image

we can improve these goaccess stats by configuring it to ignore javascript, css, and such

we should look into ```kiwix-serve --verbose``` which gives "a few logs" ... enough to provide stats? that would be nice.

The admin portal (port 8080) runs on uhttpd (migrate to nginx?)

What sends logs via datapost?
* the "logs" user created by datapost -- su to logs, crontab -e to see the cron entry


To reduce en-datapost size:

```
ffmpeg -i en-datapost/content/video/about_datapost.mp4 en-datapost/content/video/about_datapost.small.mp4
mv en-datapost/content/video/about_datapost.small.mp4 en-datapost/content/video/about_datapost.mp4
```

To reduce en-moodle size:

```
for i in en-moodle/vids/*.mp4; do ffmpeg -i "$i" "${i%.*}.small.mp4"; done
for i in en-moodle/vids/*.small.mp4; do mv "$i" "${i%.*.*}.mp4"; done
# fix a typo
en-moodle/vids/25\ Forum\ 3\ .1.mp4 en-moodle/vids/25\ Forum\ 3.1.mp4
sed -i'' -e '/25 Forum/s/3 .1/3.1/' en-moodle/vids/index.html
```

To reduce en-local_content size:
```
ffmpeg -i en-local_content/intro.mp4 en-local_content/intro.small.mp4
mv en-local_content/intro.small.mp4 en-local_content/intro.mp4
# remove cruft
rm en-local_content/CAP3_old.png 
```

The above size removal items *were* included on RACHEL_500P -- but I did not change the modules on our server
so if they get reinstalled or the USB gets recreated you'll get another 289M of stuff

There is some confusion/mess with `/media` where the CAP1 & CAP2 mounted the big drive, and `/.data`
where the CMAL100 and CMAL150 mount the big drive. This should be cleaned up. Right now there's some duplicated/unused
directories in there and it's not always clear which one is actually being used.
