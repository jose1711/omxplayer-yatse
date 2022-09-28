# omxplayer-yatse

## Trivia

Kodi performance on my Pi Zero was never great but with the most conservative settings it at least worked. But when both LibreELEC and OSMC stopped working as OpenMAX was dropped from Kodi I started to look around for alternatives.

Unfortunately there really aren't that many. Omxplayer got deprecated (and is removed from Rapsbian repository) and VLC is simply too slow.

Another option was to stick to old Kodi release but all I really needed was local files playback so I got the idea of using:
  * `vifm` for directory structure navigation
  * `omxplayer` for playback (despite the warning it still works and is included in Void Linux which is a distribution that is actively maintained)

Being a happy user of `yatse` Kodi remote I tried to extend the idea with controlling the combination using my smartphone. And since `omxplayer` is able to talk through DBus this repository was born.

## What is this?

This repository describes steps to turn your Pi Zero (original Pi Zero, not 2W) into a minimalistic and snappy video player that:

  * boots into terminal and provides a file-based view on your video collection
  * allows one to navigate and control playback of videos using local keyboard, `yatse` or via SSH connection

## What to expect?

* video files supported by OMXPlayer work
* sound is routed through HDMI
* every 15 seconds actual playback position is stored and user gets a prompt if the playback is resumed in future
* basic `yatse` controls work (seeking, volume, stop/pause, navigation)
* reboot/shutdown initiated from `yatse` does its job

## What to *not* expect?

* library management (there is no metadata parsing, images, links etc)
* other fancy Kodi features like addons, playlists, sleep timer, image slideshows, games, weather forecast, IPTV, screensaver..

## Instructions

* get at least a 16GB microSD card and make sure it is empty (or contains data you no longer need)
* download the latest `void-rpi-*.img.xz` from https://repo-default.voidlinux.org/live/current/
* follow Installation section of Void Handbook (https://docs.voidlinux.org/installation/index.html)
* boot system (default password for `root` is `voidlinux`) and change the password using `passwd` command
  * configure timezone
  ```
  ln -sf /usr/share/zoneinfo/<timezone> /etc/localtime
  ```
* configure network as per https://docs.voidlinux.org/config/network/index.html
  ```
  ip link
  # wlan adapter name shows up at wlan0 hence we'll use it in the command below
  wpa_passphrase 'MYSSID' 'MYPASS' >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
  ln -s /etc/sv/wpa_supplicant /etc/runit/runsvdir/default/
  # wait a minute
  ip a
  # ip address should appear and device should also be available through SSH
  ```
* perform a system update
  ```
  xbps-install -yu xbps
  xbps-install -Suy
  ```
* reboot
* install git
  ```
  xbps-install -y git
  ```
* clone this repository
  ```
  git clone https://github.com/jose1711/omxplayer-yatse
  cd omxplayer-yatse/
  ```
* edit `deploy.sh` - set username based on your preference
* run `deploy.sh`
  ```
  cd omxplayer-yatse
  ./deploy.sh
  # type new password for user when prompted
  ```
* shutdown, remove SD card and expand partition using GParted, then reinsert into Pi and boot it again
* prohibit `root` login via SSH
  ```
  # login via ssh
  sudo su -
  sed -i '/PermitRootLogin/d' /etc/ssh/sshd_config
  echo 'PermitRootLogin no' >> /etc/ssh/sshd_config
  sv restart sshd
  ```
* install [yatse](https://www.yatse.tv/) on your smartphone and add host manually, port: 8080
  * ignore missing Event server warning (you may need to hold button when adding host)

## Usage

  | yatse action    | in filebrowser       | during playback    |
  | --------------- | -------------------- | ------------------ |
  | up/down         | navigation           | seek (1m)          |
  | left/right      | navigation           | seek (10m)         |
  | OK              | change dir/open file | show info          |
  | OK (held)       | context menu*        | -                  |
  | volume +/-      | -                    | volume +/-         |
  | play/pause      | -                    | play/pause         |
  | stop            | -                    | stop               |
  | rewind/fforward | -                    | playback speed +/- |

\* context menu allows user to set different aspect mode.

## Performance

Fresh install is taking approx. 860 MB. In case you need to free up some space, here are possibly candidates for deletion:
  * `/var/cache/xbps/` - 160 MB
  * `/usr/share/locale` - 70 MB
  * `/usr/share/man` - 40 MB

Startup times:
  - from powering on to first ping reply: 28 seconds
  - from powering on til moment when `yatse` remote starts responding: 45 seconds

CPU/memory usage:
  * while idle: 5-20 % (depending on whether `yatse` is sending requests), 55 MB
  * during playback: 25-50 %, 75 MB
