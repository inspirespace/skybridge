#!/usr/bin/env sh
set -eu

WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"
VENV_DIR="/firebase-emulator/functions-venv"
EXPORT_ROOT="${WORKSPACE_DIR}/.firebase-emulator/exports"
LEGACY_ROOT="${EXPORT_ROOT}/legacy"

echo "Installing firebase emulator dependencies..."
apk add --no-cache curl python3 py3-pip py3-virtualenv openjdk21-jre
java -version
npm install -g firebase-tools@15.7.0

echo "Preparing functions venv at ${VENV_DIR}..."
if [ -f "${VENV_DIR}/bin/activate" ] && ! grep -q "${VENV_DIR}" "${VENV_DIR}/bin/activate"; then
  rm -rf "${VENV_DIR}"
fi
if [ ! -x "${VENV_DIR}/bin/python" ]; then
  rm -rf "${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

if [ -e "${WORKSPACE_DIR}/functions/venv" ] && [ ! -L "${WORKSPACE_DIR}/functions/venv" ]; then
  rm -rf "${WORKSPACE_DIR}/functions/venv"
fi
ln -sfn "${VENV_DIR}" "${WORKSPACE_DIR}/functions/venv"
ln -sfn "${VENV_DIR}/bin/python" "${VENV_DIR}/bin/python3.11"
if [ -d "${VENV_DIR}/lib/python3.12" ]; then
  ln -sfn "${VENV_DIR}/lib/python3.12" "${VENV_DIR}/lib/python3.11"
fi

"${VENV_DIR}/bin/python" -m ensurepip --upgrade
"${VENV_DIR}/bin/python" -m pip install -r "${WORKSPACE_DIR}/functions/requirements.txt"

echo "Preparing emulator export directory..."
mkdir -p "${EXPORT_ROOT}" "${LEGACY_ROOT}"
for legacy_dir in "${WORKSPACE_DIR}"/firebase-export-*; do
  if [ -d "${legacy_dir}" ]; then
    mv "${legacy_dir}" "${LEGACY_ROOT}/$(basename "${legacy_dir}")"
  fi
done
for legacy_file in "${WORKSPACE_DIR}"/firebase-export-*.json; do
  if [ -f "${legacy_file}" ]; then
    mv "${legacy_file}" "${LEGACY_ROOT}/$(basename "${legacy_file}")"
  fi
done

PROJECT_ID="$(sh "${WORKSPACE_DIR}/scripts/firebase-config.sh" project)"
REGION="$(sh "${WORKSPACE_DIR}/scripts/firebase-config.sh" region)"
if [ -z "${PROJECT_ID}" ]; then
  echo "Missing default Firebase project in .firebaserc" >&2
  exit 1
fi

echo "Starting Firebase emulators for project ${PROJECT_ID} (region: ${REGION})..."
cd "${WORKSPACE_DIR}"
FIREBASE_REGION="${REGION}" firebase emulators:start \
  --config "${WORKSPACE_DIR}/firebase.json" \
  --project "${PROJECT_ID}" \
  --only auth,firestore,pubsub,storage,functions,hosting \
  --import "${EXPORT_ROOT}" \
  --export-on-exit "${EXPORT_ROOT}"
