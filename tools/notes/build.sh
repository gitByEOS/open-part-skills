#!/bin/sh
set -eu

cd "$(dirname "$0")/../.."
exec npm --prefix tools/notes run build
