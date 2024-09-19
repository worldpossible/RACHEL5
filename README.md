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
# XXX for git clone to work you have to put your github ssh keys in /root/.ssh
git clone git@github.com:worldpossible/internetdelivered-emule-webservice.git emulewebservice
cd emulewebservice/bin/
./install.sh
# wait several minutes

# XXX we should revert datapost code to not change this because we have to change it back:
sed -i '/php7.1-fpm.sock/ s/php7.1/php7.0/' /etc/nginx/sites-available/rachel.nginx.conf
service nginx restart
# the above happens when install_emulewebserver.sh copies over config/nginx/sites-available/rachel.nginx.conf

# XXX we should also stop datapost from inserting the webmail link because we end up with two:
sed -i '0,/WEBMAIL/{/WEBMAIL/d}' /media/RACHEL/rachel/index.php
# the above takes place in /opt/emulewebservice/bin/install_emulewebserver.sh

# At this point webmail should work, but we have no module to show
# to get that, we install some default modules:
rsync -av "jfield@192.168.x.x:~/RACHEL5/modules-4.1.2/" /media/RACHEL/rachel/modules

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
service start emule

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
#  "there os a setting in the Roundcube config file - create_default_folders -
#  which makes it auto create defailt folders on first login."

# sending a message internally worked
# sending a message remotely worked
# sending a message remote-to-rachel did not work -- android did not pick up the bundle
# i think i need to register the device
# XXX: on the register link on RACHEL there is a missing icon
# XXX: no indication which fields are required (oh, it's all ... link to a gps tool? link to a default or choosable icon?)
# XXX: all data lost if you submit with missing info
# XXX: when done, you get a back button that takes you to the same blank form
# Note: admin password: grep admin /opt/emulewebservice/node/datapost-admin/app.js
# XXX: no way to see registration data? can you change by overwriting?

# android app (i got it from datapost.site, not RACHEL device):
# XXX: initial page doesn't inclue sync buttons (shows profile) - you have to go to menu > home
# XXX: even after sending a reply from my gmail address, the app says there is "no bundle to pick up"
# XXX: Romeo says there may be problems with the server at the moment, so moving on
```

### Install Kolibri

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

### Install KA-Lite

```
# needed for dpkg installation
apt install -y unzip

dpkg -i /root/files/ka-lite_0.17.4-0ubuntu2_all.deb
    # run at startup? yes
    # which user? root
    # confirm? ok

# install contentpacks (everything but videos, I believe) 
kalite manage retrievecontentpack local en /root/files/contentpacks/en-0.17-fixed.zip
kalite manage retrievecontentpack local es /root/files/contentpacks/es.zip
kalite manage retrievecontentpack local fr /root/files/contentpacks/fr.zip
kalite manage retrievecontentpack local hi /root/files/contentpacks/hi.zip
kalite manage retrievecontentpack local pt-BR /root/files/contentpacks/pt-BR.zip
kalite manage retrievecontentpack local pt-PT /root/files/contentpacks/pt-PT.zip
kalite manage retrievecontentpack local sw /root/files/contentpacks/sw.zip

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


### Install Kiwix

```
# install from web
cd /root
wget https://download.kiwix.org/release/kiwix-tools/kiwix-tools_linux-x86_64.tar.gz
tar -xzvf kiwix-tools_linux-x86_64.tar.gz
mkdir /var/kiwix /var/kiwix/bin
mv /root/kiwix-tools_linux-x86_64-3.7.0-2/* /var/kiwix/bin

# (updated admin/version.php to use kiwix-serve -V)
# XXX also needed to do this becasue some modules check the old kiwix version
/var/kiwix/bin/kiwix-serve -V | grep kiwix-tools | cut -d ' ' -f2 > /etc/kiwix-version

# XXX I guess there's been a change where kiwix doesn't need a separate index file?
# so we use a newer version of rachelKiwixStart.sh from kn-wikipedia (I'm sure it's elsewhere as well :)
cp /root/files/rachelKiwixStart.sh /var/kiwix/

# this allows kiwix to run and show an informative page even if there
# are no modules installed
cp /root/files/empty.zim /var/kiwix/

# this is also changed (and available in kn-wikipedia) to point to a better location for the startup script
cp /root/files/init-kiwix-service /etc/init.d/kiwix
systemctl daemon-reload
chmod +x /etc/init.d/kiwix 
update-rc.d kiwix defaults
service kiwix start

# XXX given how much kiwix has changed, there may be some modules that need to be updated? 

```

### Install Moodle

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
cat /root/files/mysql-additions.txt >> /etc/mysql/my.cnf

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

# ok, now install moodle itself (mostly just php)
cd /root
wget https://download.moodle.org/download.php/direct/stable36/moodle-3.6.10.tgz
tar -xzvf moodle-3.6.10.tgz
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

# XXX do we want the en-moodle module installed by default?

```

### Misc Configuration

```
# this is used by the recovery USB in the recover.sh script
# -- use whatever version you're on, obviously
echo "v5.0.0" > /etc/rachelinstaller-version

# I can't find versioning in the actual emule code, but
# [this page](https://github.com/worldpossible/datapost-field-util)
# claims it is v0.2.1 so we'll go with that until there's better information
echo "v0.2.1" > /etc/datapost-version

# these are slow, so we just save them
kolibri --version | cut -d " " -f 3 > /etc/kolibri-version
kalite --version > /etc/kalite-version

# lots of tweaks were done to contentshell to fix minor differences with between
# the CMAL100/CMAL150 but those will be checked in to github as v5.0.0

# install php stemming (what uses this now? the modules i checked included their own stemmer?)
apt -y install php7.0-dev
yes yes | pecl install -O stem-2.0.0.tgz
echo extension=stem.so > /etc/php/7.0/mods-available/stem.ini
ln -s /etc/php/7.0/mods-available/stem.ini /etc/php/7.0/cli/conf.d/30-stem.ini
ln -s /etc/php/7.0/mods-available/stem.ini /etc/php/7.0/fpm/conf.d/30-stem.ini

# not sure it matters in practice, but we should be running in server mode, not GUI mode
systemctl set-default multi-user.target
# `runlevel` doesn't work so check with
systemctl get-default

# we had sporading issues on the CMAL100 with /.data (and thus /media/RACHEL) not
# being mounted quickly enough during startup so that some services would fail to
# start -- we patched the init scripts to wait for the mount. I don't know if the
# CMAL150 has the same issue (I haven't seen it), but to be safe we include the
# same patches here. Patches created with: diff -Naur file.orig file.edit
patch /etc/init.d/ka-lite -i ka-lite.init.patch
patch /etc/init.d/kolibri -i kolibri.init.patch
patch /etc/init.d/mysql -i mysql.init.patch
# kiwix already has the wait code in kiwix-init-service

```


### Cleanup

Some of this is helpful, some could probably be omitted

```
# Get rid of leftover install files
apt clean

# these should be moved up to their respective install sections
rm -rf /root/goaccess-*
rm -rf /root/moodle-*
rm -rf /root/kiwix-tools*

rm -rf /root/files
rm -rf /.Trash-0
rm -rf /tmp/firstboot.log
rm -rf /tmp/sortmods*
rm -rf /tmp/do_tasks.log
rm /srv/.git* # this was a one-time thing

# sanitize logs
find /var/log -name '*.gz' -delete
find /var/log -name '*.1' -delete
for i in $(find /var/log -type f); do cat /dev/null > $i; done

# sanitize history
:> /root/.bash_history
:> /root/.viminfo
rm /root/.mysql_history
rm /root/.wget-hsts
:> /home/cap/.bash_history
:> /home/cap/.viminfo

# remove any extraneous auto-installer files
rm /root/rachel-scripts/files/rachel-autoinstall.*

# if you want to clear out freespace (makes zipped filesystem smaller)
cat /dev/zero > /root/zerofile; rm /root/zerofile


```

### Fix Size

Before expanding the USB size as described below, I tried shrinking some videos in the included
modules. From the modules directory (on my Mac):

```
tar -xzvf modules-5.0.0.tar.gz
cd modules

ffmpeg -i en-datapost/content/video/about_datapost.mp4 en-datapost/content/video/about_datapost.small.mp4
mv en-datapost/content/video/about_datapost.small.mp4 en-datapost/content/video/about_datapost.mp4

for i in en-moodle/vids/*.mp4; do ffmpeg -i "$i" "${i%.*}.small.mp4"; done
for i in en-moodle/vids/*.small.mp4; do mv "$i" "${i%.*.*}.mp4"; done
# fix a typo
en-moodle/vids/25\ Forum\ 3\ .1.mp4 en-moodle/vids/25\ Forum\ 3.1.mp4
sed -i'' -e '/25 Forum/s/3 .1/3.1/' en-moodle/vids/index.html

ffmpeg -i en-local_content/intro.mp4 en-local_content/intro.small.mp4
mv en-local_content/intro.small.mp4 en-local_content/intro.mp4
# remove cruft
rm en-local_content/CAP3_old.png 

cd ..
tar --no-xattrs -czvf modules-5.0.0b.tar.gz modules

# if all went well
mv modules-5.0.0b.tar.gz modules-5.0.0.tar.gz
```

The above saved ~289M on the gz file. Not critical, but why not. 

### Making the USB

The 5.x.x USB (~2.6GB) is larger than the 4.x.x (~2.3GB). Assuming we are building
and imaging a drive larger than that, you can set up the USB as so on Mac OS:
(replace diskXX with your USB's number)

```diskutil partitionDisk /dev/diskXX MBR FAT32 RACHEL_500P 3.8G FREE UNUSED R```

This creates a partition which should have plenty for RACHEL 5 and logs, and will
fit on any 4GB USB.

After copying clonezilla 3.1.3 files, copying everything into recovery, adding OPTIONS, LOG,
and INSTRUCTIONS directories, and installing our grub.cfg, I ran:

```dot_clean -mv /Volumes/RACHEL_500P```

Then I moved to Linux to set it as bootable. However, mtools was needed -- so:

```apt install mtools```

then:

```
cd /media/root/RACHEL_500P/utils/linux
bash makeboot.sh /dev/sdb1
```

Hit "y" a bunch of times and you should be good.


Later when when you want to make a USB from an image on the mac you can do this:

```sudo asr restore --source RACHEL_500P.dmg --target /Volumes/RACHEL_500P --erase```

### Research

```
# put these in place
/etc/rachelinstaller-version
/etc/datapost-version

better way to manage versioning numbers in recovery.sh (encodes 

apache2 not running (ok? do we need nginx hub.conf?)
looks like apache2 is gone from rachel 4 (good? one webserver is plenty, thank you)

no longer use /root/rachel-scripts/rachelStartup.sh ... is that OK?
now use /etc/rachel/boot/ ... but it just does the firstboot.sh stuff

are we using /var/kiwix/rachelKiwixStart.sh or /root/rachel-scripts/rachelKiwixStart.sh?
seems the first one is in the /etc/rc*.d files? is the second a boondoggle?


# some modules need to be updated to understand latest kiwix:
kn-wikipedia

# some modules should be indexed and made into a searchable zim module:
en-w3schools

# possible tweaks
Turn it in : make teacher login submit when you hit enter on password
           : no confirm on delete?

File Share : no way to delete files? 
           : no security for uploading?
           : combine with Turn it in? Or not (but improve?)
           : or just lose this module?

Datapost   : "Register" uses admin/common.php for auth screen, but logo is broken
             because the path is relative and the dir is different (this is hardcoded
             in common.php authorized()

emule service doesn't show up with service --status-all but it is running fine if you do service emule status

we should add the rc.local changes to the image and remove it from recovery.sh

nicer MOTD on RACHEL 4

"logs" user created by datapost -- su to logs, crontab -e to see the cron entry

```
