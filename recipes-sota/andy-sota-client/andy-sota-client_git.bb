DESCRIPTION = "andy-sota-client"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

DEPENDS = "jsoncpp boost aktualizr"

SRC_URI:lmp = "\
    file://main.cc \
    file://CMakeLists.txt \
"

S = "${WORKDIR}"

inherit pkgconfig cmake
