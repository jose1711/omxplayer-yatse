#!/bin/bash
# set -x
# install prerequisites
user="CONFIGUREME"

if [ $(id -u) -ne 0 ]
then
  echo "Rerun the script as root"
  exit 1
fi

if [ "${user}" = "CONFIGUREME" ]
then
  echo "Be sure to edit deploy.sh - modify user variable, then rerun"
  exit 1 
fi

# create user if it does not exist already
getent passwd "${user}" >/dev/null 2>&1 || {
  useradd -m "${user}"
  passwd "${user}"
}

usermod -a -G video $user

chsh -s /bin/bash root
chsh -s /bin/bash "${user}"

install -o "${user}" -m755 -d /home/${user}/videos
ln -sf /media /home/${user}/videos/media

xbps-install -yu tmux \
                 omxplayer \
                 udevil \
                 vifm \
                 vim \
                 python3-Flask \
                 python3-requests \
                 python3-dbus \
                 terminus-font

# configure autologin
# (https://dudik.github.io/posts/void-linux-agetty-login-without-username-just-password.html)
cp -R /etc/sv/agetty-tty1 /etc/sv/agetty-autologin-tty1
cat > /etc/sv/agetty-autologin-tty1/conf <<HERE
GETTY_ARGS="--autologin ${user} --noclear"
BAUD_RATE=38400
TERM_NAME=linux
HERE
rm /var/service/agetty-tty1 2>/dev/null
ln -sf /etc/sv/agetty-autologin-tty1 /var/service

# copy user files
install -o "${user}" -Dm755 dist/.bashrc /home/${user}/.bashrc
install -o "${user}" -Dm644 dist/vifmrc /home/${user}/.vifm/vifmrc
install -o "${user}" -Dm755 dist/service-run /home/${user}/service/omxplayer-yatse/run
install -o "${user}" -d /home/${user}/service/omxplayer-yatse
install -o "${user}" -d /home/${user}/vifm
install -o "${user}" -Dm755 dist/omxplayer.sh /home/${user}/bin/omxplayer.sh
install -o "${user}" -Dm755 dist/omxplayer-yatse.py /home/${user}/bin/omxplayer-yatse.py
install -o "${user}" -Dm755 dist/mount_all.sh /home/${user}/bin/mount_all.sh
sed -i "s/{{user}}/${user}/" /home/${user}/bin/mount_all.sh

# add to sudoers
cat >/etc/sudoers.d/${user}_nopasswd <<HERE
${user} ALL=(ALL:ALL) NOPASSWD: ALL
HERE

grep -q bin/mount_all.sh /etc/rc.local || {
  echo "~${user}/bin/mount_all.sh" >> /etc/rc.local
}

# configure per-user services
# https://docs.voidlinux.org/config/services/user-services.html
install -Dm755 dist/run /etc/sv/runsvdir-${user}/run
sed -i "s/{{user}}/${user}/" /etc/sv/runsvdir-${user}/run
ln -sf "/etc/sv/runsvdir-${user}" /var/service

# set terminal font
sed -i 's/^ *FONT=.*/FONT=ter-u32n/' /etc/rc.conf
egrep -q '^ *FONT=ter-u32n' /etc/rc.conf || {
  echo 'FONT=ter-u32n' >> /etc/rc.conf
}

# clear package cache 
xbps-remove -Oo
