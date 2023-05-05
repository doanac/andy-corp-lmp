# SRCREV = "45dd07dae09159d032e6eafdb85cae6c02900175"
#GO_IMPORT = "github.com/doanac/fioconfig"
#GO_IMPORT_PROTO ?= "https"
#SRC_URI = "git://${GO_IMPORT};protocol=${GO_IMPORT_PROTO};branch=rotate-fixes \
#	file://fioconfig.service \
#	file://fioconfig.path \
#	file://fioconfig-extract.service \
#"
#SRCREV = "6cfa9d26d5970726bce196a3eb7791d7285e7762"

#do_install:append() {
#	install -d ${D}${systemd_system_unitdir}
#	install -m 0644 ${WORKDIR}/fioconfig.service ${D}${systemd_system_unitdir}/
#	install -m 0644 ${WORKDIR}/fioconfig.path ${D}${systemd_system_unitdir}/
#	install -m 0644 ${WORKDIR}/fioconfig-extract.service ${D}${systemd_system_unitdir}/
#	install -d ${D}${datadir}/fioconfig/handlers
#	install -m 0755 ${S}/src/${GO_IMPORT}/contrib/aktualizr-toml-update ${D}${datadir}/fioconfig/handlers
#	install -m 0755 ${S}/src/${GO_IMPORT}/contrib/factory-config-vpn ${D}${datadir}/fioconfig/handlers
#	install -m 0755 ${S}/src/${GO_IMPORT}/contrib/renew-client-cert ${D}${datadir}/fioconfig/handlers
#}
