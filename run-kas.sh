#!/bin/bash
set -eo pipefail

here=$(dirname $(readlink -f 0))

if [ $# -ne 1 ] ; then
	echo "Usage: $0 [checkout|build]"
	exit 1
fi
action="$1"
if [ "$action" != "build" ] && [ "$action" != "checkout" ] ; then
	echo "Usage: $0 [checkout|build]"
	exit 1
fi

kas_cache="${KAS_CACHE-${here}/.kas-cache}"
export DL_DIR=${kas_cache}/downloads
export SSTATE_DIR=${kas_cache}/sstate-cache
export KAS_WORK_DIR="${KAS_WORK_DIR-${here}/.kas-work}"
FACTORY_KEYS_DIR="${FACTORY_KEYS_DIR-${here}/factory-keys}"

if [ ! -d "${FACTORY_KEYS_DIR}" ] ; then
	echo "ERROR: Missing FACTORY_KEYS_DIR does not exist"
	exit 1
fi
export FACTORY_KEYS_DIR=$(readlink -f ${FACTORY_KEYS_DIR})

if [ -z "${H_BUILD}" ] ; then
	echo "ERROR: H_BUILD must be set to an integer"
	exit 1
fi

mkdir -p $KAS_WORK_DIR/build/conf $DL_DIR $SSTATE_DIR

exec ./kas-container --runtime-args "-v $FACTORY_KEYS_DIR:/work/build/conf/factory-keys:ro -e H_BUILD=$H_BUILD" $action kas/lmp-factory-image.yml
