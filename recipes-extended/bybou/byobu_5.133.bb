DESCRIPTION = "Byobu terminal multiplexer"
HOMEPAGE = "http://byobu.org/"
SECTION = "console/utils"

RDEPENDS:byobu = "bash glibc-utils perl tmux"

LICENSE = "GPLv3"
LIC_FILES_CHKSUM = "file://COPYING;md5=f27defe1e96c2e1ecd4e0c9be8967949"

SRC_URI = "https://launchpad.net/byobu/trunk/5.133/+download/byobu_5.133.orig.tar.gz"
SRC_URI[md5sum] = "0ff03f3795cc08aae50c1ab117c03261"

inherit autotools

do_install:append() {
	rm -rf ${D}${datadir}/dbus-1
}
