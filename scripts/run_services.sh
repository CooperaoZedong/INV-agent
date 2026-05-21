#!/usr/bin/env bash

set -e

init_variables() {
  options=( "$@" )

  valid_options=(
    "--help"
    "--build-agent-image"
    "--run-agent-service"
  )

  DEFAULT_AGENT_IMAGE_NAME=pomoika-agent-service
  DEFAULT_IMAGE_VERSION=latest
  #DEFAULT_

  if [ -z "${AGENT_IMAGE_NAME}" ]; then
     export AGENT_IMAGE_NAME=${DEFAULT_AGENT_IMAGE_NAME}
  fi

  if [ -z "${NECTIT_IMAGE_VERSION}" ]; then
     export NECTIT_IMAGE_VERSION=${DEFAULT_IMAGE_VERSION}
  fi
}

check_help_message() {
  if [[ "$#" -eq 1 ]] && [ $options = "--help" ]; then
    print_help_and_exit
  fi
}

build_agent_image() {
  if [[ "$#" -ne 0 ]] && array_contains options "--build-agent-image"; then
    pushd ${PA_HOME}/docker

    docker build -t ${AGENT_IMAGE_NAME}:${AGENT_IMAGE_VERSION}

    popd
  fi
}

run_agent_image() {
  if [[ "$#" -ne 0 ]] && array_contains options "--run-agent-service"; then
    pushd ${KI_HOME}/docker

    docker-compose up -d

    popd
  fi
}

array_contains () {
  local array="$1[@]"
  local seeking=$2
  local in=1
  for element in "${!array}"; do
    if [[ $seeking == $element* ]]; then
        return 0
    fi
  done
  return 1
}

check_options_are_valid () {
  for i in "${options[@]}"
  do
    if ! array_contains valid_options $i; then
      print_help_and_exit
      exit
    fi;
  done
}

print_help_and_exit() {
    cat << EOF
    Options:
      --help                              Show usage with available options.Has no effect if combined with other options.
      --build-agent-image                Builds nectit image from docker file
      --run-agent-service                Runs build nectit image
EOF
    exit
}

init_variables $@
check_options_are_valid $@
check_help_message $@
build_agent_image $@
run_agent_image $@
