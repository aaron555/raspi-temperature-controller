# Aliases for temperature controller - to be placed in /etc/profile.d
source /etc/controller.conf
if [[ ! -f ${SCRIPTDIR}/temperature_controller.sh ]]; then
  # Set default location for scripts
  ${SCRIPTDIR}=/opt/scripts/temperature-controller
fi
alias s="${SCRIPTDIR}/temperature_controller.sh set"
alias g="${SCRIPTDIR}/temperature_controller.sh get"
alias a="${SCRIPTDIR}/temperature_controller.sh analyse"
alias s3="${SCRIPTDIR}/temperature_controller.sh sync"
