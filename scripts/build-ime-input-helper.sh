#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
sdk_root=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}

if [[ -z "$sdk_root" ]]; then
    echo "Set ANDROID_HOME or ANDROID_SDK_ROOT to an Android SDK." >&2
    exit 1
fi

platform_dir=$(find "$sdk_root/platforms" -mindepth 1 -maxdepth 1 -type d -name 'android-*' | sort -V | tail -1)
build_tools_dir=$(find "$sdk_root/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)
if [[ -z "$platform_dir" || -z "$build_tools_dir" ]]; then
    echo "Android SDK platform and build tools are required." >&2
    exit 1
fi

build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT

android_jar="$platform_dir/android.jar"
aapt2="$build_tools_dir/aapt2"
d8="$build_tools_dir/d8"
apksigner="$build_tools_dir/apksigner"
source_dir="$project_dir/android/ime-input"
output_file="$project_dir/src/vphone/device/adb/resources/vphone-ime-input.apk"
keystore="$source_dir/vphone-debug.keystore"

mkdir -p "$build_dir/classes" "$build_dir/dex" "$(dirname -- "$output_file")"
"$aapt2" compile --dir "$source_dir/res" -o "$build_dir/resources.zip"
"$aapt2" link \
    -o "$build_dir/unsigned.apk" \
    -I "$android_jar" \
    --manifest "$source_dir/AndroidManifest.xml" \
    --min-sdk-version 21 \
    --target-sdk-version 35 \
    "$build_dir/resources.zip"

javac \
    -source 8 \
    -target 8 \
    -bootclasspath "$android_jar" \
    -d "$build_dir/classes" \
    "$source_dir/src/dev/vphone/input/VPhoneInputMethodService.java"
"$d8" \
    --lib "$android_jar" \
    --min-api 21 \
    --output "$build_dir/dex" \
    "$build_dir/classes/dev/vphone/input/VPhoneInputMethodService.class" \
    "$build_dir/classes/dev/vphone/input/VPhoneInputMethodService\$1.class"

cp "$build_dir/unsigned.apk" "$build_dir/with-dex.apk"
zip -q -j "$build_dir/with-dex.apk" "$build_dir/dex/classes.dex"
"$apksigner" sign \
    --ks "$keystore" \
    --ks-pass pass:vphone \
    --key-pass pass:vphone \
    --v4-signing-enabled false \
    --out "$output_file" \
    "$build_dir/with-dex.apk"

echo "Built $output_file"
