#!/bin/bash

first_boot=/etc/rachel/install/firstboot.py
done=/etc/rachel/install/firstboot.done

if [ -f $first_boot ]; then
  sleep 40
  echo $(date) - "Running firstboot script"
  sudo python3 $first_boot
  mv $first_boot $done
fi

exit 0
