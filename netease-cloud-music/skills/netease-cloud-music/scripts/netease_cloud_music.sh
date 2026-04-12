#!/bin/sh
set -eu

find_ncmctl() {
  if command -v ncmctl >/dev/null 2>&1; then
    command -v ncmctl
    return 0
  fi

  gobin="$(go env GOBIN 2>/dev/null || true)"
  if [ -n "${gobin}" ] && [ -x "${gobin}/ncmctl" ]; then
    printf '%s\n' "${gobin}/ncmctl"
    return 0
  fi

  gopath="$(go env GOPATH 2>/dev/null || true)"
  if [ -n "${gopath}" ] && [ -x "${gopath}/bin/ncmctl" ]; then
    printf '%s\n' "${gopath}/bin/ncmctl"
    return 0
  fi

  return 1
}

if ! ncmctl_bin="$(find_ncmctl)"; then
  echo "ncmctl not found." >&2
  echo "Install it first:" >&2
  echo "  go install github.com/chaunsin/netease-cloud-music/cmd/ncmctl@latest" >&2
  exit 127
fi

exec "${ncmctl_bin}" "$@"
