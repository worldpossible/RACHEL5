#!/bin/sh
#
# Copyright World Possible 2024

version="5.0.0"

dir="$(dirname "${BASH_SOURCE[0]}")"
usb_mount="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
emmc_device=/dev/mmcblk0p2
emmc_mount=/mnt/emmc
ssd_device=/dev/sda
ssd_mount=/mnt/ssd
ssd_partition=/dev/sda1
ssd_label="contenthub"
ssd_uuid=99999999-9999-9999-9999-999999999999
recovery_files=$dir/fs

# build log file name
mac=$(cat /sys/class/net/eth0/address | sed 's/:/-/g')
date=$(date +%s) 
usb_log="${usb_mount}/LOGS/recovery_${mac}_${date}.txt"

options_dir=$usb_mount/OPTIONS/ENABLED

function log(){
  err=$1    
  echo -e "RECOVERY: $1" | tee -a $usb_log
}

function check(){
  if [ "${?}" -ne "0" ]; then
    log "FAILED: '${err}'"
    exit 1
  fi
}

function setup_logging(){
  local options=($(basename -a $options_dir/*))
  local emmc_version=$(cat $emmc_mount/etc/rachelinstaller-version) 
  local drive_type=$(cat /sys/block/sda/queue/rotational)

  if [ -e $usb_log ]; then
    echo "Deleting ${usb_log}..."
    rm $usb_log; check
  fi

  log "USB Version: ${version}"
  log "Current Version: ${emmc_version}"
  log "MAC: ${mac}"
  log "Timestamp: ${date}"
  
  if [ $drive_type == '0' ]; then
    log "Drive Type: SSD" 
  else
    log "Drive Type: HDD"
  fi

  for option in "${options[@]}"; do
    log "Option: $option"
  done

  exec 3>&2
  exec 2>> $usb_log
}

function copy_logs(){
  if [ -f /var/log/clonezilla.log ]; then
    log "Copying clonezilla log to USB"
    cp /var/log/clonezilla.log "${usb_mount}/LOGS/${mac}_clonezilla.log"; check
  fi
}

function execute_options(){
  log "==== Checking Options ===="

  if [ -f "$options_dir/00_PASS.txt" ]; then
    local password=$(cat $options_dir/00_PASS.txt)
    
    if [ -z $password ]; then
      set_pass $password
    else
      log "The password option is set, but the file is empty"
    fi
  fi

  if [ -f "$options_dir/00_PRODUCTION.txt" ]; then
    log "Running Production Mode"
    # later functions behave differently so it is not
    # the same is 02_RESET
    ssd_reset
    return
  fi

  if [ -f "$options_dir/01_CHECK_DRIVE.txt" ]; then
    log "Running Drive Check Mode"
    ssd_check
    return
  fi

  if [ -f "$options_dir/02_RESET_DRIVE.txt" ]; then
    log "Running Drive Reset Mode"
    ssd_reset
    return
  fi
  
  log "Running No Drive mode"
  ssd_fsck
  ssd_mount
  ssd_contenthub
  ssd_unmount
}

function set_pass(){
  log "==== Setting Password ===="

  log "Setting password"
  chroot $emmc_mount /bin/bash -c "echo root:$1 | chpasswd"; check
  
  log "==== Finished Setting Password ===="
}

function emmc_mount(){
  log "==== Running EMMC Config ===="

  if [ ! -d $emmc_mount ]; then
    log "Creating ${emmc_mount}..."
    mkdir $emmc_mount; check
  fi

  log "Mounting ${emmc_device} at ${emmc_mount}..."
  mount $emmc_device $emmc_mount; check

  log "==== Finished Mounting EMMC ===="
}

#-------------------------------------------
# this puts startup.sh, firstboot.py,
# and the installer logs onto the EMMC
#-------------------------------------------
function emmc_config(){
  log "==== Running EMMC Config ===="

  local emmc_log=$emmc_mount/etc/rachel/logs/post-run.txt

  # these aren't on the RACHEL5 image at this point
  # should be, we'll get there...
  log "Making /etc/rachel directories"
  mkdir $emmc_mount/etc/rachel
  mkdir $emmc_mount/etc/rachel/install
  mkdir $emmc_mount/etc/rachel/boot
  mkdir $emmc_mount/etc/rachel/logs
  log "Installing startup.sh"
  cp $recovery_files/startup.sh $emmc_mount/etc/rachel/boot/; check

  if [ -f "$options_dir/NO_FIRSTBOOT.txt" ]; then
    log "Skipping firstboot.py installation"
  elif [ -f "$options_dir/00_PRODUCTION.txt" ]; then
    log "Installing production firstboot.py"
    cp $recovery_files/firstboot.production.py $emmc_mount/etc/rachel/install/firstboot.py; check
  else
    log "Installing standard firstboot.py"
    cp $recovery_files/firstboot.py $emmc_mount/etc/rachel/install/; check
  fi

# we want a nicer MOTD - again, this should be on the image
cat >> $emmc_mount/etc/update-motd.d/00-header << EOF
printf "Welcome to RACHEL-Plus from World Possible \n\n"
printf "RACHEL: \$(cat /etc/rachelinstaller-version) \n"
printf "MAC: \$(cat /sys/class/net/enp2s0/address) \n"
EOF

  # although the emmc has its own version recorded (and logged above)
  # I think it makes sense to synchronize to this script here:
  echo $version > $emmc_mount/etc/rachelinstaller-version

  # firstboot.py changes this, but at that point it's too late
  # because datapost (and others?) have already started with
  # the wrong name
  sed 's/://g' /sys/class/net/eth0/address | cut -c 7-12 > $emmc_mount/etc/hostname

  # we forgot this when making the device -- should be part of the image
  sed -i '/^touch/i bash /etc/rachel/boot/startup.sh &' \
    $emmc_mount/etc/rc.local
  # and we missed this too
  chmod +x $emmc_mount/etc/rc.local

  log "Copying ${usb_log} to ${emmc_log}"
  cp $usb_log $emmc_log; check

  log "Syncing ${emmc_device}"
  sync $emmc_device; check

  log "Unmounting ${emmc_mount}"
  umount $emmc_mount; check

  log "==== Finished running EMMC Config ===="
}

function ssd_fsck(){
  log "==== SSD Filesystem Check ===="

  log "Running filesystem check on ${ssd_partition}..."
  e2fsck -y $ssd_partition

  log "==== Finished SSD Filesystem Check ===="  
}

function ssd_mount(){
  log "==== SSD Mount ===="

  if [ ! -d $ssd_mount ]; then
    log "Creating ${ssd_mount}..."
    mkdir $ssd_mount; check
  fi
  
  log "Mounting ${ssd_partition} as ${ssd_mount}..."
  mount $ssd_partition $ssd_mount; check
  
  log "==== SSD Mount ===="
}

function ssd_unmount(){
  log "Syncing ${ssd_partition}"
  sync $ssd_partition; check
 
  log "Unmounting ${ssd_mount}"
  umount $ssd_mount; check
}

#-------------------------------------------
# this wipes the SSD and reinstalls everything
#-------------------------------------------
function ssd_reset(){
  log "==== Configuring SSD ===="

  log "Clearing ${ssd_device}..."
  sgdisk --zap-all --clear $ssd_device; check
  
  log "Creating new partition on ${ssd_device}..."
  sgdisk --largest-new=1 $ssd_device; check

  log "Creating new filesystem with label and ${ssd_uuid} on ${ssd_partition}..."
  yes | mke2fs -t ext4 -L $ssd_label -U $ssd_uuid $ssd_partition; check
  
  log "Enabling writeback journal..."
  tune2fs -o journal_data_writeback $ssd_partition; check
  
  log "Turning off full journaling..."
  tune2fs -O ^has_journal $ssd_partition; check
  
  ssd_mount
  
  local rachel_dir=$ssd_mount/RACHEL

  if [ ! -d $rachel_dir ]; then
    log "Creating ${rachel_dir}..."
    mkdir $rachel_dir; check

    log "Setting permissions on ${rachel_dir}..."
    chmod 0755 $rachel_dir; check
  fi  

  sdd_contentshell
  ssd_contenthub
  ssd_kolibri
  ssd_kalite
  ssd_moodle
  ssd_unmount

  log "==== Finished configuring the SSD ===="
}

#-------------------------------------------
# this installs everything *without* wiping the SSD
#-------------------------------------------
function ssd_check(){
  log "==== SSD Check ===="
  ssd_mount
  ssd_uuid
  sdd_contentshell
  ssd_contenthub
  ssd_kolibri
  ssd_kalite
  ssd_moodle
  ssd_unmount
  log "==== Finished SSD Check ===="
}

function ssd_uuid(){
  log "==== SSD UUID Check ===="

  log "Getting SSD UUID..."
  local current_uuid=$(blkid -o value -s UUID $ssd_partition)

  if [ $current_uuid == $ssd_uuid ]; then
    log "Found SSD with UUID ${ssd_uuid}"
  else
    log "SSD UUID ${current_uuid} is not ${ssd_uuid}. Updating UUID"
    log "Unmounting ${ssd_partition} to change UUID..."
    umount $ssd_partition; check

    log "FSCKing ${ssd_partition} to change UUID..."
    e2fsck -y $ssd_partition; check

    log "Setting SSD UUID to ${ssd_uuid}..."
    tune2fs /dev/sda1 -U $ssd_uuid; check

    log "Remounting ${ssd_partition} as ${ssd_mount}"
    mount $ssd_partition $ssd_mount; check
  fi

  log "==== Finished SSD UUID Check ===="
}

#-------------------------------------------
# this is the RACHEL contentshell
#-------------------------------------------
function sdd_contentshell(){
  log "==== Content Shell Check ===="

  local rachel_dir=$ssd_mount/RACHEL
  local cshell_dir=$rachel_dir/rachel
  local modules=$recovery_files/modules-5.0.0.tar.gz
  local shell_ver=v5.0.0
  local tar_file=$recovery_files/contentshell-5.0.0.tar.gz

  if [ ! -d $cshell_dir ]; then
    log "Missing ${cshell_dir}. Installing ${tar_file}..."
    tar -xf $tar_file -C $rachel_dir; check

    if [ -f $modules ]; then
      log "Installing modules from ${modules}..."
      tar -xf $modules -C $cshell_dir; check
    fi

    log "==== Finished Content Shell Check ===="
    return
  fi

  local version_file=$rachel_dir/rachel/admin/version.php
  local content=$(cat $version_file)
  local version=$(echo "$content" | grep -oP 'id="cur_contentshell"[^>]*>\K[^<]+')

  if [ "$version" = "$shell_ver" ]; then
    log "Found version=${version}. No content shell upgrade required"
    return
  fi
  
  log "Mismatched version ${version} found. Upgrading to ${shell_ver}"

  log "Installing ${tar_file} to ${rachel_dir}..."
  tar -xf $tar_file --exclude="admin/admin.sqlite" --exclude="modules" -C $rachel_dir; check
 
  local zims=$(find $rachel_dir/rachel/modules -type f -name "*.zima" | wc -l)

  if [ "$zims" != "0" ]; then
    log "Outdated Kiwix modules detected. You will need to update some your content for use with this version"
  fi

  log "==== Finished Content Shell Check ===="
}


#-------------------------------------------
# this is the Intel contenthub
#-------------------------------------------
function ssd_contenthub(){
  log "==== Content Hub Check ===="

  # on RACHEL 5, the contenthub stuff is on the emmc
  # and only the upload directory needs to be created
  # if missing

  local uploaded_dir=$ssd_mount/uploaded

  if [ ! -d $uploaded_dir ]; then
    log "Missing ${uploaded_dir}. Creating..."
    mkdir $uploaded_dir; check
    
    log "Setting permissions on ${uploaded_dir}..."
    chmod 0755 $uploaded_dir; check
    
    log "Setting ownership on ${uploaded_dir}"
    chown 33:33 $uploaded_dir -R; check
  else 
    log "Found ${uploaded_dir}. Continuing..."
  fi

  log "==== Finished Content Hub Check ===="
}

function ssd_kolibri(){
  log "==== Kolibri Check ===="

  local rachel_dir=$ssd_mount/RACHEL
  local kolibri_dir=$rachel_dir/.kolibri
  local tar_file=$recovery_files/kolibri-0.15.12.tar.gz
  
  if [ ! -d $kolibri_dir ]; then
    log "Missing ${kolibri_dir}. Installing ${tar_file}..."
    tar -xf $tar_file -C $rachel_dir; check
  else
    log "Found ${kolibri_dir}. Continuing..."
  fi

  log "==== Finished Kolibri Check ===="
}

function ssd_kalite(){
  log "==== KA-Lite Check ===="

  local rachel_dir=$ssd_mount/RACHEL
  local kalite_dir=$rachel_dir/.kalite
  local tar_file=$recovery_files/kalite-0.17.4.tar.gz

  if [ ! -d $kalite_dir ]; then
    log "Missing ${kalite_dir}. Installing ${tar_file}..."
    tar -xf $tar_file -C $rachel_dir; check
  else
    log "Found ${kalite_dir}. Continuing..."
  fi

  log "==== Finished KA-Lite Check ===="
}

function ssd_moodle(){
  log "==== Moodle Check ===="

  local rachel_dir=$ssd_mount/RACHEL
  local mysql_dir=$rachel_dir/mysql
  local moodle_dir=$rachel_dir/moodle
  local moodle_data_dir=$rachel_dir/moodle-data
  local moodle_symlink=$rachel_dir/rachel/moodle
  local moodle_symlink_path=/media/RACHEL/moodle
  local tar_file_moodle=$recovery_files/moodle-3.6.10.tar.gz
  local tar_file_moodle_data=$recovery_files/moodle-data-3.6.10.tar.gz
  local tar_file_mysql=$recovery_files/mysql-10.0.38-MariaDB.tar.gz
  local install=0

  if [ ! -d $mysql_dir ]; then
    log "Missing ${mysql_dir}"
    install=1
  fi

  if [ ! -d $moodle_dir ]; then
    log "Missing ${moodle_dir}"
    install=1
  fi

  if [ ! -d $moodle_data_dir ]; then
    log "Missing ${moodle_data_dir}"
    install=1
  fi

  if [ ! -L $moodle_symlink ]; then
    log "Missing ${moodle_symlink}. Creating..."
    ln -s $moodle_symlink_path $moodle_symlink; check
  fi

  if [ $install -eq 1 ]; then
    log "Installing ${tar_file}..."
    tar -xf $tar_file_moodle      -C $rachel_dir; check
    tar -xf $tar_file_moodle_data -C $rachel_dir; check
    tar -xf $tar_file_mysql       -C $rachel_dir; check
  else
    log "Moodle installation found. Continuing..."
  fi

  log "==== Finished Moodle Check ===="
}

echo "==== POST RUN: recoverh.sh ===="
emmc_mount
setup_logging
execute_options
copy_logs
emmc_config
exec 2>&3
echo "==== POST RUN COMPLETE ===="

poweroff
exit 0;
