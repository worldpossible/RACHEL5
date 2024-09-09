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

# The Build Process

Starting with a bare CMAL 150 as provided by ECS (or a cloned reinstall of same):

## Initial Setup and Conveniences

```bash
ssh cap@192.168.x.x
sudo bash

# manually add line "Defaults always_set_home"
visudo [...]

# make vi a bit nicer
cat >> /root/.vimrc<< EOF
set softtabstop=4 shiftwidth=4 expandtab
set vb
set encoding=utf-8
set fileencoding=utf-8
EOF

# allow root login
sed -i '/PermitRootLogin/ s/prohibit-password/yes/' /etc/ssh/sshd_config




```
