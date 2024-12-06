#!/bin/bash
#-------------------------------------------
# This script is used to refresh the kiwix library upon restart to
# include everything in the rachel modules directory. It is used
# as part of rachelStartup.sh and various scripts in contentshell
#
# Authors: Sam Kinch <sam@hackersforcharity.org>     (bash version)
#          Jonathan Field <jfield@worldpossible.org> (original perl version)
#                                                    (& bash version tweaks)
#          James Kainer <james@worldpossible.org>    (Updates for 3.1.2)
# Date: 2021-07-07
#-------------------------------------------

# figure out what our system is (and thus the modules directory)
if [[ -e /media/RACHEL/rachel ]]; then
    rachelDir=/media/RACHEL/rachel
elif [[ -e /srv/rachel/www ]]; then
    rachelDir=/srv/rachel/www
else
    echo "Unknown system; exiting.";
fi

library="/var/kiwix/library.xml"

# Remove existing library
rm -f $library

# Create tmp file for working on our zim file list
tmp=`mktemp`

# Find all the zim files in the modules directoy
ls $rachelDir/modules/*/data/content/*.zim* 2>/dev/null | sed 's/ /\n/g' > $tmp

# Remove extra files - we only need the first (.zim or .zimaa)
sed -i '/zima[^a]/d' $tmp

# Remove modules that are marked hidden on main menu
for d in $(sqlite3 $rachelDir/admin/admin.sqlite 'select moddir from modules where hidden = 1'); do
    sed -i '/\/'$d'\//d' $tmp
done

# build the library file by adding each zim found
for i in $(cat $tmp); do
    if [[ $? -ge 1 ]]; then echo "No zims found."; fi
    cmd="/var/kiwix/bin/kiwix-manage $library add $i"
    moddir="$(echo $i | cut -d'/' -f1-6)"
    $cmd 2>/dev/null
    if [[ $? -ge 1 ]]; then
        echo "Couldn't add $zim to library";
    else
        found=1
    fi
done

# Remove that temp file
rm -f $tmp

# if there were no zims, we put in an "empty" zim so that
# kiwix can at least show it's running and working
if [[ ! $found ]]; then
    /var/kiwix/bin/kiwix-manage $library add /var/kiwix/empty.zim
fi

# Restart Kiwix
killall /var/kiwix/bin/kiwix-serve
/var/kiwix/bin/kiwix-serve --daemon --port=82 --library $library > /dev/null
