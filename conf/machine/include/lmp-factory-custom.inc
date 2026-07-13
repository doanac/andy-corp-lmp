# LMP factory specific customizations (either replace or extend options as defined by meta-lmp)

KERNEL_FEATURES:append = " features/nfsd/nfsd-enable.scc"

# Factory signing keys location.
# Precedence: FACTORY_KEYS_DIR (env / kas var) > vendored <layer>/factory-keys
#             > legacy ${TOPDIR}/conf/factory-keys (repo + setup-environment flow).
FACTORY_KEYS_LAYERDIR := "${@os.path.normpath(os.path.dirname(d.getVar('FILE', True)) + '/../../..')}"
FACTORY_KEYS_DIR ??= "${@('%s/factory-keys' % d.getVar('FACTORY_KEYS_LAYERDIR')) if os.path.isdir('%s/factory-keys' % d.getVar('FACTORY_KEYS_LAYERDIR')) else (d.getVar('TOPDIR') + '/conf/factory-keys')}"

# kernel modules signing key
MODSIGN_KEY_DIR = "${FACTORY_KEYS_DIR}"
MODSIGN_PRIVKEY = "${MODSIGN_KEY_DIR}/privkey_modsign.pem"
MODSIGN_X509 = "${MODSIGN_KEY_DIR}/x509_modsign.crt"

# U-Boot signing key
UBOOT_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}"
UBOOT_SIGN_KEYNAME = "ubootdev"

# OP-TEE: Custom TA signing key
OPTEE_TA_SIGN_KEY = "${FACTORY_KEYS_DIR}/opteedev.key"

# SPL / U-Boot proper signing key
UBOOT_SPL_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}"
UBOOT_SPL_SIGN_KEYNAME = "spldev"

# UEFI keys and certificates
UEFI_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}/uefi"

# TF-A Trusted Boot
TF_A_SIGN_KEY_PATH = "${FACTORY_KEYS_DIR}/tf-a/privkey_ec_prime256v1.pem"
