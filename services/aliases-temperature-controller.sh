# Aliases for temperature controller - to be placed in /etc/profile.d

# Set default location for scripts - note if running multiple control processes there may be multiple dirs
${SCRIPTDIR}=/opt/scripts/temperature-controller

alias s="${SCRIPTDIR}/temperature_controller.sh set"
alias g="${SCRIPTDIR}/temperature_controller.sh get"
alias a="${SCRIPTDIR}/temperature_controller.sh analyse"
alias s3="${SCRIPTDIR}/temperature_controller.sh sync"
